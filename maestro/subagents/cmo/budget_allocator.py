from datetime import UTC, datetime


def recommend_budget_actions(
    monthly_budget_usd: int,
    approval_threshold_usd: int = 500,
    *,
    spend_usd_last_30d: float = 0.0,
    performance_signal: str = "no_data",
) -> dict:
    shift = min(500, max(0, int(monthly_budget_usd * 0.1)))
    expected_spend = monthly_budget_usd * _month_progress()
    pacing_ratio = (spend_usd_last_30d / expected_spend) if expected_spend else 0
    pacing = "on_track"
    if spend_usd_last_30d and pacing_ratio < 0.75:
        pacing = "underspent"
    elif expected_spend and pacing_ratio > 1.25:
        pacing = "overspent"

    if performance_signal == "degrading":
        recommendation = "pause_or_reallocate"
        reason = "Performance signal is degrading; avoid increasing spend until creative or targeting changes."
    elif performance_signal in {"improving", "flat"} and shift:
        recommendation = "prepare_test_budget_shift"
        reason = "Real performance is usable; prepare a controlled test budget shift."
    else:
        recommendation = "hold_until_real_ads_data" if shift == 0 else "prepare_test_budget_shift"
        reason = "No reliable ads data yet; keep changes test-sized until source metrics are connected."

    return {
        "recommendation": recommendation,
        "proposed_shift_usd": shift,
        "requires_approval": shift > approval_threshold_usd,
        "budget_pacing": pacing,
        "expected_spend_to_date_usd": round(expected_spend, 2),
        "actual_spend_usd_last_30d": round(spend_usd_last_30d, 2),
        "reason": reason,
    }


def _month_progress() -> float:
    now = datetime.now(UTC)
    return max(0.1, min(1.0, now.day / 30))
