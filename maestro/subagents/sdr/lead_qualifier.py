"""
Lead Qualifier — score + justification for incoming leads.

Primary: Claude Sonnet 4.6 with full business profile context.
Fallback: deterministic rule engine when LLM unavailable (dev/test).

Output: {score: int, justification: str, recommended_action: str}
"""

import json
import re

import structlog

from maestro.profiles._schema import BusinessProfile
from maestro.schemas.events import LeadRecord

log = structlog.get_logger()


def _build_system_prompt(profile: BusinessProfile) -> str:
    offerings = "\n".join(
        f"  - {o.name}: avg ${o.ticket_avg_usd}, min ${o.ticket_min_usd}" for o in profile.offerings
    )
    rules = "\n".join(f"  - {r}" for r in profile.qualification_criteria.custom_rules) or "  (none)"
    return f"""\
You are the lead qualifier for {profile.business_name}, a {profile.business_type}.

Score the lead from 0–100 and return ONLY a JSON object — no prose, no markdown.

Business context:
  Service area: {profile.service_area}
  Min ticket: ${profile.qualification_criteria.min_ticket_usd}
  Ready within: {profile.qualification_criteria.ready_within_months_max} months max
  Offerings:
{offerings}
  Custom rules:
{rules}

Schema:
{{
  "score": <int 0-100>,
  "justification": "<max 2 sentences in English>",
  "recommended_action": "request_approval" | "manual_review" | "disqualify"
}}

Scoring guide:
- Has contact info (email or phone): +15
- Ticket meets min threshold: +20
- High-intent wording (urgent, asap, quote, estimate, soon): +10
- In service area: +15
- Timeline within window: +10
- No contact info: -20
- Ticket clearly below minimum: -15
- Score ≥ 70 → request_approval
- Score 40–69 → manual_review
- Score < 40 → disqualify
"""


def _keyword_fallback(lead: LeadRecord, profile: BusinessProfile) -> dict:
    score = 50
    reasons: list[str] = []

    if lead.email or lead.phone:
        score += 15
        reasons.append("has reachable contact")
    else:
        score -= 20
        reasons.append("missing direct contact")

    if lead.estimated_ticket_usd:
        if lead.estimated_ticket_usd >= profile.qualification_criteria.min_ticket_usd:
            score += 20
            reasons.append("ticket meets threshold")
        else:
            score -= 10
            reasons.append("ticket below threshold")

    if lead.message:
        lowered = lead.message.lower()
        if any(word in lowered for word in ["urgent", "asap", "soon", "estimate", "quote"]):
            score += 10
            reasons.append("high-intent wording")

    score = max(0, min(100, score))

    if score >= 70:
        action = "request_approval"
    elif score >= 40:
        action = "manual_review"
    else:
        action = "disqualify"

    return {
        "score": score,
        "justification": "; ".join(reasons) or "basic lead received",
        "recommended_action": action,
    }


def _parse_llm_response(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("no JSON in LLM response")
    return json.loads(match.group())


async def qualify_lead(lead: LeadRecord, profile: BusinessProfile) -> dict:
    """
    Qualify a lead using Claude Sonnet 4.6.
    Falls back to rule engine if LLM unavailable.
    """
    from maestro.config import get_settings
    settings = get_settings()

    if not settings.anthropic_api_key:
        log.info("lead_qualifier_fallback", reason="no_api_key", lead_id=str(lead.id))
        return _keyword_fallback(lead, profile)

    try:
        from maestro.utils.llm import SONNET, UnknownModelPricingError, call_claude

        user_content = (
            f"Lead name: {lead.name or 'unknown'}\n"
            f"Email: {lead.email or 'none'}\n"
            f"Phone: {lead.phone or 'none'}\n"
            f"Source: {lead.source}\n"
            f"Estimated ticket: ${lead.estimated_ticket_usd or 'unknown'}\n"
            f"Message: {lead.message or '(no message)'}"
        )

        raw = await call_claude(
            _build_system_prompt(profile),
            user_content,
            settings=settings,
            model=SONNET,
            max_tokens=256,
        )
        result = _parse_llm_response(raw)

        log.info(
            "lead_qualified",
            lead_id=str(lead.id),
            score=result.get("score"),
            action=result.get("recommended_action"),
            business=profile.business_id,
        )
        return result

    except UnknownModelPricingError:
        raise
    except Exception as exc:
        log.warning("lead_qualifier_llm_failed", error=str(exc), fallback="rules")
        return _keyword_fallback(lead, profile)
