"""SDR Agent — qualifies leads, drafts emails, suggests meetings.

Enrichment waterfall:
1. Apollo (if available and plan allows)
2. Hunter.io fallback (if Apollo fails or plan-limited)
"""

from urllib.parse import urlparse

import structlog

from maestro.config import Settings
from maestro.profiles._schema import BusinessProfile
from maestro.schemas.events import AgentRunRecord, ApprovalRequest, LeadIn, LeadRecord
from maestro.subagents.sdr import draft_email, qualify_lead, suggest_meeting_slots
from maestro.tools._enrichment.apollo import enrich_lead
from maestro.tools._enrichment.hunter import find_email

log = structlog.get_logger()


def _domain_from_profile(profile: BusinessProfile) -> str | None:
    website = profile.contact.website if profile.contact else None
    if not website:
        return None
    try:
        parsed = urlparse(website)
        return parsed.netloc.replace("www.", "")
    except Exception:
        return None


class SDRAgent:
    def __init__(self, settings: Settings, profile: BusinessProfile) -> None:
        self.settings = settings
        self.profile = profile

    async def _maybe_enrich_lead(self, lead: LeadRecord) -> dict:
        """Enrich lead via Apollo → Hunter waterfall if contact data is incomplete."""
        has_email = bool(lead.email)
        has_phone = bool(lead.phone)

        if has_email and has_phone:
            return {"enriched": False, "reason": "complete_contact_data"}

        if not lead.name and not lead.email:
            return {"enriched": False, "reason": "insufficient_data_for_enrichment"}

        enrichment_meta: dict = {"apollo": {}, "hunter": {}}

        # Step 1: Apollo
        apollo_result = await enrich_lead(
            name=lead.name,
            email=lead.email,
            company_name=self.profile.business_name,
            idempotency_key=f"apollo:{lead.event_id}",
        )
        enrichment_meta["apollo"] = {
            "attempted": True,
            "plan_limited": apollo_result.get("plan_limited", False),
            "found": apollo_result.get("person") is not None,
        }

        person = apollo_result.get("person")
        if person:
            return self._apply_enrichment(lead, person, source="apollo")

        # Step 2: Hunter fallback (only if we have name + domain)
        if not lead.email and lead.name:
            domain = _domain_from_profile(self.profile)
            if not domain and self.profile.contact.email and "@" in self.profile.contact.email:
                domain = self.profile.contact.email.split("@", 1)[1]
            if domain:
                parts = lead.name.split(" ", 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ""

                hunter_result = await find_email(
                    first_name=first_name,
                    last_name=last_name,
                    domain=domain,
                    company=self.profile.business_name,
                    idempotency_key=f"hunter:{lead.event_id}",
                )
                enrichment_meta["hunter"] = {
                    "attempted": True,
                    "found": hunter_result.get("email") is not None,
                    "confidence": hunter_result.get("confidence"),
                }

                if hunter_result.get("email"):
                    lead.email = hunter_result["email"]
                    return {
                        "enriched": True,
                        "fields": ["email"],
                        "source": "hunter",
                        "email": hunter_result["email"],
                        "confidence": hunter_result["confidence"],
                        "position": hunter_result.get("position"),
                    }

        return {
            "enriched": False,
            "reason": "no_match",
            "sources_attempted": ["apollo", "hunter"],
            **enrichment_meta,
        }

    def _apply_enrichment(self, lead: LeadRecord, person: dict, source: str) -> dict:
        """Apply Apollo person data to lead record."""
        enriched_fields = []
        if not lead.email and person.get("email"):
            lead.email = person["email"]
            enriched_fields.append("email")
        if not lead.phone and person.get("phone"):
            lead.phone = person["phone"]
            enriched_fields.append("phone")
        if not lead.name and person.get("name"):
            lead.name = person["name"]
            enriched_fields.append("name")

        return {
            "enriched": True,
            "fields": enriched_fields,
            "source": source,
            "apollo_id": person.get("apollo_id"),
            "title": person.get("title"),
            "company": (person.get("company") or {}).get("name"),
        }

    async def prepare_lead(self, lead_in: LeadIn) -> tuple[LeadRecord, ApprovalRequest, AgentRunRecord]:
        lead = LeadRecord(**lead_in.model_dump())

        enrichment = await self._maybe_enrich_lead(lead)

        qualification = await qualify_lead(lead, self.profile)
        score = qualification["score"]
        reasoning = qualification["justification"]
        lead.qualification_score = score
        lead.qualification_reasoning = reasoning

        email = await draft_email(lead, self.profile)
        slots = suggest_meeting_slots()
        preview = {
            "lead": {
                "name": lead.name,
                "email": lead.email,
                "phone": lead.phone,
                "source": lead.source,
                "estimated_ticket_usd": lead.estimated_ticket_usd,
                "qualification_score": score,
                "qualification_reasoning": reasoning,
            },
            "email": email,
            "meeting_slots": slots,
            "dry_run": self.settings.dry_run,
            "profit_signal": "conversion",
            "enrichment": enrichment,
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
        log.info(
            "sdr_lead_prepared",
            business=lead.business,
            score=score,
            action=qualification.get("recommended_action"),
            prompt_version=self.settings.prompt_version,
        )
        return lead, approval, run
