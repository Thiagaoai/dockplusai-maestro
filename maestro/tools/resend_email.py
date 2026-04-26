"""
Resend email tool — LangChain @tool wrapper.
Replaces Gmail OAuth2. Simpler, more reliable, no token refresh needed.
"""
import os
from typing import Optional

import httpx
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

from maestro.utils.logging import get_logger
from maestro.utils.pii import mask_email

log = get_logger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def send_email(
    to: str,
    subject: str,
    body: str,
    from_address: str,
    reply_to: Optional[str] = None,
    *,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Send a transactional email via Resend. Use for lead outreach, follow-ups, and meeting confirmations."""
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        raise ValueError("RESEND_API_KEY not set")

    log.info("send_email_start", to=mask_email(to), subject=subject, from_address=from_address)

    payload: dict = {
        "from": from_address,
        "to": [to],
        "subject": subject,
        "text": body,
    }
    if reply_to:
        payload["reply_to"] = reply_to

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(RESEND_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()

    log.info("send_email_success", to=mask_email(to), email_id=result.get("id"))
    return {"email_id": result.get("id"), "to": to, "subject": subject}


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def send_email_html(
    to: str,
    subject: str,
    html_body: str,
    text_body: str,
    from_address: str,
    reply_to: Optional[str] = None,
    *,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Send an HTML email via Resend. Use when rich formatting improves readability."""
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        raise ValueError("RESEND_API_KEY not set")

    log.info("send_email_html_start", to=mask_email(to), subject=subject)

    payload: dict = {
        "from": from_address,
        "to": [to],
        "subject": subject,
        "html": html_body,
        "text": text_body,
    }
    if reply_to:
        payload["reply_to"] = reply_to

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(RESEND_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()

    log.info("send_email_html_success", to=mask_email(to), email_id=result.get("id"))
    return {"email_id": result.get("id"), "to": to, "subject": subject}
