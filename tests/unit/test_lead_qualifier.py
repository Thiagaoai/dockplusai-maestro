"""
Unit tests for lead_qualifier — all run against deterministic fallback (no LLM).
ANTHROPIC_API_KEY is empty in conftest so LLM is never called.
"""

import pytest

from maestro.profiles.loader import load_profile
from maestro.schemas.events import LeadRecord
from maestro.subagents.sdr.lead_qualifier import qualify_lead


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
        "name": "John Smith",
        "source": "website",
    }
    defaults.update(kwargs)
    return LeadRecord(**defaults)


# ── test 1: high-quality lead scores high and gets request_approval ────────────

@pytest.mark.asyncio
async def test_high_quality_lead_gets_approval(roberts):
    lead = _lead(
        email="john@example.com",
        phone="5085551234",
        estimated_ticket_usd=8000,
        message="I need a quote urgently for a full lawn renovation",
    )
    result = await qualify_lead(lead, roberts)

    assert result["score"] >= 70
    assert result["recommended_action"] == "request_approval"
    assert result["justification"]


# ── test 2: no contact info tanks the score ────────────────────────────────────

@pytest.mark.asyncio
async def test_no_contact_info_reduces_score(roberts):
    lead = _lead(
        email=None,
        phone=None,
        estimated_ticket_usd=6000,
    )
    result = await qualify_lead(lead, roberts)

    assert result["score"] < 70
    assert "missing" in result["justification"].lower() or "contact" in result["justification"].lower()


# ── test 3: ticket below threshold reduces score ───────────────────────────────

@pytest.mark.asyncio
async def test_ticket_below_threshold_reduces_score(roberts):
    lead = _lead(
        email="low@example.com",
        estimated_ticket_usd=500,  # roberts min is $5000
    )
    result = await qualify_lead(lead, roberts)

    # With contact but below threshold, stays in manual_review or lower
    assert result["score"] < 80
    assert "below" in result["justification"].lower() or "threshold" in result["justification"].lower()


# ── test 4: urgent wording adds bonus points ───────────────────────────────────

@pytest.mark.asyncio
async def test_high_intent_wording_boosts_score(roberts):
    lead_no_intent = _lead(email="a@a.com", estimated_ticket_usd=6000, message="Just browsing")
    lead_urgent = _lead(email="b@b.com", estimated_ticket_usd=6000, message="Need an urgent estimate ASAP")

    result_no = await qualify_lead(lead_no_intent, roberts)
    result_yes = await qualify_lead(lead_urgent, roberts)

    assert result_yes["score"] > result_no["score"]


# ── test 5: result always has required keys ────────────────────────────────────

@pytest.mark.asyncio
async def test_result_schema_is_always_complete(dockplusai):
    lead = _lead(business="dockplusai")
    result = await qualify_lead(lead, dockplusai)

    assert "score" in result
    assert "justification" in result
    assert "recommended_action" in result
    assert isinstance(result["score"], int)
    assert 0 <= result["score"] <= 100
    assert result["recommended_action"] in ("request_approval", "manual_review", "disqualify")
