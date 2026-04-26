from maestro.profiles._schema import BusinessProfile


def analyze_ad_performance(profile: BusinessProfile) -> dict:
    return {
        "monthly_budget_usd": profile.ads.monthly_budget_usd,
        "cpl_trend": "unknown_dry_run",
        "roas_trend": "unknown_dry_run",
        "alerts": ["Connect Meta/Google Ads APIs for real spend and ROAS."],
        "sources": ["profile.ads", "dry_run"],
    }
