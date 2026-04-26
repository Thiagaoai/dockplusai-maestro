from maestro.profiles._schema import BusinessProfile


def analyze_ad_performance(profile: BusinessProfile, real_performance: dict | None = None) -> dict:
    real_performance = real_performance or {}
    spend = float(real_performance.get("real_spend_usd_last_30d") or 0.0)
    clicks = int(real_performance.get("real_clicks_last_30d") or 0)
    impressions = int(real_performance.get("real_impressions_last_30d") or 0)
    ctr = round((clicks / impressions) * 100, 2) if impressions else 0.0
    cpc = round(spend / clicks, 2) if clicks else 0.0
    sources = real_performance.get("sources") or ["profile.ads", "dry_run"]
    has_real_data = bool(real_performance.get("sources"))

    return {
        "monthly_budget_usd": profile.ads.monthly_budget_usd,
        "spend_usd_last_30d": round(spend, 2),
        "clicks_last_30d": clicks,
        "impressions_last_30d": impressions,
        "ctr_pct": ctr,
        "cpc_usd": cpc,
        "performance_signal": _performance_signal(spend, clicks, impressions, has_real_data),
        "cpl_trend": "available_from_real_sources" if has_real_data else "unknown_dry_run",
        "roas_trend": "available_from_real_sources" if has_real_data else "unknown_dry_run",
        "alerts": real_performance.get("alerts") or ["Connect Meta/Google Ads APIs for real spend and ROAS."],
        "sources": sources,
    }


def _performance_signal(spend: float, clicks: int, impressions: int, has_real_data: bool) -> str:
    if not has_real_data:
        return "no_data"
    if spend > 0 and clicks == 0:
        return "degrading"
    ctr = (clicks / impressions) * 100 if impressions else 0
    if ctr >= 2.0:
        return "improving"
    if ctr >= 0.8:
        return "flat"
    return "degrading"
