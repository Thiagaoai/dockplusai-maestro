from maestro.profiles._schema import BusinessProfile


def create_visual_prompts(topic: str, profile: BusinessProfile) -> list[str]:
    style = profile.marketing.visual_style
    return [
        f"{topic}, {style}, real business asset, high-trust local proof",
        f"Before and after concept for {topic}, {style}, clean composition",
    ]
