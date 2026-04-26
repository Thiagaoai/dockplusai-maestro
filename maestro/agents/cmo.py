import structlog

from maestro.config import Settings
from maestro.profiles._schema import BusinessProfile
from maestro.schemas.events import AgentResult, AgentRunRecord, ApprovalRequest
from maestro.services.marketing_channels import (
    GBPClient,
    GoogleAdsClient,
    MarketingChannelError,
    MetaAdsClient,
)
from maestro.subagents.cmo import (
    analyze_ad_performance,
    recommend_budget_actions,
    suggest_creative_tests,
)

log = structlog.get_logger()


class CMOAgent:
    def __init__(self, settings: Settings, profile: BusinessProfile) -> None:
        self.settings = settings
        self.profile = profile

    async def run(self, request: str = "weekly marketing briefing") -> tuple[AgentResult, AgentRunRecord]:
        real_performance = await self._real_performance()
        performance = analyze_ad_performance(self.profile, real_performance)
        if real_performance["sources"]:
            performance = {**performance, **real_performance}
        threshold = self.profile.decision_thresholds.thiago_approval_above_usd
        budget = recommend_budget_actions(
            self.profile.ads.monthly_budget_usd,
            threshold,
            spend_usd_last_30d=performance.get("real_spend_usd_last_30d")
            or performance.get("spend_usd_last_30d")
            or 0.0,
            performance_signal=performance.get("performance_signal", "no_data"),
        )
        creative_tests = suggest_creative_tests(self.profile.business_name, self.profile.business_type)
        creative_tests = [
            {
                **test,
                "requires_approval": float(test.get("estimated_budget_usd") or 0) > threshold,
            }
            for test in creative_tests
        ]

        llm_summary = await self._llm_summarize(performance, budget, creative_tests)
        top_creative_tests = llm_summary.get("top_creative_tests") or creative_tests[:2]

        data = {
            "request": request,
            "tools_called": {
                "meta_ads": real_performance.get("meta"),
                "google_ads": real_performance.get("google_ads"),
                "gbp": real_performance.get("gbp_status"),
            },
            "performance": performance,
            "budget": budget,
            "creative_tests": creative_tests,
            "top_creative_tests": top_creative_tests,
            "llm_summary": llm_summary,
        }

        message = llm_summary.get("summary") or (
            f"CMO {self.profile.business_name}: {len(creative_tests)} creative tests ready."
        )

        approval = None
        requires_creative_approval = any(test.get("requires_approval") for test in top_creative_tests)
        if budget["requires_approval"] or requires_creative_approval:
            approval = ApprovalRequest(
                business=self.profile.business_id,
                event_id=f"cmo:{self.profile.business_id}:budget",
                action="cmo_budget_test_dry_run",
                preview={
                    "budget": budget,
                    "performance": performance,
                    "creative_tests": top_creative_tests,
                    "threshold_usd": threshold,
                    "dry_run": self.settings.dry_run,
                    "profit_signal": "roas",
                },
            )

        log.info(
            "cmo_run_complete",
            business=self.profile.business_id,
            creative_tests=len(creative_tests),
            prompt_version=self.settings.prompt_version,
        )

        result = AgentResult(
            business=self.profile.business_id,
            agent_name="cmo",
            message=message,
            data=data,
            approval=approval,
            profit_signal="roas",
        )
        run = AgentRunRecord(
            business=self.profile.business_id,
            agent_name="cmo",
            input=request,
            output=result.model_dump_json(),
            profit_signal="roas",
            prompt_version=self.settings.prompt_version,
            dry_run=self.settings.dry_run,
        )
        return result, run

    async def _llm_summarize(self, performance: dict, budget: dict, creative_tests: list) -> dict:
        if not self.settings.anthropic_api_key:
            return {}
        try:
            from maestro.utils.llm import SONNET, UnknownModelPricingError, call_claude_json
            from maestro.utils.prompts import load_prompt

            context = {
                "business_name": self.profile.business_name,
                "business_type": self.profile.business_type,
                "offerings": self.profile.offerings,
                "tone": self.profile.tone,
                "ads": self.profile.ads,
                "decision_thresholds": self.profile.decision_thresholds,
                "performance": performance,
                "budget": budget,
                "creative_tests": creative_tests,
            }
            prompt = load_prompt("cmo_weekly_briefing", context)
            result = await call_claude_json(
                system="You are the CMO agent. Follow the output format exactly. Return only valid JSON.",
                user=prompt,
                settings=self.settings,
                model=SONNET,
                max_tokens=768,
            )
            log.info("cmo_llm_summary_ok", business=self.profile.business_id)
            return result
        except UnknownModelPricingError:
            raise
        except Exception as exc:
            log.warning("cmo_llm_summary_failed", error=str(exc))
            return {}

    async def _real_performance(self) -> dict:
        alerts: list[str] = []
        sources: list[str] = []
        meta = await self._safe_meta()
        google = await self._safe_google_ads()
        gbp = await self._safe_gbp()
        for label, data in {"meta": meta, "google": google, "gbp": gbp}.items():
            if data["status"] == "ok":
                sources.extend(data.get("sources", []))
            elif data["status"] == "error":
                alerts.append(f"{label} error: {data.get('error')}")
        spend = sum(float(data.get("spend_usd") or 0) for data in (meta, google))
        clicks = sum(int(data.get("clicks") or 0) for data in (meta, google))
        impressions = sum(int(data.get("impressions") or 0) for data in (meta, google))
        return {
            "real_spend_usd_last_30d": round(spend, 2),
            "real_clicks_last_30d": clicks,
            "real_impressions_last_30d": impressions,
            "meta": meta,
            "google_ads": google,
            "gbp_status": gbp,
            "sources": sources,
            "alerts": alerts or ["Real ads/GBP sources connected where credentials are configured."],
        }

    async def _safe_meta(self) -> dict:
        try:
            return await MetaAdsClient(self.settings).account_insights(self.profile.business_id)
        except MarketingChannelError as exc:
            return {"status": "error", "error": str(exc)[:300], "sources": ["meta_ads:error"]}

    async def _safe_google_ads(self) -> dict:
        try:
            return await GoogleAdsClient(self.settings).customer_insights(self.profile.business_id)
        except MarketingChannelError as exc:
            return {"status": "error", "error": str(exc)[:300], "sources": ["google_ads:error"]}

    async def _safe_gbp(self) -> dict:
        try:
            return await GBPClient(self.settings).account_status()
        except MarketingChannelError as exc:
            return {"status": "error", "error": str(exc)[:300], "sources": ["gbp:error"]}
