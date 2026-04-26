from maestro.agents.cfo import CFOAgent
from maestro.agents.cmo import CMOAgent
from maestro.config import Settings
from maestro.profiles._schema import BusinessProfile
from maestro.schemas.events import AgentResult, AgentRunRecord
from maestro.subagents.ceo import create_weekly_briefing, prepare_decisions


class CEOAgent:
    def __init__(self, settings: Settings, profile: BusinessProfile) -> None:
        self.settings = settings
        self.profile = profile

    async def run(self, request: str = "weekly executive briefing") -> tuple[AgentResult, AgentRunRecord]:
        cfo_result, _ = await CFOAgent(self.settings, self.profile).run(request)
        cmo_result, _ = await CMOAgent(self.settings, self.profile).run(request)
        briefing = create_weekly_briefing(self.profile.business_name, cfo_result.data, cmo_result.data)
        decisions = prepare_decisions(self.profile.business_name)
        data = {
            "request": request,
            "briefing": briefing,
            "decisions": decisions,
            "cfo": cfo_result.data,
            "cmo": cmo_result.data,
        }
        result = AgentResult(
            business=self.profile.business_id,
            agent_name="ceo",
            message=briefing,
            data=data,
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
