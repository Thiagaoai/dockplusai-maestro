from maestro.profiles._schema import BusinessProfile


def choose_hashtags(profile: BusinessProfile) -> list[str]:
    strategy = profile.marketing.hashtag_strategy
    local = strategy.get("local", [])[:4]
    niche = strategy.get("niche", [])[:4]
    general = ["#SmallBusiness", "#Growth", "#QualityWork", "#Business"]
    return (local + niche + general)[:12]
