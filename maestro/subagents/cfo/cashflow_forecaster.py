def forecast_cashflow(
    estimated_revenue_usd: float,
    *,
    pipeline_value_usd: float = 0.0,
    collected_revenue_usd: float = 0.0,
) -> dict:
    weighted_pipeline = pipeline_value_usd * 0.25
    base = max(estimated_revenue_usd, collected_revenue_usd + weighted_pipeline)
    realistic_30d = round(base, 2)
    pessimistic_30d = round(base * 0.5, 2)
    optimistic_30d = round(base * 1.5, 2)
    shortfall = round(realistic_30d - pessimistic_30d, 2)

    return {
        "30_days": {
            "pessimistic_usd": pessimistic_30d,
            "realistic_usd": realistic_30d,
            "optimistic_usd": optimistic_30d,
        },
        "60_days": {
            "pessimistic_usd": round(estimated_revenue_usd, 2),
            "realistic_usd": round(estimated_revenue_usd * 2, 2),
            "optimistic_usd": round(estimated_revenue_usd * 3, 2),
        },
        "forecast_30d_shortfall_usd": shortfall,
        "pipeline_value_usd": round(pipeline_value_usd, 2),
        "weighted_pipeline_usd": round(weighted_pipeline, 2),
        "collected_revenue_usd": round(collected_revenue_usd, 2),
        "cashflow_signal": _cashflow_signal(shortfall),
        "sources": ["profile average ticket", "stripe collected revenue", "ghl weighted pipeline"],
    }


def _cashflow_signal(shortfall: float) -> str:
    if shortfall > 20_000:
        return "red"
    if shortfall >= 5_000:
        return "yellow"
    return "green"
