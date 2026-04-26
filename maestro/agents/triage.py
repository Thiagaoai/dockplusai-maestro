"""
Triage Agent — classifica toda mensagem em <500ms.

Fase 1: usa Claude Haiku 4.5 com prompt determinístico.
Fallback: keyword matching quando ANTHROPIC_API_KEY não está configurada (dev/test).

Output: {business, function, intent, confidence, target_agent}
"""

import json
import re
from typing import Any

import structlog
from pydantic import BaseModel, Field, field_validator

log = structlog.get_logger()

ALLOWED_BUSINESSES = {"roberts", "dockplusai"}
ALLOWED_FUNCTIONS = {"sales", "marketing", "finance", "operations", "strategy"}
ALLOWED_TARGET_AGENTS = {"sdr", "marketing", "cfo", "cmo", "ceo", "operations"}

_SYSTEM_PROMPT = """\
You are the triage router for MAESTRO, a multi-agent business automation system.

Classify the user message and return ONLY a JSON object — no prose, no markdown.

Schema:
{
  "business": "roberts" | "dockplusai" | "<last_active>",
  "function": "sales" | "marketing" | "finance" | "operations",
  "intent": "<concise phrase in English, max 10 words>",
  "confidence": <float 0.0–1.0>,
  "target_agent": "sdr" | "marketing" | "cfo" | "cmo" | "ceo" | "operations"
}

Routing rules:
- Lead, quote, prospect, schedule meeting, follow-up → target_agent: sdr
- Post, Instagram, content, caption, image, hashtag → target_agent: marketing
- Revenue, margin, cashflow, invoice, Stripe, finance → target_agent: cfo
- Ads, ROAS, Meta, Google Ads, budget, campaign → target_agent: cmo
- Weekly briefing, strategy, summary, overview → target_agent: ceo
- Prospecting/outbound campaigns/lists → target_agent: sdr
- Everything else or unclear requests → target_agent: operations

If confidence < 0.7, set target_agent: "operations" and intent: "need more context".
If the message mentions "dockplus" or "dockplusai", set business: "dockplusai".
Otherwise inherit business from context (last_active).
"""

_FALLBACK_KEYWORDS = {
    "sdr": ["lead", "quote", "estimate", "prospect", "schedule", "follow-up", "client"],
    "marketing": ["post", "instagram", "caption", "image", "hashtag", "content", "creative"],
    "cfo": ["margin", "revenue", "cashflow", "invoice", "stripe", "finance", "money"],
    "cmo": ["ads", "roas", "meta", "google ads", "budget", "campaign", "cpc"],
    "ceo": ["briefing", "strategy", "summary", "overview", "week", "decisions"],
}


class TriageResult(BaseModel):
    business: str
    function: str
    intent: str = Field(min_length=1, max_length=120)
    confidence: float = Field(ge=0.0, le=1.0)
    target_agent: str

    @field_validator("business")
    @classmethod
    def validate_business(cls, value: str) -> str:
        value = value.strip().casefold()
        if value not in ALLOWED_BUSINESSES:
            raise ValueError("invalid business")
        return value

    @field_validator("function")
    @classmethod
    def validate_function(cls, value: str) -> str:
        value = value.strip().casefold()
        aliases = {
            "marketing_performance": "marketing",
            "growth": "marketing",
            "executive": "strategy",
        }
        value = aliases.get(value, value)
        if value not in ALLOWED_FUNCTIONS:
            raise ValueError("invalid function")
        return value

    @field_validator("target_agent")
    @classmethod
    def validate_target_agent(cls, value: str) -> str:
        value = value.strip().casefold()
        aliases = {
            "prospecting": "sdr",
            "prospecting_agent": "sdr",
            "sdr_agent": "sdr",
            "marketing_agent": "marketing",
            "cfo_agent": "cfo",
            "cmo_agent": "cmo",
            "ceo_agent": "ceo",
            "operations_agent": "operations",
            "clarify": "operations",
        }
        value = aliases.get(value, value)
        if value not in ALLOWED_TARGET_AGENTS:
            raise ValueError("invalid target_agent")
        return value


def _keyword_fallback(text: str, last_business: str = "roberts") -> dict:
    """Deterministic fallback when LLM is unavailable."""
    lowered = text.lower()
    target = "operations"
    for agent, keywords in _FALLBACK_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            target = agent
            break
    business = "dockplusai" if "dockplus" in lowered else last_business
    function_map = {
        "sdr": "sales",
        "marketing": "marketing",
        "cfo": "finance",
        "cmo": "marketing",
        "ceo": "strategy",
        "operations": "operations",
    }
    return {
        "business": business,
        "function": function_map.get(target, "operations"),
        "intent": lowered[:80],
        "confidence": 0.6,
        "target_agent": target,
    }


def _parse_llm_response(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("no JSON found in LLM response")
    return json.loads(match.group())


def _response_text(response: Any) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", []):
        text = getattr(block, "text", None)
        if text:
            parts.append(str(text))
    return "\n".join(parts).strip()


def _normalize_result(raw_result: dict[str, Any], last_business: str) -> dict:
    raw_result = dict(raw_result)
    if raw_result.get("business") == "<last_active>":
        raw_result["business"] = last_business
    result = TriageResult.model_validate(raw_result)
    return result.model_dump()


async def triage_message(
    text: str,
    last_business: str = "roberts",
    anthropic_client: Any | None = None,
) -> dict:
    """
    Classify an incoming Telegram message.

    Returns dict with business, function, intent, confidence, target_agent.
    Falls back to keyword matching if LLM is unavailable.
    """
    from maestro.config import get_settings
    settings = get_settings()

    if not settings.anthropic_api_key:
        log.info("triage_keyword_fallback", reason="no_api_key")
        return _keyword_fallback(text, last_business)

    try:
        if anthropic_client is None:
            from anthropic import AsyncAnthropic

            anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

        context = f"[last_active_business: {last_business}]\n\nUser message: {text}"

        response = await anthropic_client.messages.create(
            model=settings.anthropic_triage_model,
            max_tokens=256,
            temperature=0,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context}],
        )
        result = _normalize_result(_parse_llm_response(_response_text(response)), last_business)

        log.info(
            "triage_classified",
            business=result.get("business"),
            target=result.get("target_agent"),
            confidence=result.get("confidence"),
        )
        return result

    except Exception as exc:
        log.warning("triage_llm_failed", error=str(exc), fallback="keyword")
        return _keyword_fallback(text, last_business)
