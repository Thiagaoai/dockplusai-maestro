"""
Postforme.dev tool — schedule and publish social media posts.
Docs: https://api.postforme.dev/docs
"""
import os
from typing import Optional

import httpx
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

from maestro.utils.logging import get_logger

log = get_logger(__name__)

POSTFORME_API_URL = "https://api.postforme.dev/v1"


def _headers() -> dict:
    api_key = os.getenv("POSTFORME_API_KEY", "")
    if not api_key:
        raise ValueError("POSTFORME_API_KEY not set")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _account_id(business_id: str, platform: str = "instagram") -> str:
    key = f"POSTFORME_ACCOUNT_{business_id.upper()}_{platform.upper()}"
    account_id = os.getenv(key, "")
    if not account_id:
        raise ValueError(f"{key} not set")
    return account_id


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def schedule_post(
    business_id: str,
    platform: str,
    caption: str,
    image_url: str,
    scheduled_at: Optional[str] = None,
    *,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Schedule or publish a social media post via Postforme. platform: instagram|linkedin|facebook. Pass scheduled_at (ISO 8601) to schedule; omit to publish immediately. business_id: roberts|dockplusai."""
    account_id = _account_id(business_id, platform)

    log.info(
        "postforme_schedule_start",
        business_id=business_id,
        platform=platform,
        account_id=account_id,
        scheduled_at=scheduled_at,
        caption_len=len(caption),
    )

    payload: dict = {
        "caption": caption,
        "social_accounts": [account_id],
        "media": [{"url": image_url}],
    }
    if scheduled_at:
        payload["scheduled_at"] = scheduled_at
    if idempotency_key:
        payload["external_id"] = idempotency_key

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{POSTFORME_API_URL}/social-posts",
            json=payload,
            headers=_headers(),
        )
        response.raise_for_status()
        result = response.json()

    log.info(
        "postforme_schedule_success",
        business_id=business_id,
        platform=platform,
        post_id=result.get("id"),
        status=result.get("status"),
    )
    return {
        "post_id": result.get("id"),
        "status": result.get("status"),
        "scheduled_at": result.get("scheduled_at"),
        "platform": platform,
        "caption": caption,
    }


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def get_post_status(post_id: str) -> dict:
    """Get the current status of a Postforme post by its ID. Status: draft|scheduled|processing|processed."""
    log.info("postforme_get_status", post_id=post_id)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{POSTFORME_API_URL}/social-posts/{post_id}",
            headers=_headers(),
        )
        response.raise_for_status()
        result = response.json()

    log.info("postforme_get_status_success", post_id=post_id, status=result.get("status"))
    return {
        "post_id": result.get("id"),
        "status": result.get("status"),
        "scheduled_at": result.get("scheduled_at"),
        "caption": result.get("caption"),
    }


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def cancel_post(post_id: str) -> dict:
    """Cancel a scheduled or draft Postforme post. Only works on posts with status 'scheduled' or 'draft'."""
    log.info("postforme_cancel", post_id=post_id)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.delete(
            f"{POSTFORME_API_URL}/social-posts/{post_id}",
            headers=_headers(),
        )
        response.raise_for_status()
        result = response.json()

    log.info("postforme_cancel_success", post_id=post_id)
    return {"deleted": True, "post_id": post_id, "detail": result}


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def list_social_accounts() -> list:
    """List all connected social media accounts on Postforme. Returns account IDs needed for posting."""
    log.info("postforme_list_accounts")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{POSTFORME_API_URL}/social-accounts",
            headers=_headers(),
        )
        response.raise_for_status()
        result = response.json()

    accounts = [
        {
            "id": a.get("id"),
            "platform": a.get("platform"),
            "username": a.get("username"),
            "status": a.get("status"),
        }
        for a in result.get("data", [])
    ]
    log.info("postforme_list_accounts_success", count=len(accounts))
    return accounts
