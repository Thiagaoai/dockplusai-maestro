"""Unit tests for Hunter.io enrichment tool."""

from unittest.mock import AsyncMock, MagicMock, patch

from maestro.config import get_settings
from maestro.tools._enrichment.hunter import domain_search, find_email, verify_email


class TestHunterNoKey:
    """Tests when HUNTER_API_KEY is missing."""

    async def test_find_email_returns_none_when_no_api_key(self):
        result = await find_email(first_name="John", last_name="Doe", domain="acme.com")

        assert result["source"] == "hunter"
        assert result["email"] is None
        assert result["confidence"] is None

    async def test_verify_email_returns_unknown_when_no_api_key(self):
        result = await verify_email(email="john@acme.com")

        assert result["source"] == "hunter"
        assert result["status"] == "unknown"
        assert result["score"] is None

    async def test_domain_search_returns_empty_when_no_api_key(self):
        result = await domain_search(domain="acme.com")

        assert result["source"] == "hunter"
        assert result["emails"] == []
        assert result["total"] == 0


class TestHunterWithMock:
    """Tests with mocked HTTP responses."""

    def _enable_hunter(self, monkeypatch):
        monkeypatch.setenv("HUNTER_API_KEY", "test-hunter-key")
        get_settings.cache_clear()

    def _mock_response(self, json_data):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json = lambda: json_data
        return response

    async def test_find_email_returns_data(self, monkeypatch):
        self._enable_hunter(monkeypatch)

        mock_data = {
            "data": {
                "email": "jane.smith@acme.com",
                "score": 92,
                "position": "VP of Engineering",
                "sources": [{"uri": "https://acme.com/team"}],
            }
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = self._mock_response(mock_data)

            result = await find_email(
                first_name="Jane", last_name="Smith", domain="acme.com"
            )

        assert result["email"] == "jane.smith@acme.com"
        assert result["confidence"] == 92
        assert result["position"] == "VP of Engineering"
        assert result["url"] == "https://acme.com/team"

    async def test_verify_email_returns_status(self, monkeypatch):
        self._enable_hunter(monkeypatch)

        mock_data = {
            "data": {
                "status": "valid",
                "result": "deliverable",
                "score": 95,
                "regexp": True,
                "gibberish": False,
                "disposable": False,
                "webmail": False,
                "mx_records": True,
                "smtp_server": True,
                "smtp_check": True,
                "accept_all": False,
                "block": False,
            }
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = self._mock_response(mock_data)

            result = await verify_email(email="jane@acme.com")

        assert result["status"] == "valid"
        assert result["result"] == "deliverable"
        assert result["score"] == 95
        assert result["disposable"] is False

    async def test_domain_search_returns_emails(self, monkeypatch):
        self._enable_hunter(monkeypatch)

        mock_data = {
            "data": {
                "domain": "acme.com",
                "pattern": "{first}.{last}",
                "emails_count": 2,
                "emails": [
                    {
                        "value": "jane.smith@acme.com",
                        "confidence": 92,
                        "first_name": "Jane",
                        "last_name": "Smith",
                        "position": "VP of Engineering",
                        "department": "engineering",
                        "linkedin": "https://linkedin.com/in/janesmith",
                        "phone_number": "+1-555-0100",
                        "type": "personal",
                    },
                    {
                        "value": "john.doe@acme.com",
                        "confidence": 88,
                        "first_name": "John",
                        "last_name": "Doe",
                        "position": "CEO",
                        "department": "executive",
                        "type": "professional",
                    },
                ],
            }
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = self._mock_response(mock_data)

            result = await domain_search(domain="acme.com", limit=5)

        assert len(result["emails"]) == 2
        assert result["pattern"] == "{first}.{last}"
        assert result["total"] == 2
        assert result["emails"][0]["email"] == "jane.smith@acme.com"
        assert result["emails"][0]["department"] == "engineering"
        assert result["emails"][0]["type"] == "personal"
