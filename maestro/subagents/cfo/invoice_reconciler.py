def reconcile_invoices(
    business: str,
    *,
    stripe_summary: dict | None = None,
    pipeline_summary: dict | None = None,
) -> dict:
    stripe_summary = stripe_summary or {}
    pipeline_summary = pipeline_summary or {}
    discrepancies = []

    refunded = float(stripe_summary.get("refunded_usd") or 0.0)
    if refunded > 0:
        discrepancies.append(
            {
                "kind": "refunds_detected",
                "amount_usd": round(refunded, 2),
                "reason": "Stripe shows refunded charges in the recent period.",
            }
        )

    won_value = float(pipeline_summary.get("won_value_usd") or 0.0)
    stripe_revenue = float(stripe_summary.get("gross_revenue_usd") or 0.0)
    if won_value and stripe_revenue and abs(won_value - stripe_revenue) > 500:
        discrepancies.append(
            {
                "kind": "stripe_vs_ghl_gap",
                "amount_usd": round(abs(won_value - stripe_revenue), 2),
                "reason": "GHL won pipeline value does not match Stripe gross revenue.",
            }
        )

    sources = ["dry_run:stripe", "dry_run:ghl"]
    if stripe_summary.get("sources"):
        sources = list(stripe_summary["sources"])
    if pipeline_summary.get("status") == "ok" and pipeline_summary.get("sources"):
        sources.extend(source for source in pipeline_summary["sources"] if source not in sources)

    return {
        "business": business,
        "stripe_charges_checked": int(stripe_summary.get("charges_checked") or 0),
        "ghl_won_checked": int(pipeline_summary.get("won_count") or 0),
        "stripe_gross_revenue_usd": round(stripe_revenue, 2),
        "ghl_won_value_usd": round(won_value, 2),
        "open_pipeline_value_usd": round(float(pipeline_summary.get("open_value_usd") or 0.0), 2),
        "discrepancies": discrepancies,
        "sources": sources,
    }
