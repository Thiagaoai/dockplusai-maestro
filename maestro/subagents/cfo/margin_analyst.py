from maestro.profiles._schema import BusinessProfile


def analyze_margin(
    profile: BusinessProfile,
    *,
    revenue_usd: float | None = None,
    direct_cost_ratio: float | None = None,
) -> dict:
    """Estimate margin from real revenue when available, otherwise profile ticket data."""
    avg_ticket = profile.offerings[0].ticket_avg_usd if profile.offerings else 0
    base_revenue = float(revenue_usd if revenue_usd is not None and revenue_usd > 0 else avg_ticket)
    ratio = direct_cost_ratio if direct_cost_ratio is not None else _default_direct_cost_ratio(profile)
    estimated_direct_cost = base_revenue * ratio
    margin = base_revenue - estimated_direct_cost
    margin_pct = round((margin / base_revenue) * 100, 1) if base_revenue else 0
    source = "stripe.gross_revenue_usd" if revenue_usd is not None and revenue_usd > 0 else "profile.offerings.ticket_avg_usd"
    return {
        "estimated_revenue_usd": round(base_revenue, 2),
        "estimated_direct_cost_usd": round(estimated_direct_cost, 2),
        "estimated_gross_margin_usd": round(margin, 2),
        "estimated_gross_margin_pct": margin_pct,
        "direct_cost_ratio": ratio,
        "margin_signal": _margin_signal(margin_pct),
        "sources": [source, f"cost assumption {int(ratio * 100)}%"],
    }


def _default_direct_cost_ratio(profile: BusinessProfile) -> float:
    if profile.business_type.upper() == "B2B":
        return 0.35
    return 0.58


def _margin_signal(margin_pct: float) -> str:
    if margin_pct < 30:
        return "critical"
    if margin_pct < 42:
        return "watch"
    return "healthy"
