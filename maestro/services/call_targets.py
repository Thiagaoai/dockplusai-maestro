from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
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
