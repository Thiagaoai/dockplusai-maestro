from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from maestro.config import Settings, get_settings
from maestro.repositories import store

router = APIRouter(prefix="/webhooks/resend", tags=["webhooks"])


@router.post("")
async def resend_webhook(
    request: Request,
    token: str = Query(default=""),
    svix_id: str | None = Header(default=None),
    svix_timestamp: str | None = Header(default=None),
    svix_signature: str | None = Header(default=None),
    x_resend_webhook_secret: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    raw_body = await request.body()
    if settings.resend_webhook_secret and not token:
        if not _verify_svix_signature(
            secret=settings.resend_webhook_secret,
            payload=raw_body,
            svix_id=svix_id,
            svix_timestamp=svix_timestamp,
            svix_signature=svix_signature,
        ):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature")
    elif settings.resend_webhook_secret:
        supplied = token or x_resend_webhook_secret or ""
        if supplied != settings.resend_webhook_secret:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        return {"status": "ignored", "reason": "invalid_json"}
    event_type = str(payload.get("type") or payload.get("event") or "unknown")
    data = payload.get("data") or {}
    email_id = str(data.get("email_id") or data.get("id") or payload.get("email_id") or "")
    event_id = str(payload.get("id") or f"resend:{event_type}:{email_id}")

    if event_id and await store.is_processed(event_id):
        return {"status": "duplicate"}

    email = _first_email(data.get("to") or data.get("recipient") or payload.get("to"))
    business = _business_from_payload(data, email)
    result = {
        "status": "recorded",
        "event_type": event_type,
        "business": business,
        "email_id": email_id,
        "email": email,
    }

    await store.add_audit_log(
        event_type="email_event",
        business=business,
        agent="prospecting",
        action="resend_email_event",
        payload={**payload, "normalized": result},
    )

    if event_type in {"email.bounced", "email.complained", "email.delivery_delayed"}:
        await store.add_audit_log(
            event_type="deliverability",
            business=business,
            agent="prospecting",
            action=event_type.replace(".", "_"),
            payload={"email_id": email_id, "email": email, "raw": payload},
        )

    if event_id:
        await store.mark_processed(event_id, "resend", result, business=business)
    return result


def _first_email(value: Any) -> str | None:
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            return str(first.get("email") or "").casefold() or None
        return str(first).casefold()
    if isinstance(value, dict):
        return str(value.get("email") or "").casefold() or None
    if value:
        return str(value).casefold()
    return None


def _business_from_payload(data: dict[str, Any], email: str | None) -> str:
    from_addr = str(data.get("from") or "").casefold()
    if "dockplus" in from_addr:
        return "dockplusai"
    if email and email.endswith("@dockplusai.com"):
        return "dockplusai"
    return "roberts"


def _verify_svix_signature(
    secret: str,
    payload: bytes,
    svix_id: str | None,
    svix_timestamp: str | None,
    svix_signature: str | None,
) -> bool:
    if not svix_id or not svix_timestamp or not svix_signature:
        return False
    try:
        timestamp = int(svix_timestamp)
    except ValueError:
        return False
    if abs(int(time.time()) - timestamp) > 60 * 5:
        return False

    secret_value = secret.removeprefix("whsec_")
    try:
        secret_bytes = base64.b64decode(secret_value)
    except Exception:
        secret_bytes = secret_value.encode("utf-8")

    signed_payload = b".".join([svix_id.encode("utf-8"), svix_timestamp.encode("utf-8"), payload])
    expected = base64.b64encode(
        hmac.new(secret_bytes, signed_payload, hashlib.sha256).digest()
    ).decode("utf-8")

    for signature in svix_signature.split():
        if "," not in signature:
            continue
        version, value = signature.split(",", 1)
        if version == "v1" and hmac.compare_digest(value, expected):
            return True
    return False
