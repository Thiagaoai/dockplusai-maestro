"""
CEO Weekly Briefing — synthesizes CFO + CMO data into executive briefing + decisions.

Primary: Claude Opus 4.7 using ceo_weekly_briefing prompt template.
Fallback: deterministic summary when LLM unavailable (dev/test).

Output always in Portuguese (Thiago reads on his phone).
"""

import json
import re

import structlog

log = structlog.get_logger()


def create_weekly_briefing(business_name: str, cfo_data: dict, cmo_data: dict) -> str:
    """Sync string fallback — used in tests and when API key is absent."""
    margin = cfo_data.get("margin", {}).get("estimated_gross_margin_pct", "unknown")
    creative_count = len(cmo_data.get("creative_tests", []))
    return (
        f"*{business_name}* — briefing semanal:\n"
        f"- Sinal financeiro: margem bruta estimada *{margin}%*.\n"
        f"- Sinal de marketing: {creative_count} testes criativos prontos.\n"
        "- Prioridade: converter mais rápido, publicar com consistência e proteger margem."
    )


def _parse_json(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("no JSON in LLM response")
    return json.loads(match.group())


async def create_briefing_with_decisions(profile, cfo_data: dict, cmo_data: dict, settings) -> dict:
    """
    Generate executive briefing + strategic decisions via Claude Opus 4.7.
    Falls back to sync summary + prepare_decisions on failure or missing API key.
    Returns dict with: briefing (str), decisions (list).
    """
    from maestro.subagents.ceo.decision_preparer import prepare_decisions

    fallback = {
        "briefing": create_weekly_briefing(profile.business_name, cfo_data, cmo_data),
        "decisions": prepare_decisions(profile, cfo_data=cfo_data, cmo_data=cmo_data),
        "week_priority": "Converter leads, publicar e proteger margem.",
    }

    if not settings.anthropic_api_key:
        return fallback

    try:
        from maestro.utils.llm import OPUS, UnknownModelPricingError, call_claude
        from maestro.utils.prompts import load_prompt

        context = {
            "business_name": profile.business_name,
            "business_type": profile.business_type,
            "service_area": profile.service_area,
            "offerings": profile.offerings,
            "decision_thresholds": profile.decision_thresholds,
            "cfo_data": cfo_data,
            "cmo_data": cmo_data,
        }
        prompt = load_prompt("ceo_weekly_briefing", context)

        raw = await call_claude(
            system="You are the CEO agent. Follow the output format exactly. Return only valid JSON.",
            user=prompt,
            settings=settings,
            model=OPUS,
            max_tokens=1024,
        )
        result = _parse_json(raw)

        decisions = result.get("decisions", fallback["decisions"])
        if not decisions:
            decisions = fallback["decisions"]

        log.info(
            "ceo_briefing_generated",
            business=profile.business_id,
            decisions_count=len(decisions),
        )
        return {
            "briefing": result.get("briefing", fallback["briefing"]),
            "decisions": decisions,
            "week_priority": result.get("week_priority", ""),
        }

    except UnknownModelPricingError:
        raise
    except Exception as exc:
        log.warning("ceo_briefing_llm_failed", error=str(exc), fallback="sync")
        return fallback
