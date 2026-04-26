import structlog

from maestro.profiles._schema import BusinessProfile

log = structlog.get_logger()


def create_visual_prompts(topic: str, profile: BusinessProfile) -> list[str]:
    style = profile.marketing.visual_style
    return [
        f"{topic}, {style}, real business asset, high-trust local proof",
        f"Before and after concept for {topic}, {style}, clean composition",
    ]


async def generate_image(prompt: str, settings) -> str:
    """Call Replicate to generate an image. Returns URL or empty string on failure/missing token."""
    if not getattr(settings, "replicate_api_token", ""):
        return ""
    try:
        from maestro.services.replicate import ReplicateClient, ReplicateError

        client = ReplicateClient(settings)
        return await client.generate_image(prompt, aspect_ratio="1:1")
    except Exception as exc:
        log.warning("replicate_generate_failed", error=str(exc)[:200])
        return ""
