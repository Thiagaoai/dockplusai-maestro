from datetime import datetime, timedelta, timezone

from maestro.profiles._schema import BusinessProfile


def suggest_post_time(profile: BusinessProfile) -> str:
    if profile.marketing.best_posting_times:
        return profile.marketing.best_posting_times[0]
    return (datetime.now(timezone.utc) + timedelta(days=1)).replace(
        hour=18, minute=0, second=0, microsecond=0
    ).isoformat()
