"""CEO subagent: prepare strategic decisions that may require HITL approval."""

from maestro.profiles._schema import BusinessProfile


def prepare_decisions(
    profile: BusinessProfile,
    *,
    cfo_data: dict | None = None,
    cmo_data: dict | None = None,
) -> list[dict]:
    """Generate strategic decisions with estimated financial impact.

    Decisions with impact above the business's approval threshold
    will trigger HITL in the CEO agent.
    """
    avg_ticket = profile.offerings[0].ticket_avg_usd if profile.offerings else 0
    cfo_data = cfo_data or {}
    cmo_data = cmo_data or {}
    margin_signal = cfo_data.get("margin", {}).get("margin_signal", "unknown")
    performance_signal = cmo_data.get("performance", {}).get("performance_signal", "no_data")
    open_pipeline = cfo_data.get("reconciliation", {}).get("open_pipeline_value_usd", 0) or 0

    decisions = [
        {
            "title": "Approve next growth test",
            "options": ["Approve controlled dry-run", "Wait for more data"],
            "recommendation": _growth_recommendation(margin_signal, performance_signal),
            "reason": _growth_reason(profile.business_name, margin_signal, performance_signal),
            "estimated_impact_usd": round(avg_ticket * (0.08 if performance_signal == "improving" else 0.05), 2),
            "strategic_priority": "high",
        },
        {
            "title": "Tighten response speed",
            "options": ["Keep SDR first", "Shift focus to reporting"],
            "recommendation": "Keep SDR first",
            "reason": "Lead response has direct revenue impact.",
            "estimated_impact_usd": round(open_pipeline * 0.05, 2) if open_pipeline else 0,
            "strategic_priority": "medium",
        },
        {
            "title": "Expand service area or double down",
            "options": ["Expand to adjacent towns", "Focus on current area"],
            "recommendation": "Focus on current area",
            "reason": f"Current service area for {profile.business_name} has untapped demand.",
            "estimated_impact_usd": round(avg_ticket * 0.15, 2),
            "strategic_priority": "medium",
        },
    ]
    return sorted(decisions, key=lambda item: item["estimated_impact_usd"], reverse=True)


def _growth_recommendation(margin_signal: str, performance_signal: str) -> str:
    if margin_signal == "critical":
        return "Wait for more data"
    if performance_signal == "degrading":
        return "Approve controlled dry-run"
    return "Approve controlled dry-run"


def _growth_reason(business_name: str, margin_signal: str, performance_signal: str) -> str:
    if margin_signal == "critical":
        return f"{business_name} should protect cash and margin before adding spend."
    if performance_signal == "degrading":
        return "Growth needs a creative or channel correction before spend increases."
    return f"{business_name} needs compounding growth tests with audit trail."
