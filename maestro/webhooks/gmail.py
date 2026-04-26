"""Gmail push notification webhook — cold email reply → SDR Agent."""
from __future__ import annotations

import base64
import json

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from maestro.config import Settings, get_settings
from maestro.graph import MaestroGraph
from maestro.memory.redis_session import get_session, is_stopped, set_session
from maestro.repositories import store
from maestro.schemas.events import LeadIn
from maestro.services.cost_monitor import evaluate_cost_guard
from maestro.services.gmail import GmailClient

router = APIRouter(prefix="/webhooks/gmail", tags=["webhooks"])
log = structlog.get_logger()

_HISTORY_SESSION_KEY = "gmail:history_id"
_HISTORY_SESSION_TTL = 60 * 60 * 24 * 30  # 30 days


@router.post("")
async def gmail_webhook(
    request: Request,
    token: str = Query(default=""),
    settings: Settings = Depends(get_settings),
) -> dict:
    # 1. Validate shared secret — Pub/Sub sends ?token=... in the push URL
    if not settings.gmail_webhook_secret or token != settings.gmail_webhook_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")

    # 2. Parse Pub/Sub envelope
    body = await request.json()
    raw_data = body.get("message", {}).get("data", "")
    try:
        decoded = json.loads(base64.b64decode(raw_data + "=="))
    except Exception:
        return {"status": "ignored", "reason": "invalid_pubsub_payload"}

    history_id = str(decoded.get("historyId", ""))
    if not history_id:
        return {"status": "ignored", "reason": "no_history_id"}

    # 3. Paused / cost guard
    if store.paused or is_stopped():
        return {"status": "paused"}
    cost_guard = await evaluate_cost_guard(settings, store, source="gmail")
    if cost_guard.should_block:
        return {"status": "blocked", "reason": "cost_guard"}

    # 4. Gmail client check
    gmail = GmailClient(settings)
    if not gmail.is_configured():
        log.warning("gmail_not_configured")
        return {"status": "skipped", "reason": "gmail_not_configured"}

    # 5. Determine startHistoryId — use previous value, fall back to historyId - 1
    session = get_session(_HISTORY_SESSION_KEY)
    start_id = (session or {}).get("history_id") or str(int(history_id) - 1)
    set_session(_HISTORY_SESSION_KEY, {"history_id": history_id}, ttl=_HISTORY_SESSION_TTL)

    # 6. Fetch history and process replies
    processed: list[dict] = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            history_events = await gmail.list_history(client, start_history_id=start_id)
        except Exception as exc:
            log.error("gmail_history_fetch_failed", error=str(exc))
            return {"status": "error", "reason": str(exc)[:200]}

        for event in history_events:
            for msg_meta in event.get("messagesAdded", []):
                message_id = msg_meta.get("message", {}).get("id")
                if not message_id:
                    continue

                event_key = f"gmail:{message_id}"
                if await store.is_processed(event_key):
                    continue

                try:
                    raw = await gmail.get_message(client, message_id)
                    reply = gmail.parse_reply(raw)
                except Exception as exc:
                    log.error("gmail_message_fetch_failed", message_id=message_id, error=str(exc))
                    await store.mark_processed(event_key, "gmail", {"status": "fetch_error"})
                    continue

                if not reply:
                    await store.mark_processed(event_key, "gmail", {"status": "not_a_reply"})
                    continue

                result = await _handle_reply(reply, settings)
                await store.mark_processed(event_key, "gmail", result)
                processed.append(result)

    return {"status": "ok", "processed": len(processed)}


async def _handle_reply(reply, settings: Settings) -> dict:
    lead_record = await store.get_lead_by_email(reply.sender_email)

    if not lead_record:
        log.info("gmail_reply_no_lead", email=reply.sender_email)
        return {"status": "no_lead", "email": reply.sender_email}

    # STOP request — log compliance event, no SDR routing
    if reply.is_stop_request:
        await store.add_audit_log(
            event_type="compliance",
            business=lead_record.business,
            agent="gmail",
            action="stop_request_received",
            payload={
                "email": reply.sender_email,
                "message_id": reply.message_id,
                "lead_id": str(lead_record.id),
            },
        )
        log.info("gmail_stop_request", email=reply.sender_email, business=lead_record.business)
        return {"status": "stop_request", "email": reply.sender_email, "business": lead_record.business}

    lead_in = LeadIn(
        event_id=f"gmail:{reply.message_id}",
        business=lead_record.business,
        name=reply.sender_name or lead_record.name or reply.sender_email,
        email=reply.sender_email,
        source="cold_email_reply",
        message=reply.body_text,
        raw={
            "gmail_message_id": reply.message_id,
            "gmail_thread_id": reply.thread_id,
            "subject": reply.subject,
            "original_lead_id": str(lead_record.id),
            "original_source": lead_record.source,
        },
    )

    graph = MaestroGraph(settings, store)
    result = await graph.handle_inbound_lead(lead_in)

    log.info(
        "gmail_reply_routed_to_sdr",
        email=reply.sender_email,
        business=lead_record.business,
        graph_status=result.get("status"),
    )
    return {"status": "routed_to_sdr", "graph_result": result}
