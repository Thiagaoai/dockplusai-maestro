from maestro.config import Settings
from maestro.profiles._schema import BusinessProfile
from maestro.schemas.events import AgentResult, AgentRunRecord, ApprovalRequest
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
        budget = recommend_budget_actions(self.profile.ads.monthly_budget_usd)
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
                preview=data,
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
