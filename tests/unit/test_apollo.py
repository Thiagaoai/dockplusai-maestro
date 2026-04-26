"""Unit tests for Apollo.io enrichment tool."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maestro.config import get_settings
from maestro.tools._enrichment.apollo import (
    enrich_lead,
    search_organizations,
    search_people,
)


class TestApolloNoKey:
    """Tests when APOLLO_API_KEY is missing."""

    async def test_enrich_lead_returns_none_when_no_api_key(self):
        result = await enrich_lead(name="John Doe", email="john@example.com")

        assert result["source"] == "apollo"
        assert result["person"] is None
        assert result["plan_limited"] is False
        assert result["input"]["name"] == "John Doe"

    async def test_search_people_returns_empty_when_no_api_key(self):
        result = await search_people(q_keywords="software engineer")

        assert result["source"] == "apollo"
        assert result["people"] == []
        assert result["plan_limited"] is False
        assert result["pagination"]["total_entries"] == 0

    async def test_search_orgs_returns_empty_when_no_api_key(self):
        result = await search_organizations(q_organization_name="Tesla")

        assert result["source"] == "apollo"
        assert result["organizations"] == []
        assert result["pagination"]["total_entries"] == 0


class TestApolloPlanLimited:
    """Tests when API key exists but plan does not include person endpoints."""

    def _enable_apollo(self, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "false")
        monkeypatch.setenv("APOLLO_API_KEY", "test-apollo-key")
        get_settings.cache_clear()

    async def test_enrich_lead_detects_plan_limit(self, monkeypatch):
        self._enable_apollo(monkeypatch)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MagicMock(
                json=lambda: {
                    "error": "api/v1/people/match is not accessible with this api_key",
                    "error_code": "API_INACCESSIBLE",
                }
            )

            result = await enrich_lead(name="Jane Smith", company_name="Acme Corp")

        assert result["plan_limited"] is True
        assert result["person"] is None
        assert "error" in result

    async def test_search_people_detects_plan_limit(self, monkeypatch):
        self._enable_apollo(monkeypatch)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MagicMock(
                json=lambda: {
                    "error": "api/v1/mixed_people/search is not accessible with this api_key",
                    "error_code": "API_INACCESSIBLE",
                }
            )

            result = await search_people(person_titles=["CEO"])

        assert result["plan_limited"] is True
        assert result["people"] == []


class TestApolloWithMock:
    """Tests with mocked HTTP responses (DRY_RUN=false + API key present)."""

    @pytest.fixture
    def mock_apollo_response(self):
        return {
            "person": {
                "id": "apollo_123",
                "first_name": "Jane",
                "last_name": "Smith",
                "title": "VP of Engineering",
                "email": "jane@acme.com",
                "personal_emails": ["jane.smith@gmail.com"],
                "phone_number": "+1-555-0199",
                "linkedin_url": "https://linkedin.com/in/janesmith",
                "city": "San Francisco",
                "state": "CA",
                "organization": {
                    "name": "Acme Corp",
                    "website_url": "https://acme.com",
                    "linkedin_url": "https://linkedin.com/company/acme",
                    "industry": "Software",
                    "estimated_num_employees": 500,
                },
            },
            "cached": False,
        }

    def _enable_apollo(self, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "false")
        monkeypatch.setenv("APOLLO_API_KEY", "test-apollo-key")
        get_settings.cache_clear()

    def _mock_response(self, json_data):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json = lambda: json_data
        return response

    async def test_enrich_lead_normalizes_person(self, monkeypatch, mock_apollo_response):
        self._enable_apollo(monkeypatch)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = self._mock_response(mock_apollo_response)

            result = await enrich_lead(name="Jane Smith", company_name="Acme Corp")

        person = result["person"]
        assert person is not None
        assert person["apollo_id"] == "apollo_123"
        assert person["name"] == "Jane Smith"
        assert person["email"] == "jane@acme.com"
        assert person["personal_email"] == "jane.smith@gmail.com"
        assert person["phone"] == "+1-555-0199"
        assert person["title"] == "VP of Engineering"
        assert person["company"]["name"] == "Acme Corp"
        assert person["company"]["employee_count"] == 500
        assert person["location"] == "San Francisco"
        assert result["cached"] is False

    async def test_search_people_returns_normalized_list(self, monkeypatch, mock_apollo_response):
        self._enable_apollo(monkeypatch)

        search_response = {
            "people": [mock_apollo_response["person"]],
            "page": 1,
            "per_page": 5,
            "total_entries": 1,
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = self._mock_response(search_response)

            result = await search_people(person_titles=["VP of Engineering"], per_page=5)

        assert len(result["people"]) == 1
        assert result["people"][0]["name"] == "Jane Smith"
        assert result["pagination"]["total_entries"] == 1
        assert result["pagination"]["per_page"] == 5

    async def test_search_organizations_returns_normalized_list(self, monkeypatch):
        self._enable_apollo(monkeypatch)

        org_response = {
            "organizations": [
                {
                    "id": "org_123",
                    "name": "Acme Corp",
                    "website_url": "https://acme.com",
                    "linkedin_url": "https://linkedin.com/company/acme",
                    "industry": "Software",
                    "estimated_num_employees": 500,
                    "annual_revenue_printed": "$50M",
                    "city": "San Francisco",
                    "state": "CA",
                    "phone": "+1-555-0100",
                }
            ],
            "page": 1,
            "per_page": 10,
            "total_entries": 1,
            "total_pages": 1,
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = self._mock_response(org_response)

            result = await search_organizations(q_organization_name="Acme Corp")

        assert len(result["organizations"]) == 1
        org = result["organizations"][0]
        assert org["name"] == "Acme Corp"
        assert org["industry"] == "Software"
        assert org["employee_count"] == 500
        assert org["revenue"] == "$50M"
        assert org["phone"] == "+1-555-0100"
        assert result["pagination"]["total_entries"] == 1
