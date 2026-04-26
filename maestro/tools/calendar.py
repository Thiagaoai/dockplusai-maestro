"""
Google Calendar tool — find free slots and create events.

Uses OAuth2 refresh token (GOOGLE_REFRESH_TOKEN, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET).
Falls back to deterministic slot generation in dry_run or when credentials missing.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import structlog
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

log = structlog.get_logger()

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_CALENDAR_BASE = "https://www.googleapis.com/calendar/v3"
_CALENDAR_ID = "primary"
_SLOT_DURATION_MINUTES = 60


async def _get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    async with httpx.AsyncClient(timeout=10) as http:
        resp = await http.post(
            _TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


def _deterministic_slots(count: int = 3) -> list[dict]:
    """Generate next N business-hours slots starting tomorrow."""
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    slots = []
    cursor = now + timedelta(days=1)
    preferred_hours = [10, 14, 16]  # 10am, 2pm, 4pm UTC

    while len(slots) < count:
        if cursor.weekday() < 5:  # Mon–Fri
            hour = preferred_hours[len(slots) % len(preferred_hours)]
            start = cursor.replace(hour=hour, minute=0)
            end = start + timedelta(minutes=_SLOT_DURATION_MINUTES)
            slots.append({"start": start.isoformat(), "end": end.isoformat()})
        cursor += timedelta(days=1)

    return slots


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def find_free_slots(
    days_ahead: int = 5,
    count: int = 3,
    *,
    idempotency_key: Optional[str] = None,
) -> list[dict]:
    """
    Return N free 1-hour slots in the next `days_ahead` business days.
    Falls back to deterministic slots when credentials are missing.

    Returns list of {"start": ISO8601, "end": ISO8601}.
    """
    from maestro.config import get_settings
    settings = get_settings()

    if settings.dry_run or not all([
        settings.google_client_id,
        settings.google_client_secret,
        settings.google_refresh_token,
    ]):
        log.info("calendar_find_slots_fallback", dry_run=settings.dry_run)
        return _deterministic_slots(count)

    try:
        access_token = await _get_access_token(
            settings.google_client_id,
            settings.google_client_secret,
            settings.google_refresh_token,
        )

        now = datetime.now(timezone.utc)
        time_max = now + timedelta(days=days_ahead)

        # Fetch busy periods via freebusy API
        async with httpx.AsyncClient(timeout=30, headers={"Authorization": f"Bearer {access_token}"}) as http:
            resp = await http.post(
                f"{_CALENDAR_BASE}/freeBusy",
                json={
                    "timeMin": now.isoformat(),
                    "timeMax": time_max.isoformat(),
                    "items": [{"id": _CALENDAR_ID}],
                },
            )
            resp.raise_for_status()
            busy_periods = resp.json().get("calendars", {}).get(_CALENDAR_ID, {}).get("busy", [])

        busy_ranges = [
            (datetime.fromisoformat(b["start"]), datetime.fromisoformat(b["end"]))
            for b in busy_periods
        ]

        # Find free slots in business hours (10–18 UTC)
        slots = []
        cursor = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

        while len(slots) < count and cursor < time_max:
            if cursor.weekday() < 5 and 10 <= cursor.hour < 18:
                slot_end = cursor + timedelta(minutes=_SLOT_DURATION_MINUTES)
                overlaps = any(
                    not (slot_end <= b_start or cursor >= b_end)
                    for b_start, b_end in busy_ranges
                )
                if not overlaps:
                    slots.append({"start": cursor.isoformat(), "end": slot_end.isoformat()})
            cursor += timedelta(hours=1)

        log.info("calendar_slots_found", count=len(slots))
        return slots if slots else _deterministic_slots(count)

    except Exception as exc:
        log.warning("calendar_find_slots_failed", error=str(exc), fallback="deterministic")
        return _deterministic_slots(count)


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def create_event(
    title: str,
    start_iso: str,
    end_iso: str,
    attendee_email: str,
    description: str = "",
    *,
    idempotency_key: Optional[str] = None,
) -> dict:
    """
    Create a Google Calendar event and send invite to attendee.
    Returns {"event_id": str, "html_link": str} or {"dry_run": True} in dry_run mode.
    """
    from maestro.config import get_settings
    settings = get_settings()

    log.info("calendar_create_event_start", title=title, start=start_iso, attendee="[REDACTED]")

    if settings.dry_run:
        log.info("calendar_create_event_dry_run", title=title)
        return {"dry_run": True, "title": title, "start": start_iso, "end": end_iso}

    if not all([settings.google_client_id, settings.google_client_secret, settings.google_refresh_token]):
        raise ValueError("Google Calendar credentials not configured")

    access_token = await _get_access_token(
        settings.google_client_id,
        settings.google_client_secret,
        settings.google_refresh_token,
    )

    event_body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_iso, "timeZone": "UTC"},
        "end": {"dateTime": end_iso, "timeZone": "UTC"},
        "attendees": [{"email": attendee_email}],
        "reminders": {"useDefault": True},
    }

    async with httpx.AsyncClient(timeout=30, headers={"Authorization": f"Bearer {access_token}"}) as http:
        resp = await http.post(
            f"{_CALENDAR_BASE}/calendars/{_CALENDAR_ID}/events",
            json=event_body,
            params={"sendUpdates": "all"},
        )
        resp.raise_for_status()
        data = resp.json()

    log.info("calendar_event_created", event_id=data.get("id"), title=title)
    return {"event_id": data.get("id"), "html_link": data.get("htmlLink")}
