from maestro.profiles._schema import BusinessProfile


def validate_brand_output(text: str, profile: BusinessProfile) -> dict:
    lowered = text.lower()
    issues = [word for word in profile.brand_rules.forbidden_words if word.lower() in lowered]
    return {
        "approved": not issues,
        "issues": issues,
        "suggested_revision": "" if not issues else "Remove forbidden words and soften promise.",
    }
