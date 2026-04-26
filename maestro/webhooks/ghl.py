from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from maestro.config import Settings, get_settings
from maestro.graph import MaestroGraph
from maestro.memory.redis_session import is_stopped
from maestro.profiles import load_profile
from maestro.repositories import store
from maestro.schemas.events import LeadIn
from maestro.utils.contact_policy import find_do_not_contact_match
from maestro.utils.security import verify_hmac_signature

router = APIRouter(prefix="/webhooks/ghl", tags=["webhooks"])


def _extract_lead(payload: dict, business: str, event_id: str) -> LeadIn:
    contact = payload.get("contact") or payload.get("contactData") or payload
    opportunity = payload.get("opportunity") or payload.get("opportunityData") or {}
    name = contact.get("name") or " ".join(
        part for part in [contact.get("firstName"), contact.get("lastName")] if part
    )
    return LeadIn(
        event_id=event_id,
        business=business,
        name=name or None,
        phone=contact.get("phone"),
        email=contact.get("email"),
        source=payload.get("source") or opportunity.get("source") or "ghl",
        message=payload.get("message") or opportunity.get("notes") or contact.get("message"),
        estimated_ticket_usd=opportunity.get("monetaryValue") or payload.get("estimated_ticket_usd"),
        raw=payload,
    )


@router.post("/{business}")
async def ghl_webhook(
    business: str,
    request: Request,
    settings: Settings = Depends(get_settings),
    x_ghl_signature: str | None = Header(default=None),
    x_ghl_event_id: str | None = Header(default=None),
) -> dict:
    if business not in {"roberts", "dockplusai"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown_business")

    body = await request.body()
    verify_hmac_signature(settings.ghl_secret_for_business(business), body, x_ghl_signature)
    payload = await request.json()
    event_id = x_ghl_event_id or payload.get("eventId") or payload.get("id") or str(uuid4())
    lead = _extract_lead(payload, business, event_id)
    excluded = find_do_not_contact_match(lead.model_dump(mode="json"), load_profile(business))
    if excluded:
        result = {
            "status": "excluded_contact",
            "event_id": event_id,
            "business": business,
            "reason": excluded.reason,
        }
        await store.add_audit_log(
            event_type="agent_decision",
            business=business,
            agent="sdr",
            action="skipped_do_not_contact",
            payload=result,
        )
        await store.mark_processed(event_id, "ghl", result, business=business)
        return result

    # Check both in-memory flag (fast) and Redis flag (survives restart)
    if store.paused or is_stopped():
        await store.add_audit_log(
            event_type="agent_decision",
            business=business,
            agent="sdr",
            action="skipped_paused",
            payload={"event_id": event_id},
        )
        return {"status": "paused", "event_id": event_id}

    graph = MaestroGraph(settings, store)
    return await graph.handle_inbound_lead(lead)
