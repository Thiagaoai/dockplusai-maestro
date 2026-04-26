def forecast_cashflow(estimated_revenue_usd: float) -> dict:
    return {
        "30_days": {
            "pessimistic_usd": round(estimated_revenue_usd * 0.5, 2),
            "realistic_usd": round(estimated_revenue_usd, 2),
            "optimistic_usd": round(estimated_revenue_usd * 1.5, 2),
        },
        "60_days": {
            "pessimistic_usd": round(estimated_revenue_usd, 2),
            "realistic_usd": round(estimated_revenue_usd * 2, 2),
            "optimistic_usd": round(estimated_revenue_usd * 3, 2),
        },
        "sources": ["dry_run forecast from profile average ticket"],
    }
