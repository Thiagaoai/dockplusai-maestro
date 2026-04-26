from maestro.config import Settings
from maestro.profiles._schema import BusinessProfile
from maestro.schemas.events import AgentResult, AgentRunRecord, ApprovalRequest
from maestro.subagents.operations import (
    prepare_calendar_action,
    prepare_follow_up,
    prepare_pipeline_move,
)


class OperationsAgent:
    def __init__(self, settings: Settings, profile: BusinessProfile) -> None:
        self.settings = settings
        self.profile = profile

    async def prepare_task(self, text: str) -> tuple[AgentResult, AgentRunRecord]:
        lowered = text.lower()
        if "calendar" in lowered or "schedule" in lowered or "agendar" in lowered:
            prepared = prepare_calendar_action(text)
        elif "pipeline" in lowered or "stage" in lowered or "ghl" in lowered:
            prepared = prepare_pipeline_move(text)
        else:
            prepared = prepare_follow_up(text)
        approval = ApprovalRequest(
            business=self.profile.business_id,
            event_id=f"operations:{self.profile.business_id}:{text}",
            action="operations_external_action_dry_run",
            preview={
                "task": text,
                "prepared": prepared,
                "dry_run": self.settings.dry_run,
                "profit_signal": "time_saved",
            },
        )
        result = AgentResult(
            business=self.profile.business_id,
            agent_name="operations",
            message=f"Operations task prepared for approval: {prepared['kind']}",
            data=approval.preview,
            approval=approval,
            profit_signal="time_saved",
        )
        run = AgentRunRecord(
            business=self.profile.business_id,
            agent_name="operations",
            input=text,
            output=result.model_dump_json(),
            profit_signal="time_saved",
            prompt_version=self.settings.prompt_version,
            dry_run=self.settings.dry_run,
        )
        return result, run
