from maestro.profiles._schema import BusinessProfile


def analyze_margin(profile: BusinessProfile) -> dict:
    avg_ticket = profile.offerings[0].ticket_avg_usd if profile.offerings else 0
    estimated_direct_cost = avg_ticket * 0.58
    margin = avg_ticket - estimated_direct_cost
    margin_pct = round((margin / avg_ticket) * 100, 1) if avg_ticket else 0
    return {
        "estimated_revenue_usd": avg_ticket,
        "estimated_direct_cost_usd": round(estimated_direct_cost, 2),
        "estimated_gross_margin_usd": round(margin, 2),
        "estimated_gross_margin_pct": margin_pct,
        "sources": ["profile.offerings.ticket_avg_usd", "dry_run cost assumption 58%"],
    }
