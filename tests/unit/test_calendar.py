"""
Unit tests for the Google Calendar tool.
All tests run in dry_run mode (DRY_RUN=true in conftest) so no real HTTP calls.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maestro.tools.calendar import _deterministic_slots, create_event, find_free_slots


# ── deterministic slot generation ─────────────────────────────────────────────

def test_deterministic_slots_returns_requested_count():
    slots = _deterministic_slots(3)
    assert len(slots) == 3


def test_deterministic_slots_have_start_and_end():
    slots = _deterministic_slots(2)
    for slot in slots:
        assert "start" in slot
        assert "end" in slot
        assert slot["start"] < slot["end"]


def test_deterministic_slots_are_on_weekdays():
    slots = _deterministic_slots(5)
    for slot in slots:
        start_dt = datetime.fromisoformat(slot["start"])
        assert start_dt.weekday() < 5, f"Slot on weekend: {slot['start']}"


def test_deterministic_slots_are_in_the_future():
    now = datetime.now(timezone.utc)
    slots = _deterministic_slots(3)
    for slot in slots:
        start_dt = datetime.fromisoformat(slot["start"])
        assert start_dt > now


def test_deterministic_slots_custom_count():
    assert len(_deterministic_slots(1)) == 1
    assert len(_deterministic_slots(5)) == 5


# ── find_free_slots in dry_run ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_find_free_slots_dry_run_returns_deterministic():
    # conftest sets DRY_RUN=true, so no HTTP call is made
    slots = await find_free_slots.ainvoke({"count": 3})

    assert len(slots) == 3
    for slot in slots:
        assert "start" in slot
        assert "end" in slot


@pytest.mark.asyncio
async def test_find_free_slots_respects_count_param():
    slots = await find_free_slots.ainvoke({"count": 2})
    assert len(slots) == 2


@pytest.mark.asyncio
async def test_find_free_slots_falls_back_when_no_credentials(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "")
    from maestro.config import get_settings
    get_settings.cache_clear()

    slots = await find_free_slots.ainvoke({"count": 3})
    assert len(slots) == 3
    for slot in slots:
        assert "start" in slot


# ── create_event in dry_run ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_event_dry_run_does_not_call_api():
    result = await create_event.ainvoke({
        "title": "Discovery Call",
        "start_iso": "2026-05-01T14:00:00+00:00",
        "end_iso": "2026-05-01T15:00:00+00:00",
        "attendee_email": "lead@example.com",
        "description": "Discuss project",
    })

    assert result["dry_run"] is True
    assert result["title"] == "Discovery Call"


@pytest.mark.asyncio
async def test_create_event_dry_run_contains_times():
    result = await create_event.ainvoke({
        "title": "Site Visit",
        "start_iso": "2026-05-02T10:00:00+00:00",
        "end_iso": "2026-05-02T11:00:00+00:00",
        "attendee_email": "homeowner@example.com",
    })

    assert result["start"] == "2026-05-02T10:00:00+00:00"
    assert result["end"] == "2026-05-02T11:00:00+00:00"


# ── create_event raises when not dry_run and no credentials ──────────────────

@pytest.mark.asyncio
async def test_create_event_raises_without_credentials(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "")
    from maestro.config import get_settings
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="Google Calendar credentials not configured"):
        await create_event.ainvoke({
            "title": "Call",
            "start_iso": "2026-05-01T14:00:00+00:00",
            "end_iso": "2026-05-01T15:00:00+00:00",
            "attendee_email": "test@example.com",
        })
