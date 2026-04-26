from maestro.config import Settings
from maestro.profiles._schema import BusinessProfile
from maestro.schemas.events import AgentResult, AgentRunRecord, ApprovalRequest
from maestro.services.marketing_channels import GBPClient, GoogleAdsClient, MarketingChannelError, MetaAdsClient
from maestro.subagents.cmo import (
    analyze_ad_performance,
    recommend_budget_actions,
    suggest_creative_tests,
)


class CMOAgent:
    def __init__(self, settings: Settings, profile: BusinessProfile) -> None:
        self.settings = settings
        self.profile = profile

    async def run(self, request: str = "weekly marketing briefing") -> tuple[AgentResult, AgentRunRecord]:
        performance = analyze_ad_performance(self.profile)
        real_performance = await self._real_performance()
        if real_performance["sources"]:
            performance = {
                **performance,
                **real_performance,
                "cpl_trend": "available_from_real_sources",
                "roas_trend": "available_from_real_sources",
                "alerts": real_performance["alerts"],
            }
        threshold = self.profile.decision_thresholds.thiago_approval_above_usd
        budget = recommend_budget_actions(self.profile.ads.monthly_budget_usd, threshold)
        creative_tests = suggest_creative_tests(self.profile.business_name)
        data = {
            "request": request,
            "performance": performance,
            "budget": budget,
            "creative_tests": creative_tests,
        }
        approval = None
        if budget["requires_approval"]:
            approval = ApprovalRequest(
                business=self.profile.business_id,
                event_id=f"cmo:{self.profile.business_id}:budget",
                action="cmo_budget_test_dry_run",
                preview={
                    "budget": budget,
                    "performance": performance,
                    "creative_tests": creative_tests,
                    "threshold_usd": threshold,
                    "dry_run": self.settings.dry_run,
                    "profit_signal": "roas",
                },
            )
        result = AgentResult(
            business=self.profile.business_id,
            agent_name="cmo",
            message=f"CMO {self.profile.business_name}: {len(creative_tests)} creative tests ready.",
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
