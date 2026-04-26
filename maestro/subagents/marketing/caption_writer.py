"""
Caption Writer — generates social post content with caption, hashtags, and visual prompts.

Primary: Claude Sonnet 4.6 using marketing_create_post prompt template.
Fallback: template-based when LLM unavailable (dev/test).

All output is always in English (external-facing content).
"""

import json
import re

import structlog

from maestro.profiles._schema import BusinessProfile

log = structlog.get_logger()


def write_caption(topic: str, profile: BusinessProfile) -> str:
    """Sync fallback — used in tests and when API key is absent."""
    offering = profile.offerings[0].name if profile.offerings else "service"
    return (
        f"{topic.title()} — done right, the first time.\n\n"
        f"At {profile.business_name}, every project starts with listening. "
        f"We assess, plan, and execute {offering} that lasts.\n\n"
        "DM us your project details and let's talk."
    )


def _parse_json(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("no JSON in LLM response")
    return json.loads(match.group())


async def create_post_with_llm(topic: str, profile: BusinessProfile, settings) -> dict:
    """
    Generate full post content via Claude Sonnet using the marketing_create_post prompt.
    Falls back to individual sync functions on failure or missing API key.
    Returns dict with: caption, hashtags, visual_prompts, scheduled_at, rationale.
    """
    from maestro.subagents.marketing.content_creator import create_visual_prompts
    from maestro.subagents.marketing.hashtag_strategist import choose_hashtags
    from maestro.subagents.marketing.posting_scheduler import suggest_post_time

    visual_prompts = create_visual_prompts(topic, profile)
    fallback = {
        "caption": write_caption(topic, profile),
        "hashtags": choose_hashtags(profile),
        "visual_prompts": visual_prompts,
        "image_url": "",
        "scheduled_at": suggest_post_time(profile),
        "rationale": "template fallback",
    }

    if not settings.anthropic_api_key:
        return fallback

    try:
        from maestro.subagents.marketing.content_creator import generate_image
        from maestro.utils.llm import SONNET, UnknownModelPricingError, call_claude
        from maestro.utils.prompts import load_prompt

        context = {
            "business_name": profile.business_name,
            "business_type": profile.business_type,
            "tone": profile.tone,
            "offerings": profile.offerings,
            "marketing": profile.marketing,
            "topic": topic,
        }
        prompt = load_prompt("marketing_create_post", context)

        raw = await call_claude(
            system="You are a social media content operator. Follow the instructions exactly.",
            user=prompt,
            settings=settings,
            model=SONNET,
            max_tokens=1024,
        )
        result = _parse_json(raw)

        scheduled_at = result.get("scheduled_at") or suggest_post_time(profile)
        hashtags = result.get("hashtags") or choose_hashtags(profile)
        final_visual_prompts = result.get("visual_prompts") or visual_prompts

        image_url = await generate_image(final_visual_prompts[0], settings)

        log.info(
            "caption_written",
            business=profile.business_id,
            topic=topic[:40],
            hashtags_count=len(hashtags),
            has_image=bool(image_url),
        )
        return {
            "caption": result.get("caption", fallback["caption"]),
            "hashtags": hashtags,
            "visual_prompts": final_visual_prompts,
            "image_url": image_url,
            "scheduled_at": scheduled_at,
            "rationale": result.get("rationale", ""),
        }

    except UnknownModelPricingError:
        raise
    except Exception as exc:
        log.warning("caption_writer_llm_failed", error=str(exc), fallback="template")
        if not fallback.get("image_url"):
            from maestro.subagents.marketing.content_creator import generate_image

            fallback["image_url"] = await generate_image(fallback["visual_prompts"][0], settings)
        return fallback
