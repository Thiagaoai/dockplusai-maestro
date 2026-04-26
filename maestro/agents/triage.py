"""
Triage Agent — classifica toda mensagem em <500ms.

Fase 1: usa Claude Haiku 4.5 com prompt determinístico.
Fallback: keyword matching quando ANTHROPIC_API_KEY não está configurada (dev/test).

Output: {business, function, intent, confidence, target_agent}
"""

import json
import re

import structlog

log = structlog.get_logger()

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
- Everything else → target_agent: operations

If confidence < 0.7, set target_agent: "clarify" and intent: "need more context".
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
        "cmo": "marketing_performance",
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


async def triage_message(text: str, last_business: str = "roberts") -> dict:
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
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)

        context = f"[last_active_business: {last_business}]\n\nUser message: {text}"

        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context}],
        )
        raw = response.content[0].text
        result = _parse_llm_response(raw)

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
