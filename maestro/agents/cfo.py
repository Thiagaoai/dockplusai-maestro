import structlog
from langsmith import traceable

from maestro.config import Settings
from maestro.profiles._schema import BusinessProfile
from maestro.schemas.events import AgentResult, AgentRunRecord, ApprovalRequest
from maestro.services.highlevel import HighLevelClient
from maestro.services.stripe import StripeClient, StripeError
from maestro.subagents.cfo import (
    analyze_margin,
    forecast_cashflow,
    recommend_financial_actions,
    reconcile_invoices,
)

log = structlog.get_logger()


class CFOAgent:
    def __init__(self, settings: Settings, profile: BusinessProfile) -> None:
        self.settings = settings
        self.profile = profile

    @traceable(name="cfo_run", run_type="chain", tags=["agent", "cfo"])
    async def run(self, question: str = "weekly financial briefing") -> tuple[AgentResult, AgentRunRecord]:
        stripe_summary = await self._stripe_summary()
        pipeline_summary = await self._pipeline_summary()
        reconciliation = reconcile_invoices(
            self.profile.business_id,
            stripe_summary=stripe_summary,
            pipeline_summary=pipeline_summary,
        )
        revenue = stripe_summary.get("gross_revenue_usd") if stripe_summary.get("status") == "ok" else None
        margin = analyze_margin(self.profile, revenue_usd=revenue)
        cashflow = forecast_cashflow(
            margin["estimated_revenue_usd"],
            pipeline_value_usd=float(pipeline_summary.get("open_value_usd") or 0.0),
            collected_revenue_usd=float(stripe_summary.get("gross_revenue_usd") or 0.0),
        )
        action_plan = recommend_financial_actions(self.profile, margin, cashflow, reconciliation)

        llm_summary = await self._llm_summarize(margin, cashflow, reconciliation)
        summary_actions = llm_summary.get("recommended_actions") or action_plan["actions"]

        data = {
            "question": question,
            "tools_called": {
                "stripe": stripe_summary,
                "ghl_pipeline": pipeline_summary,
            },
            "reconciliation": reconciliation,
            "margin": margin,
            "cashflow": cashflow,
            "recommended_actions": {**action_plan, "llm_actions": summary_actions},
            "sources": reconciliation["sources"] + margin["sources"] + cashflow["sources"],
            "llm_summary": llm_summary,
        }

        message = llm_summary.get("summary") or (
            f"CFO {self.profile.business_name}: estimated gross margin "
            f"{margin['estimated_gross_margin_pct']}%. "
            f"{len(action_plan['actions'])} action(s) recommended."
        )

        approval = None
        if action_plan["requires_approval"]:
            approval = ApprovalRequest(
                business=self.profile.business_id,
                event_id=f"cfo:{self.profile.business_id}:actions",
                action="cfo_financial_actions_dry_run",
                preview={
                    "actions": action_plan["actions"],
                    "llm_actions": summary_actions,
                    "signals": {
                        "margin": margin.get("margin_signal"),
                        "cashflow": cashflow.get("cashflow_signal"),
                    },
                    "max_impact_usd": action_plan["max_impact_usd"],
                    "threshold_usd": action_plan["threshold_usd"],
                    "dry_run": self.settings.dry_run,
                    "profit_signal": "margin",
                },
            )

        log.info(
            "cfo_run_complete",
            business=self.profile.business_id,
            margin_pct=margin["estimated_gross_margin_pct"],
            actions=len(action_plan["actions"]),
            prompt_version=self.settings.prompt_version,
        )

        result = AgentResult(
            business=self.profile.business_id,
            agent_name="cfo",
            message=message,
            data=data,
            approval=approval,
            profit_signal="margin",
        )
        run = AgentRunRecord(
            business=self.profile.business_id,
            agent_name="cfo",
            input=question,
            output=result.model_dump_json(),
            profit_signal="margin",
            prompt_version=self.settings.prompt_version,
            dry_run=self.settings.dry_run,
        )
        return result, run

    async def _llm_summarize(self, margin: dict, cashflow: dict, reconciliation: dict) -> dict:
        if not self.settings.anthropic_api_key:
            return {}
        try:
            from maestro.utils.llm import SONNET, call_claude_json
            from maestro.utils.prompts import load_prompt

            context = {
                "business_name": self.profile.business_name,
                "business_type": self.profile.business_type,
                "offerings": self.profile.offerings,
                "decision_thresholds": self.profile.decision_thresholds,
                "margin": margin,
                "cashflow": cashflow,
                "reconciliation": reconciliation,
            }
            prompt = load_prompt("cfo_weekly_briefing", context)
            result = await call_claude_json(
                system="You are the CFO agent. Follow the output format exactly. Return only valid JSON.",
                user=prompt,
                settings=self.settings,
                model=SONNET,
                max_tokens=768,
            )
            log.info("cfo_llm_summary_ok", business=self.profile.business_id)
            return result
        except Exception as exc:
            log.warning("cfo_llm_summary_failed", error=str(exc))
            return {}

    async def _stripe_summary(self) -> dict:
        try:
            return await StripeClient(self.settings).recent_charges_summary(self.profile.business_id)
        except StripeError as exc:
            return {"status": "error", "error": str(exc)[:300], "sources": ["stripe:error"]}

    async def _pipeline_summary(self) -> dict:
        try:
            return await HighLevelClient(self.settings).pipeline_summary(self.profile.business_id)
        except Exception as exc:
            return {"status": "error", "error": str(exc)[:300], "sources": ["ghl:error"]}
