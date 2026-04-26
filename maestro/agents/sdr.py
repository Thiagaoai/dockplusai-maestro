from maestro.config import Settings
from maestro.profiles._schema import BusinessProfile
from maestro.schemas.events import AgentRunRecord, ApprovalRequest, LeadIn, LeadRecord
from maestro.subagents.sdr import draft_email, qualify_lead, suggest_meeting_slots


class SDRAgent:
    def __init__(self, settings: Settings, profile: BusinessProfile) -> None:
        self.settings = settings
        self.profile = profile

    async def prepare_lead(self, lead_in: LeadIn) -> tuple[LeadRecord, ApprovalRequest, AgentRunRecord]:
        lead = LeadRecord(**lead_in.model_dump())
        qualification = qualify_lead(lead, self.profile)
        score = qualification["score"]
        reasoning = qualification["justification"]
        lead.qualification_score = score
        lead.qualification_reasoning = reasoning

        email = draft_email(lead, self.profile)
        slots = suggest_meeting_slots()
        preview = {
            "lead": {
                "name": lead.name,
                "source": lead.source,
                "estimated_ticket_usd": lead.estimated_ticket_usd,
                "qualification_score": score,
                "qualification_reasoning": reasoning,
            },
            "email": email,
            "meeting_slots": slots,
            "dry_run": self.settings.dry_run,
            "profit_signal": "conversion",
        }
        approval = ApprovalRequest(
            business=lead.business,
            lead_id=lead.id,
            event_id=lead.event_id,
            action="sdr_dry_run_follow_up",
            preview=preview,
        )
        run = AgentRunRecord(
            business=lead.business,
            agent_name="sdr",
            input=lead.model_dump_json(),
            output=approval.model_dump_json(),
            profit_signal="conversion",
            prompt_version=self.settings.prompt_version,
            dry_run=self.settings.dry_run,
        )
        return lead, approval, run
