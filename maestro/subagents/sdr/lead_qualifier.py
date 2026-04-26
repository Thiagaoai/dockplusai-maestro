from maestro.profiles._schema import BusinessProfile
from maestro.schemas.events import LeadRecord


def qualify_lead(lead: LeadRecord, profile: BusinessProfile) -> dict:
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
    return {
        "score": score,
        "justification": "; ".join(reasons) or "basic lead received",
        "recommended_action": "request_approval" if score >= 50 else "manual_review",
    }
