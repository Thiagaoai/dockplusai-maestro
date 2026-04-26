"""CEO subagent: prepare strategic decisions that may require HITL approval."""

from maestro.profiles._schema import BusinessProfile


def prepare_decisions(profile: BusinessProfile) -> list[dict]:
    """Generate strategic decisions with estimated financial impact.

    Decisions with impact above the business's approval threshold
    will trigger HITL in the CEO agent.
    """
    avg_ticket = profile.offerings[0].ticket_avg_usd if profile.offerings else 0

    return [
        {
            "title": "Approve next growth test",
            "options": ["Approve controlled dry-run", "Wait for more data"],
            "recommendation": "Approve controlled dry-run",
            "reason": f"{profile.business_name} needs compounding growth tests with audit trail.",
            "estimated_impact_usd": round(avg_ticket * 0.05, 2),
            "strategic_priority": "high",
        },
        {
            "title": "Tighten response speed",
            "options": ["Keep SDR first", "Shift focus to reporting"],
            "recommendation": "Keep SDR first",
            "reason": "Lead response has direct revenue impact.",
            "estimated_impact_usd": 0,
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
