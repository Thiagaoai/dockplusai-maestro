"""
Unit tests for SDRAgent enrichment waterfall (Apollo → Hunter) and helper functions.
Tests internal methods directly to reach the uncovered branches.
"""

from unittest.mock import AsyncMock, patch

import pytest

from maestro.agents.sdr import SDRAgent, _domain_from_profile
from maestro.config import get_settings
from maestro.profiles.loader import load_profile
from maestro.schemas.events import LeadRecord


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def roberts():
    return load_profile("roberts")


@pytest.fixture
def dockplusai():
    return load_profile("dockplusai")


def _lead(**kwargs) -> LeadRecord:
    defaults = {
        "event_id": "test-enrich",
        "business": "roberts",
        "name": "James Carter",
        "source": "website",
    }
    defaults.update(kwargs)
    return LeadRecord(**defaults)


# ── _domain_from_profile ──────────────────────────────────────────────────────

def test_domain_from_profile_extracts_domain(roberts):
    domain = _domain_from_profile(roberts)
    assert domain is not None
    assert "." in domain
    assert "www." not in domain


def test_domain_from_profile_returns_none_when_no_website(roberts):
    from maestro.profiles._schema import Contact
    profile_copy = roberts.model_copy(deep=True)
    profile_copy.contact.website = None
    domain = _domain_from_profile(profile_copy)
    assert domain is None


# ── _apply_enrichment ─────────────────────────────────────────────────────────

def test_apply_enrichment_sets_email(settings, roberts):
    agent = SDRAgent(settings, roberts)
    lead = _lead(email=None, phone="508-555-1234")
    person = {"email": "james@example.com", "phone": None, "name": None, "apollo_id": "ap-001", "title": "Owner", "company": {"name": "Acme"}}

    result = agent._apply_enrichment(lead, person, source="apollo")

    assert lead.email == "james@example.com"
    assert "email" in result["fields"]
    assert result["source"] == "apollo"
    assert result["enriched"] is True


def test_apply_enrichment_sets_phone(settings, roberts):
    agent = SDRAgent(settings, roberts)
    lead = _lead(email="james@example.com", phone=None)
    person = {"email": None, "phone": "508-555-9999", "name": None, "apollo_id": None, "title": None, "company": {}}

    result = agent._apply_enrichment(lead, person, source="apollo")

    assert lead.phone == "508-555-9999"
    assert "phone" in result["fields"]


def test_apply_enrichment_skips_existing_fields(settings, roberts):
    agent = SDRAgent(settings, roberts)
    lead = _lead(email="existing@example.com", phone="508-555-0000")
    person = {"email": "new@example.com", "phone": "508-555-9999", "name": None, "apollo_id": None, "title": None, "company": {}}

    result = agent._apply_enrichment(lead, person, source="apollo")

    # Should NOT overwrite existing data
    assert lead.email == "existing@example.com"
    assert lead.phone == "508-555-0000"
    assert result["fields"] == []


# ── _maybe_enrich_lead: skip if already has both ──────────────────────────────

@pytest.mark.asyncio
async def test_maybe_enrich_skips_when_complete_contact(settings, roberts):
    agent = SDRAgent(settings, roberts)
    lead = _lead(email="james@example.com", phone="508-555-1234")

    result = await agent._maybe_enrich_lead(lead)

    assert result["enriched"] is False
    assert result["reason"] == "complete_contact_data"


# ── _maybe_enrich_lead: skip when insufficient data ──────────────────────────

@pytest.mark.asyncio
async def test_maybe_enrich_skips_when_no_name_or_email(settings, roberts):
    agent = SDRAgent(settings, roberts)
    lead = _lead(name=None, email=None)

    result = await agent._maybe_enrich_lead(lead)

    assert result["enriched"] is False
    assert result["reason"] == "insufficient_data_for_enrichment"


# ── _maybe_enrich_lead: Apollo returns person ─────────────────────────────────

@pytest.mark.asyncio
async def test_maybe_enrich_applies_apollo_result(settings, roberts):
    agent = SDRAgent(settings, roberts)
    lead = _lead(name="James Carter", email=None)

    apollo_person = {
        "email": "james@acme.com",
        "phone": "508-555-0001",
        "name": "James Carter",
        "apollo_id": "ap-123",
        "title": "Owner",
        "company": {"name": "Acme LLC"},
    }

    with patch(
        "maestro.agents.sdr.enrich_lead",
        new_callable=AsyncMock,
        return_value={"person": apollo_person, "plan_limited": False},
    ):
        result = await agent._maybe_enrich_lead(lead)

    assert result["enriched"] is True
    assert result["source"] == "apollo"
    assert lead.email == "james@acme.com"


# ── _maybe_enrich_lead: Apollo fails, Hunter fallback ─────────────────────────

@pytest.mark.asyncio
async def test_maybe_enrich_falls_back_to_hunter(settings, roberts):
    profile = roberts.model_copy(deep=True)
    agent = SDRAgent(settings, profile)
    lead = _lead(name="Alice Brown", email=None)

    with patch(
        "maestro.agents.sdr.enrich_lead",
        new_callable=AsyncMock,
        return_value={"person": None, "plan_limited": False},
    ), patch(
        "maestro.agents.sdr.find_email",
        new_callable=AsyncMock,
        return_value={"email": "alice@domain.com", "confidence": 85, "position": "Owner"},
    ):
        result = await agent._maybe_enrich_lead(lead)

    assert result["enriched"] is True
    assert result["source"] == "hunter"
    assert lead.email == "alice@domain.com"


# ── _maybe_enrich_lead: both fail ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_maybe_enrich_returns_no_match_when_both_fail(settings, roberts):
    agent = SDRAgent(settings, roberts)
    lead = _lead(name="Unknown Person", email=None)

    with patch(
        "maestro.agents.sdr.enrich_lead",
        new_callable=AsyncMock,
        return_value={"person": None, "plan_limited": False},
    ), patch(
        "maestro.agents.sdr.find_email",
        new_callable=AsyncMock,
        return_value={"email": None, "confidence": None},
    ):
        result = await agent._maybe_enrich_lead(lead)

    assert result["enriched"] is False
    assert result["reason"] == "no_match"
