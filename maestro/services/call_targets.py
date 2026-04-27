from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


EVENT_PRIORITY = {
    "email.clicked": 100,
    "email.opened": 80,
    "email.delivered": 60,
    "email.sent": 40,
    "email.delivery_delayed": 20,
    "email.bounced": -100,
    "email.complained": -100,
    "email.failed": -100,
    "email.suppressed": -100,
}

BAD_EVENTS = {"email.bounced", "email.complained", "email.failed", "email.suppressed"}


@dataclass(frozen=True)
class CallTarget:
    name: str
    email: str
    phone: str | None
    source_ref: str | None
    email_id: str
    status: str
    priority: str
    last_event_at: datetime | None
    events: tuple[str, ...]


def build_call_targets(
    send_rows: list[dict[str, Any]],
    event_rows: list[dict[str, Any]],
    leads_by_source_ref: dict[str, dict[str, Any]],
    limit: int = 50,
) -> list[CallTarget]:
    events_by_email_id = _events_by_email_id(event_rows)
    targets: list[CallTarget] = []
    seen_email_ids: set[str] = set()

    for row in send_rows:
        payload = row.get("payload") or {}
        created_at = _parse_datetime(row.get("created_at"))
        for sent in payload.get("sent", []):
            email_id = str(sent.get("email_id") or "")
            if not email_id or email_id in seen_email_ids:
                continue
            seen_email_ids.add(email_id)

            source_ref = sent.get("source_ref")
            lead = leads_by_source_ref.get(source_ref or "", {})
            email = str(sent.get("email") or lead.get("email") or "")
            if not email:
                continue

            event_items = events_by_email_id.get(email_id, [])
            event_names = tuple(item["event_type"] for item in event_items)
            status = _status_for_events(event_names)
            last_event_at = _latest_event_at(event_items) or created_at

            targets.append(
                CallTarget(
                    name=str(lead.get("name") or sent.get("property_name") or "Unknown"),
                    email=email,
                    phone=lead.get("phone"),
                    source_ref=source_ref,
                    email_id=email_id,
                    status=status,
                    priority=_priority_for_events(event_names),
                    last_event_at=last_event_at,
                    events=event_names,
                )
            )

    targets.sort(
        key=lambda target: (
            _priority_rank(target.priority),
            target.last_event_at or datetime.min.replace(tzinfo=UTC),
        ),
        reverse=True,
    )
    return targets[:limit]


def source_refs_from_send_rows(send_rows: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for row in send_rows:
        for sent in (row.get("payload") or {}).get("sent", []):
            source_ref = sent.get("source_ref")
            if source_ref and source_ref not in seen:
                seen.add(source_ref)
                refs.append(source_ref)
    return refs


async def load_call_targets(
    store: Any,
    business: str = "roberts",
    days: int = 7,
    limit: int = 50,
) -> list[CallTarget]:
    if hasattr(store, "client"):
        send_rows = _fetch_supabase_audit_rows(
            store,
            business=business,
            action="prospecting_batch_send_html",
            days=days,
            limit=max(limit * 4, 100),
        )
        event_rows = _fetch_supabase_audit_rows(
            store,
            business=business,
            action="resend_email_event",
            days=days,
            limit=max(limit * 20, 500),
        )
        leads_by_source_ref = _fetch_supabase_leads_by_source_ref(
            store,
            business,
            source_refs_from_send_rows(send_rows),
        )
        return build_call_targets(send_rows, event_rows, leads_by_source_ref, limit=limit)

    send_rows = [
        record.model_dump(mode="json")
        for record in getattr(store, "audit_log", [])
        if record.business == business and record.agent == "prospecting" and record.action == "prospecting_batch_send_html"
    ]
    event_rows = [
        record.model_dump(mode="json")
        for record in getattr(store, "audit_log", [])
        if record.business == business and record.agent == "prospecting" and record.action == "resend_email_event"
    ]
    leads_by_source_ref = _memory_leads_by_source_ref(store, business, source_refs_from_send_rows(send_rows))
    return build_call_targets(send_rows, event_rows, leads_by_source_ref, limit=limit)


def _events_by_email_id(event_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in event_rows:
        payload = row.get("payload") or {}
        normalized = payload.get("normalized") or {}
        email_id = str(normalized.get("email_id") or payload.get("email_id") or "")
        event_type = str(normalized.get("event_type") or payload.get("type") or payload.get("event") or "")
        if not email_id or not event_type:
            continue
        grouped.setdefault(email_id, []).append(
            {
                "event_type": event_type,
                "created_at": _parse_datetime(row.get("created_at")),
            }
        )
    for items in grouped.values():
        items.sort(key=lambda item: item.get("created_at") or datetime.min.replace(tzinfo=UTC))
    return grouped


def _fetch_supabase_audit_rows(
    store: Any,
    business: str,
    action: str,
    days: int,
    limit: int,
) -> list[dict[str, Any]]:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    response = (
        store.client.table("audit_log")
        .select("payload,created_at")
        .eq("business", business)
        .eq("agent", "prospecting")
        .eq("action", action)
        .gte("created_at", cutoff.isoformat())
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return getattr(response, "data", None) or []


def _fetch_supabase_leads_by_source_ref(
    store: Any,
    business: str,
    source_refs: list[str],
) -> dict[str, dict[str, Any]]:
    if not source_refs:
        return {}
    queue_rows: list[dict[str, Any]] = []
    for chunk in _chunks(source_refs, 100):
        response = (
            store.client.table("prospect_queue")
            .select("source_ref,lead_id")
            .eq("business", business)
            .in_("source_ref", chunk)
            .execute()
        )
        queue_rows.extend(getattr(response, "data", None) or [])

    lead_ids = [row["lead_id"] for row in queue_rows if row.get("lead_id")]
    leads_by_id: dict[str, dict[str, Any]] = {}
    for chunk in _chunks(lead_ids, 100):
        response = (
            store.client.table("leads")
            .select("id,name,email,phone")
            .in_("id", chunk)
            .execute()
        )
        for row in getattr(response, "data", None) or []:
            leads_by_id[str(row.get("id"))] = row

    return {
        row["source_ref"]: leads_by_id.get(str(row.get("lead_id")), {})
        for row in queue_rows
        if row.get("source_ref")
    }


def _memory_leads_by_source_ref(store: Any, business: str, source_refs: list[str]) -> dict[str, dict[str, Any]]:
    refs = set(source_refs)
    leads_by_ref: dict[str, dict[str, Any]] = {}
    for item in getattr(store, "prospect_queue", []):
        source_ref = item.get("source_ref")
        if item.get("business") != business or source_ref not in refs:
            continue
        lead = getattr(store, "leads", {}).get(str(item.get("lead_id")))
        if lead:
            leads_by_ref[source_ref] = lead.model_dump(mode="json")
    return leads_by_ref


def _status_for_events(events: tuple[str, ...]) -> str:
    if any(event in BAD_EVENTS for event in events):
        return "do_not_call"
    if "email.clicked" in events:
        return "clicked"
    if "email.opened" in events:
        return "opened"
    if "email.delivered" in events:
        return "delivered"
    if "email.delivery_delayed" in events:
        return "delayed"
    if "email.sent" in events:
        return "sent"
    return "sent_unconfirmed"


def _priority_for_events(events: tuple[str, ...]) -> str:
    if any(event in BAD_EVENTS for event in events):
        return "blocked"
    if "email.clicked" in events or "email.opened" in events:
        return "high"
    if "email.delivered" in events:
        return "call"
    if "email.sent" in events:
        return "wait"
    return "wait"


def _priority_rank(priority: str) -> int:
    return {"high": 4, "call": 3, "wait": 2, "blocked": 1}.get(priority, 0)


def _latest_event_at(items: list[dict[str, Any]]) -> datetime | None:
    dates = [item.get("created_at") for item in items if item.get("created_at")]
    return max(dates) if dates else None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[idx : idx + size] for idx in range(0, len(values), size)]
