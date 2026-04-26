def forecast_cashflow(estimated_revenue_usd: float) -> dict:
    realistic_30d = round(estimated_revenue_usd, 2)
    pessimistic_30d = round(estimated_revenue_usd * 0.5, 2)
    optimistic_30d = round(estimated_revenue_usd * 1.5, 2)
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
        "sources": ["dry_run forecast from profile average ticket"],
    }
