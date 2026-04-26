from maestro.agents.cfo import CFOAgent
from maestro.agents.cmo import CMOAgent
from maestro.config import Settings
from maestro.profiles._schema import BusinessProfile
from maestro.schemas.events import AgentResult, AgentRunRecord, ApprovalRequest
from maestro.subagents.ceo import create_weekly_briefing, prepare_decisions


class CEOAgent:
    def __init__(self, settings: Settings, profile: BusinessProfile) -> None:
        self.settings = settings
        self.profile = profile

    async def run(self, request: str = "weekly executive briefing") -> tuple[AgentResult, AgentRunRecord]:
        cfo_result, _ = await CFOAgent(self.settings, self.profile).run(request)
        cmo_result, _ = await CMOAgent(self.settings, self.profile).run(request)
        briefing = create_weekly_briefing(self.profile.business_name, cfo_result.data, cmo_result.data)
        decisions = prepare_decisions(self.profile)

        # Determine if any strategic decision requires HITL approval
        threshold = self.profile.decision_thresholds.thiago_approval_above_usd
        high_impact_decisions = [d for d in decisions if d["estimated_impact_usd"] > threshold]
        requires_approval = len(high_impact_decisions) > 0

        data = {
            "request": request,
            "briefing": briefing,
            "decisions": decisions,
            "high_impact_decisions": high_impact_decisions,
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
