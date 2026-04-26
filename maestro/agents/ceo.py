import structlog
from langsmith import traceable

from maestro.agents.cfo import CFOAgent
from maestro.agents.cmo import CMOAgent
from maestro.config import Settings
from maestro.profiles._schema import BusinessProfile
from maestro.schemas.events import AgentResult, AgentRunRecord, ApprovalRequest
from maestro.subagents.ceo.weekly_briefing import create_briefing_with_decisions

log = structlog.get_logger()


class CEOAgent:
    def __init__(self, settings: Settings, profile: BusinessProfile) -> None:
        self.settings = settings
        self.profile = profile

    @traceable(name="ceo_run", run_type="chain", tags=["agent", "ceo"])
    async def run(self, request: str = "weekly executive briefing") -> tuple[AgentResult, AgentRunRecord]:
        cfo_result, _ = await CFOAgent(self.settings, self.profile).run(request)
        cmo_result, _ = await CMOAgent(self.settings, self.profile).run(request)

        briefing_data = await create_briefing_with_decisions(
            self.profile, cfo_result.data, cmo_result.data, self.settings
        )
        briefing = briefing_data["briefing"]
        decisions = briefing_data["decisions"]

        threshold = self.profile.decision_thresholds.thiago_approval_above_usd
        high_impact_decisions = [d for d in decisions if d.get("estimated_impact_usd", 0) > threshold]
        requires_approval = len(high_impact_decisions) > 0

        data = {
            "request": request,
            "briefing": briefing,
            "week_priority": briefing_data.get("week_priority", ""),
            "decisions": decisions,
            "high_impact_decisions": high_impact_decisions,
            "executive_signals": self._executive_signals(cfo_result.data, cmo_result.data),
            "cfo": cfo_result.data,
            "cmo": cmo_result.data,
        }

        approval = None
        if requires_approval:
            approval = ApprovalRequest(
                business=self.profile.business_id,
                event_id=f"ceo:{self.profile.business_id}:strategic_decisions",
                action="ceo_strategic_decisions_dry_run",
                preview={
                    "decisions": high_impact_decisions,
                    "threshold_usd": threshold,
                    "briefing_summary": briefing[:200],
                    "dry_run": self.settings.dry_run,
                    "profit_signal": "decision_quality",
                },
            )

        log.info(
            "ceo_run_complete",
            business=self.profile.business_id,
            decisions=len(decisions),
            high_impact=len(high_impact_decisions),
            prompt_version=self.settings.prompt_version,
        )

        result = AgentResult(
            business=self.profile.business_id,
            agent_name="ceo",
            message=briefing,
            data=data,
            approval=approval,
            profit_signal="decision_quality",
        )
        run = AgentRunRecord(
            business=self.profile.business_id,
            agent_name="ceo",
            input=request,
            output=result.model_dump_json(),
            profit_signal="decision_quality",
            prompt_version=self.settings.prompt_version,
            dry_run=self.settings.dry_run,
        )
        return result, run

    def _executive_signals(self, cfo_data: dict, cmo_data: dict) -> dict:
        margin = cfo_data.get("margin", {})
        cashflow = cfo_data.get("cashflow", {})
        performance = cmo_data.get("performance", {})
        return {
            "margin_signal": margin.get("margin_signal"),
            "cashflow_signal": cashflow.get("cashflow_signal"),
            "marketing_signal": performance.get("performance_signal"),
            "open_pipeline_value_usd": cfo_data.get("reconciliation", {}).get("open_pipeline_value_usd", 0),
            "top_growth_tests": cmo_data.get("top_creative_tests", [])[:2],
        }
