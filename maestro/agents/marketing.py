import structlog
from langsmith import traceable

from maestro.config import Settings
from maestro.profiles._schema import BusinessProfile
from maestro.schemas.events import AgentResult, AgentRunRecord, ApprovalRequest
from maestro.subagents.marketing import choose_hashtags, create_visual_prompts, suggest_post_time, write_caption

log = structlog.get_logger()


class MarketingAgent:
    def __init__(self, settings: Settings, profile: BusinessProfile) -> None:
        self.settings = settings
        self.profile = profile

    @traceable(name="marketing_create_post", run_type="chain", tags=["agent", "marketing"])
    async def create_post(self, topic: str) -> tuple[AgentResult, AgentRunRecord]:
        post_content = await self._build_post_content(topic)

        preview = {
            "topic": topic,
            "caption": post_content["caption"],
            "hashtags": post_content["hashtags"],
            "visual_prompts": post_content["visual_prompts"],
            "image_url": post_content.get("image_url", ""),
            "scheduled_at": post_content["scheduled_at"],
            "platform": "instagram",
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

        log.info(
            "marketing_post_drafted",
            business=self.profile.business_id,
            topic=topic[:40],
            prompt_version=self.settings.prompt_version,
        )
        return result, run

    async def _build_post_content(self, topic: str) -> dict:
        from maestro.subagents.marketing.caption_writer import create_post_with_llm

        return await create_post_with_llm(topic, self.profile, self.settings)
