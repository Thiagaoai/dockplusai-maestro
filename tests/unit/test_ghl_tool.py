"""
Unit tests for GHL tool — helpers and mocked API calls.
Covers _headers, _location_id, get_contact, create_contact, move_opportunity_stage.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maestro.tools.ghl import (
    _headers,
    _location_id,
    create_contact,
    create_opportunity,
    get_contact,
    get_contact_opportunities,
    move_opportunity_stage,
    search_contacts,
    update_contact,
)


# ── helper functions ──────────────────────────────────────────────────────────

def test_headers_raises_when_token_missing():
    with pytest.raises(ValueError, match="GHL_TOKEN_UNKNOWN"):
        _headers("unknown")


def test_headers_returns_correct_format(monkeypatch):
    monkeypatch.setenv("GHL_TOKEN_ROBERTS", "test-token-abc")
    headers = _headers("roberts")
    assert headers["Authorization"] == "Bearer test-token-abc"
    assert "Version" in headers


def test_location_id_raises_when_missing():
    with pytest.raises(ValueError, match="GHL_LOCATION_ID_UNKNOWN"):
        _location_id("unknown")


def test_location_id_returns_env_var(monkeypatch):
    monkeypatch.setenv("GHL_LOCATION_ID_ROBERTS", "loc-roberts-123")
    loc = _location_id("roberts")
    assert loc == "loc-roberts-123"


# ── shared mock helpers ───────────────────────────────────────────────────────

def _mock_response(json_data: dict, status_code: int = 200):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.status_code = status_code
    response.json = lambda: json_data
    response.is_success = status_code < 400
    return response


# ── get_contact ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_contact_returns_contact(monkeypatch):
    monkeypatch.setenv("GHL_TOKEN_ROBERTS", "tok")
    monkeypatch.setenv("GHL_LOCATION_ID_ROBERTS", "loc-123")

    contact_data = {"id": "c-001", "name": "John Smith", "email": "john@example.com"}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response({"contact": contact_data})
        result = await get_contact.ainvoke({"business_id": "roberts", "contact_id": "c-001"})

    assert result["id"] == "c-001"
    assert result["email"] == "john@example.com"


# ── search_contacts ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_contacts_returns_list(monkeypatch):
    monkeypatch.setenv("GHL_TOKEN_ROBERTS", "tok")
    monkeypatch.setenv("GHL_LOCATION_ID_ROBERTS", "loc-123")

    contacts_data = [{"id": "c-001"}, {"id": "c-002"}]

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response({"contacts": contacts_data})
        result = await search_contacts.ainvoke({"business_id": "roberts", "query": "john"})

    assert len(result) == 2
    assert result[0]["id"] == "c-001"


# ── create_contact ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_contact_returns_contact_id(monkeypatch):
    monkeypatch.setenv("GHL_TOKEN_ROBERTS", "tok")
    monkeypatch.setenv("GHL_LOCATION_ID_ROBERTS", "loc-123")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_response({"contact": {"id": "c-new-001"}})
        result = await create_contact.ainvoke({
            "business_id": "roberts",
            "first_name": "Maria",
            "last_name": "Silva",
            "email": "maria@example.com",
            "phone": "508-555-0100",
        })

    assert result["contact_id"] == "c-new-001"
    assert "Maria" in result["name"]


# ── update_contact ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_contact_returns_updated(monkeypatch):
    monkeypatch.setenv("GHL_TOKEN_ROBERTS", "tok")
    monkeypatch.setenv("GHL_LOCATION_ID_ROBERTS", "loc-123")

    with patch("httpx.AsyncClient.put", new_callable=AsyncMock) as mock_put:
        mock_put.return_value = _mock_response({"contact": {"id": "c-001"}})
        result = await update_contact.ainvoke({
            "business_id": "roberts",
            "contact_id": "c-001",
            "tags": ["hot-lead"],
        })

    assert result["contact_id"] == "c-001"
    assert result["updated"] is True


# ── move_opportunity_stage ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_move_opportunity_stage_valid(monkeypatch):
    monkeypatch.setenv("GHL_TOKEN_ROBERTS", "tok")
    monkeypatch.setenv("GHL_LOCATION_ID_ROBERTS", "loc-123")

    with patch("httpx.AsyncClient.put", new_callable=AsyncMock) as mock_put:
        mock_put.return_value = _mock_response({"opportunity": {"id": "opp-001"}})
        result = await move_opportunity_stage.ainvoke({
            "business_id": "roberts",
            "opportunity_id": "opp-001",
            "stage_name": "call_booked",
        })

    assert result["opportunity_id"] == "opp-001"
    assert result["stage"] == "call_booked"
    assert result["updated"] is True


@pytest.mark.asyncio
async def test_move_opportunity_stage_invalid_stage(monkeypatch):
    monkeypatch.setenv("GHL_TOKEN_ROBERTS", "tok")
    monkeypatch.setenv("GHL_LOCATION_ID_ROBERTS", "loc-123")

    with pytest.raises(ValueError, match="Unknown stage"):
        await move_opportunity_stage.ainvoke({
            "business_id": "roberts",
            "opportunity_id": "opp-001",
            "stage_name": "nonexistent_stage",
        })


# ── create_opportunity ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_opportunity_returns_id(monkeypatch):
    monkeypatch.setenv("GHL_TOKEN_ROBERTS", "tok")
    monkeypatch.setenv("GHL_LOCATION_ID_ROBERTS", "loc-123")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_response({"opportunity": {"id": "opp-new-001"}})
        result = await create_opportunity.ainvoke({
            "business_id": "roberts",
            "contact_id": "c-001",
            "name": "Patio renovation",
            "monetary_value": 12000.0,
        })

    assert result["opportunity_id"] == "opp-new-001"
    assert result["contact_id"] == "c-001"


# ── get_contact_opportunities ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_contact_opportunities_returns_list(monkeypatch):
    monkeypatch.setenv("GHL_TOKEN_ROBERTS", "tok")
    monkeypatch.setenv("GHL_LOCATION_ID_ROBERTS", "loc-123")

    opps = [{"id": "opp-001", "name": "Patio", "status": "open"}]

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response({"opportunities": opps})
        result = await get_contact_opportunities.ainvoke({
            "business_id": "roberts",
            "contact_id": "c-001",
        })

    assert len(result) == 1
    assert result[0]["id"] == "opp-001"
