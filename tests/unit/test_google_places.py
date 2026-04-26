"""Unit tests for GooglePlacesProspectFinder — Roberts Landscape / Cape Cod."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maestro.config import get_settings
from maestro.services.google_places import GooglePlacesError, GooglePlacesProspectFinder


def _make_place(name="Cape Cod HOA", website="https://capecodhoa.org", place_id="abc123"):
    return {
        "name": name,
        "website": website,
        "formatted_address": f"{name}, Falmouth, MA 02540",
        "place_id": place_id,
    }


def _html_with_email(email="info@capecodhoa.org"):
    return f'<html><body><a href="mailto:{email}">Contact</a></body></html>'


def _make_finder(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    get_settings.cache_clear()
    settings = get_settings()
    return GooglePlacesProspectFinder(settings)


class TestGooglePlacesNoKey:
    async def test_raises_when_no_api_key(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "")
        get_settings.cache_clear()
        settings = get_settings()
        finder = GooglePlacesProspectFinder(settings)

        with pytest.raises(GooglePlacesError, match="GOOGLE_MAPS_API_KEY not set"):
            await finder.search_prospects("hoa", ["Falmouth"])


class TestGooglePlacesQuery:
    def test_hoa_query_includes_keywords(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        q = finder._query("hoa", "Falmouth")
        assert "HOA" in q or "homeowners association" in q.lower()
        assert "Falmouth" in q

    def test_hoas_alias_normalizes(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        q = finder._query("hoas", "Barnstable")
        assert "HOA" in q or "homeowners association" in q.lower()

    def test_generic_target_passes_through(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        q = finder._query("marina", "Chatham")
        assert "marina" in q.lower()
        assert "Chatham" in q

    def test_vacation_rental_query(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        q = finder._query("vacation rental", "Provincetown")
        assert "vacation rental" in q.lower()
        assert "Provincetown" in q


class TestGooglePlacesEmailExtraction:
    async def test_extracts_mailto_link(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        html = _html_with_email("info@capecodhoa.org")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = html

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        emails = await finder._emails_from_site(mock_client, "https://capecodhoa.org")
        assert emails == ["info@capecodhoa.org"]

    async def test_falls_back_to_regex_in_body(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        html = "<html><body>Contact us at manager@falmouth-hoa.org for questions.</body></html>"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = html

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        emails = await finder._emails_from_site(mock_client, "https://falmouth-hoa.org")
        assert "manager@falmouth-hoa.org" in emails

    async def test_filters_bad_prefixes(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        html = '<a href="mailto:noreply@example.com">x</a><a href="mailto:info@realhoa.org">y</a>'
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = html

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        emails = await finder._emails_from_site(mock_client, "https://realhoa.org")
        assert "noreply@example.com" not in emails
        assert "info@realhoa.org" in emails

    async def test_returns_empty_on_http_error(self, monkeypatch):
        import httpx

        finder = _make_finder(monkeypatch)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("timeout"))

        emails = await finder._emails_from_site(mock_client, "https://broken.example.com")
        assert emails == []

    async def test_returns_empty_on_non_html_response(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"email":"hidden@example.com"}'

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        emails = await finder._emails_from_site(mock_client, "https://api.example.com/data")
        assert emails == []


class TestGooglePlacesWebsiteFallback:
    async def test_fetches_website_from_place_details_if_missing(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        details_response = MagicMock()
        details_response.status_code = 200
        details_response.json = lambda: {"result": {"website": "https://hoa-barnstable.org"}}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=details_response)

        website = await finder._get_website(mock_client, "place_123")
        assert website == "https://hoa-barnstable.org"

    async def test_returns_empty_string_on_details_failure(self, monkeypatch):
        import httpx

        finder = _make_finder(monkeypatch)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("network error"))

        website = await finder._get_website(mock_client, "place_456")
        assert website == ""


class TestGooglePlacesFullSearch:
    async def test_full_search_returns_prospects(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        place = _make_place()

        places_response = MagicMock()
        places_response.status_code = 200
        places_response.json = lambda: {"results": [place]}

        email_html_response = MagicMock()
        email_html_response.status_code = 200
        email_html_response.headers = {"content-type": "text/html"}
        email_html_response.text = _html_with_email("info@capecodhoa.org")

        call_count = {"n": 0}

        async def mock_get(url, **kwargs):
            call_count["n"] += 1
            if "textsearch" in url or "place/text" in url:
                return places_response
            return email_html_response

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=mock_get)

        with patch("maestro.services.google_places.httpx.AsyncClient", return_value=mock_client):
            prospects = await finder.search_prospects("hoa", ["Falmouth"])

        assert len(prospects) >= 1
        assert prospects[0].email == "info@capecodhoa.org"
        assert prospects[0].location == "Falmouth"
        assert prospects[0].target == "hoa"

    async def test_deduplicates_emails_across_locations(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        place = _make_place()

        places_response = MagicMock()
        places_response.status_code = 200
        places_response.json = lambda: {"results": [place]}

        email_html_response = MagicMock()
        email_html_response.status_code = 200
        email_html_response.headers = {"content-type": "text/html"}
        email_html_response.text = _html_with_email("shared@capecodhoa.org")

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=places_response)

        # Override _prospects_from_place to return same email for both locations
        async def _fake_prospects(client, place, target, location):
            from maestro.services.tavily import WebProspect
            return [WebProspect(
                name="Cape Cod HOA",
                email="shared@capecodhoa.org",
                source_url="https://capecodhoa.org",
                source_title="Cape Cod HOA",
                verification_note="test",
                location=location,
                target=target,
                raw={},
            )]

        finder._prospects_from_place = _fake_prospects

        with patch("maestro.services.google_places.httpx.AsyncClient", return_value=mock_client):
            prospects = await finder.search_prospects("hoa", ["Falmouth", "Barnstable"])

        emails = [p.email for p in prospects]
        assert emails.count("shared@capecodhoa.org") == 1

    async def test_raises_on_api_error(self, monkeypatch):
        finder = _make_finder(monkeypatch)

        error_response = MagicMock()
        error_response.status_code = 403
        error_response.text = "REQUEST_DENIED"

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=error_response)

        with patch("maestro.services.google_places.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(GooglePlacesError, match="403"):
                await finder.search_prospects("hoa", ["Falmouth"])
