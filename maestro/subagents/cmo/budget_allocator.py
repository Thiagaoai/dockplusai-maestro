def recommend_budget_actions(monthly_budget_usd: int) -> dict:
    shift = min(500, max(0, int(monthly_budget_usd * 0.1)))
    return {
        "recommendation": "hold_until_real_ads_data" if shift == 0 else "prepare_test_budget_shift",
        "proposed_shift_usd": shift,
        "requires_approval": shift > 0,
        "reason": "Dry-run recommends only test-sized changes until ads APIs are connected.",
    }
