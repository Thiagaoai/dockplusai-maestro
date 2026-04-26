"""CFO subagent: recommend financial actions that may require HITL approval."""

from maestro.profiles._schema import BusinessProfile


def recommend_financial_actions(
    profile: BusinessProfile,
    margin: dict,
    cashflow: dict,
    reconciliation: dict,
) -> dict:
    """Analyze financial data and recommend actions.

    Returns actions with estimated impact. If any action exceeds the
    business's approval threshold, flags requires_approval.
    """
    threshold = profile.decision_thresholds.thiago_approval_above_usd
    actions = []

    margin_pct = margin.get("estimated_gross_margin_pct", 0)
    if margin_pct < 30:
        estimated_savings = profile.offerings[0].ticket_avg_usd * 0.05 if profile.offerings else 500
        actions.append({
            "title": "Review pricing and cost structure",
            "reason": f"Estimated gross margin ({margin_pct}%) is below healthy threshold (30%)",
            "recommended_action": "Analyze top cost drivers and consider selective price adjustments",
            "estimated_impact_usd": round(estimated_savings, 2),
            "category": "margin_protection",
        })
    elif margin_pct >= 42 and cashflow.get("cashflow_signal") in {"green", "yellow"}:
        actions.append({
            "title": "Protect margin while funding controlled growth",
            "reason": f"Gross margin signal is {margin.get('margin_signal')} at {margin_pct}%.",
            "recommended_action": "Keep pricing discipline and allow only small approved growth tests.",
            "estimated_impact_usd": min(
                profile.decision_thresholds.thiago_approval_above_usd,
                max(250, margin.get("estimated_gross_margin_usd", 0) * 0.03),
            ),
            "category": "growth_control",
        })

    # Action 2: Cashflow investment
    if cashflow.get("forecast_30d_shortfall_usd", 0) > 0:
        shortfall = cashflow["forecast_30d_shortfall_usd"]
        actions.append({
            "title": "Address 30-day cashflow shortfall",
            "reason": f"Projected shortfall of ${shortfall:,.2f} in next 30 days",
            "recommended_action": "Accelerate receivables or defer discretionary spend",
            "estimated_impact_usd": shortfall,
            "category": "cashflow_management",
        })

    open_pipeline = reconciliation.get("open_pipeline_value_usd", 0)
    if open_pipeline > 0:
        actions.append({
            "title": "Convert open pipeline into booked revenue",
            "reason": f"Open pipeline shows ${open_pipeline:,.2f} that can move cashflow if followed up this week.",
            "recommended_action": "Prioritize follow-up on late-stage opportunities before adding more spend.",
            "estimated_impact_usd": round(open_pipeline * 0.1, 2),
            "category": "revenue_conversion",
        })

    # Action 3: Reconciliation discrepancies
    discrepancies = reconciliation.get("discrepancies", [])
    total_discrepancy = sum(d.get("amount_usd", 0) for d in discrepancies)
    if total_discrepancy > 100:
        actions.append({
            "title": "Resolve invoice reconciliation discrepancies",
            "reason": f"Found ${total_discrepancy:,.2f} in unmatched charges",
            "recommended_action": "Review unmatched Stripe charges vs GHL opportunities",
            "estimated_impact_usd": total_discrepancy,
            "category": "reconciliation",
        })

    # Determine if approval is required
    actions = sorted(actions, key=lambda action: action["estimated_impact_usd"], reverse=True)[:3]
    max_impact = max((a["estimated_impact_usd"] for a in actions), default=0)
    requires_approval = max_impact > threshold

    return {
        "actions": actions,
        "requires_approval": requires_approval,
        "max_impact_usd": max_impact,
        "threshold_usd": threshold,
    }
