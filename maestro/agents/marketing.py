from maestro.config import Settings
from maestro.profiles._schema import BusinessProfile
from maestro.schemas.events import AgentResult, AgentRunRecord, ApprovalRequest
from maestro.subagents.marketing import (
    choose_hashtags,
    create_visual_prompts,
    suggest_post_time,
    write_caption,
)


class MarketingAgent:
    def __init__(self, settings: Settings, profile: BusinessProfile) -> None:
        self.settings = settings
        self.profile = profile

    async def create_post(self, topic: str) -> tuple[AgentResult, AgentRunRecord]:
        visual_prompts = create_visual_prompts(topic, self.profile)
        caption = write_caption(topic, self.profile)
        hashtags = choose_hashtags(self.profile)
        scheduled_at = suggest_post_time(self.profile)
        preview = {
            "topic": topic,
            "caption": caption,
            "hashtags": hashtags,
            "visual_prompts": visual_prompts,
            "scheduled_at": scheduled_at,
            "dry_run": self.settings.dry_run,
            "profit_signal": "demand_generation",
        }
        approval = ApprovalRequest(
            business=self.profile.business_id,
            event_id=f"marketing:{self.profile.business_id}:{topic}",
            action="marketing_publish_or_schedule_post",
            preview=preview,
        )
        message = f"Marketing draft ready for {self.profile.business_name}: {topic}"
        result = AgentResult(
            business=self.profile.business_id,
            agent_name="marketing",
            message=message,
            data=preview,
            approval=approval,
            profit_signal="demand_generation",
        )
        run = AgentRunRecord(
            business=self.profile.business_id,
            agent_name="marketing",
            input=topic,
            output=result.model_dump_json(),
            profit_signal="demand_generation",
            prompt_version=self.settings.prompt_version,
            dry_run=self.settings.dry_run,
        )
        return result, run
