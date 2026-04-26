"""
Unit tests for email_drafter — all run against template fallback (no LLM).
ANTHROPIC_API_KEY is empty in conftest so LLM is never called.
"""

import pytest

from maestro.profiles.loader import load_profile
from maestro.schemas.events import LeadRecord
from maestro.subagents.sdr.email_drafter import draft_email


@pytest.fixture
def roberts():
    return load_profile("roberts")


@pytest.fixture
def dockplusai():
    return load_profile("dockplusai")


def _lead(**kwargs) -> LeadRecord:
    defaults = {
        "event_id": "test-event",
        "business": "roberts",
        "name": "Sarah Johnson",
        "email": "sarah@example.com",
        "source": "website",
    }
    defaults.update(kwargs)
    return LeadRecord(**defaults)


# ── test 1: output always has subject and body ─────────────────────────────────

@pytest.mark.asyncio
async def test_draft_email_returns_subject_and_body(roberts):
    lead = _lead()
    result = await draft_email(lead, roberts)

    assert "subject" in result
    assert "body" in result
    assert isinstance(result["subject"], str)
    assert isinstance(result["body"], str)
    assert len(result["subject"]) > 0
    assert len(result["body"]) > 0


# ── test 2: uses first name in body ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_draft_email_addresses_lead_by_first_name(roberts):
    lead = _lead(name="Michael Torres")
    result = await draft_email(lead, roberts)

    assert "Michael" in result["body"]
    assert "Torres" not in result["body"]


# ── test 3: no name falls back gracefully ────────────────────────────────────

@pytest.mark.asyncio
async def test_draft_email_handles_missing_name(roberts):
    lead = _lead(name=None)
    result = await draft_email(lead, roberts)

    assert "subject" in result
    assert "body" in result
    assert len(result["body"]) > 10


# ── test 4: email body is in English, never Portuguese ────────────────────────

@pytest.mark.asyncio
async def test_draft_email_is_in_english(roberts):
    lead = _lead()
    result = await draft_email(lead, roberts)

    portuguese_markers = ["obrigado", "olá", "estimado", "prezado", "atenciosamente"]
    body_lower = result["body"].lower()
    for marker in portuguese_markers:
        assert marker not in body_lower, f"Portuguese word '{marker}' found in email body"


# ── test 5: dockplusai profile also produces valid email ─────────────────────

@pytest.mark.asyncio
async def test_draft_email_works_for_dockplusai(dockplusai):
    lead = _lead(business="dockplusai", name="Carlos Mendes", email="carlos@example.com")
    result = await draft_email(lead, dockplusai)

    assert "subject" in result
    assert "body" in result
    assert "Carlos" in result["body"]
    assert len(result["subject"]) <= 200


# ── test 6: signature is included in the email body ──────────────────────────

@pytest.mark.asyncio
async def test_draft_email_includes_signature(roberts):
    lead = _lead()
    result = await draft_email(lead, roberts)

    signature = roberts.tone.signature
    assert signature in result["body"]
