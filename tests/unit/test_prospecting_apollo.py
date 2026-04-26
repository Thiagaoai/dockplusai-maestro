"""Unit tests for Apollo-based DockPlus AI prospecting."""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from maestro.agents.prospecting import DOCKPLUS_ICP_TITLES, ProspectingAgent
from maestro.config import get_settings
from maestro.repositories.store import InMemoryStore


def _make_apollo_person(
    first="Jane",
    last="Smith",
    title="CEO",
    email="jane@acme.com",
    apollo_id=None,
):
    return {
        "apollo_id": apollo_id or str(uuid4()),
        "first_name": first,
        "last_name": last,
        "name": f"{first} {last}",
        "title": title,
        "email": email,
        "personal_email": None,
        "phone": "+1-555-0199",
        "linkedin_url": "https://linkedin.com/in/janesmith",
        "company": {
            "name": "Acme Corp",
            "website": "https://acme.com",
            "linkedin": None,
            "industry": "home services",
            "employee_count": 45,
        },
        "location": "Boston, MA",
    }


def _make_agent(monkeypatch):
    monkeypatch.setenv("APOLLO_API_KEY", "test-key")
    monkeypatch.setenv("DRY_RUN", "true")
    get_settings.cache_clear()
    settings = get_settings()
    store = InMemoryStore()
    return ProspectingAgent(settings=settings, store=store)


class TestPrepareApolloEmpty:
    async def test_returns_none_when_apollo_returns_empty(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        empty = {"source": "apollo", "people": [], "plan_limited": False, "pagination": {"page": 1, "per_page": 10, "total_entries": 0}}

        with patch("maestro.agents.prospecting.search_people", new=AsyncMock(return_value=empty)):
            approval, run = await agent.prepare_dockplusai_apollo_batch()

        assert approval is None
        assert run.business == "dockplusai"
        assert "empty" in run.output

    async def test_returns_none_when_plan_limited(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        limited = {"source": "apollo", "people": [], "plan_limited": True, "error": "API_INACCESSIBLE", "pagination": {}}

        with patch("maestro.agents.prospecting.search_people", new=AsyncMock(return_value=limited)):
            approval, run = await agent.prepare_dockplusai_apollo_batch()

        assert approval is None
        assert "plan_limited" in run.output


class TestPrepareApolloBatch:
    async def test_queues_prospects_and_returns_approval(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        person = _make_apollo_person()
        search_result = {
            "source": "apollo",
            "people": [person],
            "plan_limited": False,
            "pagination": {"page": 1, "per_page": 10, "total_entries": 1},
        }

        with patch("maestro.agents.prospecting.search_people", new=AsyncMock(return_value=search_result)):
            approval, run = await agent.prepare_dockplusai_apollo_batch()

        assert approval is not None
        assert approval.business == "dockplusai"
        assert approval.action == "prospecting_apollo_batch_send"
        assert len(approval.preview["prospects"]) == 1
        assert approval.preview["campaign"]["source"] == "apollo_people_search"

    async def test_approval_preview_has_email_templates(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        person = _make_apollo_person()
        search_result = {
            "source": "apollo",
            "people": [person],
            "plan_limited": False,
            "pagination": {"page": 1, "per_page": 10, "total_entries": 1},
        }

        with patch("maestro.agents.prospecting.search_people", new=AsyncMock(return_value=search_result)):
            approval, _ = await agent.prepare_dockplusai_apollo_batch()

        email = approval.preview["email"]
        assert "subject" in email
        assert "html" in email
        assert "text" in email
        assert "DockPlus" in email["html"]
        assert "Book a Free Audit" in email["html"]

    async def test_skips_people_without_email(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        no_email = _make_apollo_person(email=None)
        no_email["email"] = None
        no_email["personal_email"] = None
        has_email = _make_apollo_person(email="valid@company.com")

        search_result = {
            "source": "apollo",
            "people": [no_email, has_email],
            "plan_limited": False,
            "pagination": {"page": 1, "per_page": 10, "total_entries": 2},
        }

        with patch("maestro.agents.prospecting.search_people", new=AsyncMock(return_value=search_result)):
            approval, _ = await agent.prepare_dockplusai_apollo_batch()

        assert approval is not None
        assert len(approval.preview["prospects"]) == 1

    async def test_prospect_queue_status_set_to_drafted(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        person = _make_apollo_person()
        search_result = {
            "source": "apollo",
            "people": [person],
            "plan_limited": False,
            "pagination": {"page": 1, "per_page": 10, "total_entries": 1},
        }

        with patch("maestro.agents.prospecting.search_people", new=AsyncMock(return_value=search_result)):
            await agent.prepare_dockplusai_apollo_batch()

        drafted = [
            item for item in agent.store.prospect_queue
            if item.get("status") == "drafted" and item.get("source_type") == "apollo"
        ]
        assert len(drafted) == 1

    async def test_uses_default_icp_titles(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        mock_search = AsyncMock(return_value={"source": "apollo", "people": [], "plan_limited": False, "pagination": {}})

        with patch("maestro.agents.prospecting.search_people", new=mock_search):
            await agent.prepare_dockplusai_apollo_batch()

        called_titles = mock_search.call_args.kwargs["person_titles"]
        assert called_titles == DOCKPLUS_ICP_TITLES

    async def test_custom_titles_override_defaults(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        custom_titles = ["HOA Manager", "Property Manager"]
        mock_search = AsyncMock(return_value={"source": "apollo", "people": [], "plan_limited": False, "pagination": {}})

        with patch("maestro.agents.prospecting.search_people", new=mock_search):
            await agent.prepare_dockplusai_apollo_batch(person_titles=custom_titles)

        called_titles = mock_search.call_args.kwargs["person_titles"]
        assert called_titles == custom_titles


class TestDockplusEmailTemplates:
    def test_html_body_has_no_raw_url(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        html = agent._dockplus_html_body("DockPlus AI", "https://dockplus.ai")
        assert "https://dockplus.ai" in html
        assert "<script" not in html

    def test_text_body_includes_stop_opt_out(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        text = agent._dockplus_text_body("DockPlus AI", "https://dockplus.ai")
        assert "STOP" in text

    def test_subject_is_non_empty(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        assert len(agent._dockplus_subject()) > 5
