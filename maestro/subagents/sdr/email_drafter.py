"""
Email Drafter — generates the first outbound email for a qualified lead.

Primary: Claude Sonnet 4.6 with tone profile + lead context.
Fallback: template-based when LLM unavailable (dev/test).

Output always in English regardless of input language.
"""

import json
import re

import structlog

from maestro.profiles._schema import BusinessProfile
from maestro.schemas.events import LeadRecord

log = structlog.get_logger()


def _build_system_prompt(profile: BusinessProfile) -> str:
    tone = profile.tone
    offerings_str = ", ".join(o.name for o in profile.offerings[:3]) if profile.offerings else "our services"
    do_rules = "\n".join(f"  - DO: {d}" for d in tone.do) or "  (none)"
    dont_rules = "\n".join(f"  - DON'T: {d}" for d in tone.do_not) or "  (none)"
    samples = "\n\n".join(tone.sample_emails[:1]) if tone.sample_emails else "(no samples)"

    return f"""\
You are writing the first outbound email for {profile.business_name}, a {profile.business_type}.

ALWAYS write in English. NEVER write in Portuguese or any other language.

Tone profile:
  Voice: {tone.voice}
  Formality: {tone.formality}/5
{do_rules}
{dont_rules}
  Signature: {tone.signature}

Offerings available: {offerings_str}

Sample email style (match this):
{samples}

Return ONLY a JSON object — no prose, no markdown:
{{
  "subject": "<email subject line, max 60 chars>",
  "body": "<full email body, plain text, max 200 words>"
}}

Rules:
- Address the lead by first name
- Reference their specific request or message if available
- Mention 1 relevant offering that fits their need
- End with a clear CTA (suggest a call or reply)
- Use the exact signature from the tone profile
- Never include pricing in the first email
- Never use generic openers like "I hope this email finds you well"
"""


def _template_fallback(lead: LeadRecord, profile: BusinessProfile) -> dict[str, str]:
    first_name = (lead.name or "there").split(" ")[0]
    top_offering = profile.offerings[0].name if profile.offerings else "your project"
    subject = f"Thanks for reaching out about {top_offering}"
    body = (
        f"Hi {first_name},\n\n"
        f"Thanks for reaching out to {profile.business_name}. "
        "We received your request and would love to help.\n\n"
        "I'd like to learn a bit more about what you're looking for. "
        "Could we schedule a quick 15-minute call this week?\n\n"
        f"{profile.tone.signature}"
    )
    return {"subject": subject, "body": body}


def _parse_llm_response(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("no JSON in LLM response")
    return json.loads(match.group())


async def draft_email(lead: LeadRecord, profile: BusinessProfile) -> dict[str, str]:
    """
    Draft a personalized outbound email using Claude Sonnet 4.6.
    Falls back to template if LLM unavailable.
    Returns {"subject": str, "body": str}.
    """
    from maestro.config import get_settings
    settings = get_settings()

    if not settings.anthropic_api_key:
        log.info("email_drafter_fallback", reason="no_api_key", lead_id=str(lead.id))
        return _template_fallback(lead, profile)

    try:
        from maestro.utils.llm import SONNET, UnknownModelPricingError, call_claude

        user_content = (
            f"Lead name: {lead.name or 'unknown'}\n"
            f"Their message: {lead.message or '(no message provided)'}\n"
            f"Source: {lead.source}\n"
            f"Estimated project: ${lead.estimated_ticket_usd or 'unknown'}"
        )

        raw = await call_claude(
            _build_system_prompt(profile),
            user_content,
            settings=settings,
            model=SONNET,
            max_tokens=512,
        )
        result = _parse_llm_response(raw)

        log.info(
            "email_drafted",
            lead_id=str(lead.id),
            subject=result.get("subject", "")[:40],
            business=profile.business_id,
        )
        return result

    except UnknownModelPricingError:
        raise
    except Exception as exc:
        log.warning("email_drafter_llm_failed", error=str(exc), fallback="template")
        return _template_fallback(lead, profile)
