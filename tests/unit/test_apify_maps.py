"""Unit tests for ApifyProspectFinder — Google Maps scraping via Apify."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maestro.config import get_settings
from maestro.services.apify_maps import ApifyError, ApifyProspectFinder


def _make_finder(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "test-apify-token")
    get_settings.cache_clear()
    settings = get_settings()
    return ApifyProspectFinder(settings)


def _make_place_item(
    title="Cape Cod Property Mgmt",
    website="https://capecodpm.com",
    emails=None,
    address="123 Main St, Falmouth, MA",
):
    return {
        "title": title,
        "website": website,
        "emails": [{"email": e} for e in (emails or ["info@capecodpm.com"])],
        "address": address,
        "cid": "12345",
    }


class TestApifyNoToken:
    async def test_raises_when_no_token(self, monkeypatch):
        monkeypatch.setenv("APIFY_TOKEN", "")
        get_settings.cache_clear()
        settings = get_settings()
        finder = ApifyProspectFinder(settings)

        with pytest.raises(ApifyError, match="APIFY_TOKEN not set"):
            await finder.search_prospects("hoa", ["Falmouth"])


class TestApifyQuery:
    def test_hoa_query_expands_to_full_term(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        q = finder._query("hoa", "Falmouth")
        assert "HOA" in q or "homeowners association" in q.lower()
        assert "Falmouth" in q
        assert "MA" in q

    def test_vacation_rental_passes_through(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        q = finder._query("vacation rental", "Provincetown")
        assert "vacation rental" in q.lower()
        assert "Provincetown" in q

    def test_marina_passes_through(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        q = finder._query("marina", "Chatham")
        assert "marina" in q.lower()
        assert "Chatham" in q


class TestApifyEmailExtraction:
    def test_extracts_emails_from_emails_field(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        item = _make_place_item(emails=["info@hoa.org", "manager@hoa.org"])
        emails = finder._emails_from_item(item)
        assert "info@hoa.org" in emails
        assert "manager@hoa.org" in emails

    def test_filters_bad_email_prefixes(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        item = _make_place_item(emails=["noreply@example.com", "info@goodhoa.org"])
        emails = finder._emails_from_item(item)
        assert "noreply@example.com" not in emails
        assert "info@goodhoa.org" in emails

    def test_falls_back_to_description_regex(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        item = {
            "title": "Barnstable HOA",
            "website": "",
            "emails": [],
            "description": "Contact us at board@barnstablehoa.org for inquiries.",
            "address": "Barnstable, MA",
        }
        emails = finder._emails_from_item(item)
        assert "board@barnstablehoa.org" in emails

    def test_returns_empty_when_no_emails(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        item = {"title": "No Email Co", "website": "https://noemail.com", "emails": [], "description": ""}
        emails = finder._emails_from_item(item)
        assert emails == []


class TestApifyLocationGuess:
    def test_guesses_location_from_address(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        item = {"address": "456 Shore Rd, Chatham, MA"}
        loc = finder._guess_location(item, ["Falmouth", "Chatham", "Barnstable"])
        assert loc == "Chatham"

    def test_falls_back_to_first_location(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        item = {"address": "999 Unknown Ave, Somewhere, AZ"}
        loc = finder._guess_location(item, ["Falmouth", "Chatham"])
        assert loc == "Falmouth"

    def test_returns_cape_cod_when_no_locations(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        item = {"address": "999 Anywhere"}
        loc = finder._guess_location(item, [])
        assert loc == "Cape Cod"


class TestApifyFullSearch:
    async def test_successful_run_returns_prospects(self, monkeypatch):
        finder = _make_finder(monkeypatch)

        run_response = MagicMock()
        run_response.status_code = 200
        run_response.json = lambda: {
            "data": {"id": "run_abc", "defaultDatasetId": "ds_xyz"}
        }

        status_response = MagicMock()
        status_response.status_code = 200
        status_response.json = lambda: {"data": {"status": "SUCCEEDED"}}

        dataset_response = MagicMock()
        dataset_response.status_code = 200
        dataset_response.json = lambda: [_make_place_item()]

        call_count = {"n": 0}

        async def mock_request(url, **kwargs):
            call_count["n"] += 1
            if "actor-runs" in url and call_count["n"] == 1:
                return run_response
            if "actor-runs" in url:
                return status_response
            if "datasets" in url:
                return dataset_response
            return status_response

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=run_response)
        mock_client.get = AsyncMock(side_effect=lambda url, **kw: (
            status_response if "actor-runs" in url else dataset_response
        ))

        with patch("maestro.services.apify_maps.httpx.AsyncClient", return_value=mock_client):
            with patch.object(finder, "_wait_for_run", new=AsyncMock(return_value=None)):
                with patch.object(
                    finder,
                    "_fetch_dataset",
                    new=AsyncMock(return_value=[_make_place_item()]),
                ):
                    prospects = await finder.search_prospects("hoa", ["Falmouth"])

        assert len(prospects) == 1
        assert prospects[0].email == "info@capecodpm.com"
        assert prospects[0].target == "hoa"

    async def test_deduplicates_emails(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        item1 = _make_place_item(title="HOA 1", emails=["shared@hoa.org"])
        item2 = _make_place_item(title="HOA 2", emails=["shared@hoa.org"])

        with patch("maestro.services.apify_maps.httpx.AsyncClient"):
            with patch.object(finder, "_wait_for_run", new=AsyncMock(return_value=None)):
                with patch.object(
                    finder,
                    "_fetch_dataset",
                    new=AsyncMock(return_value=[item1, item2]),
                ):
                    mock_run = MagicMock()
                    mock_run.status_code = 200
                    mock_run.json = lambda: {"data": {"id": "r1", "defaultDatasetId": "d1"}}
                    mock_client = MagicMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client.post = AsyncMock(return_value=mock_run)

                    with patch("maestro.services.apify_maps.httpx.AsyncClient", return_value=mock_client):
                        prospects = await finder.search_prospects("hoa", ["Falmouth"])

        emails = [p.email for p in prospects]
        assert emails.count("shared@hoa.org") == 1

    async def test_raises_on_run_failure(self, monkeypatch):
        finder = _make_finder(monkeypatch)

        error_response = MagicMock()
        error_response.status_code = 401
        error_response.text = "Unauthorized"

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=error_response)

        with patch("maestro.services.apify_maps.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ApifyError, match="401"):
                await finder.search_prospects("hoa", ["Falmouth"])

    async def test_raises_on_run_timeout(self, monkeypatch):
        finder = _make_finder(monkeypatch)
        finder.timeout_seconds = 1

        with patch.object(finder, "_wait_for_run", new=AsyncMock(side_effect=ApifyError("timed out after 90s"))):
            run_response = MagicMock()
            run_response.status_code = 200
            run_response.json = lambda: {"data": {"id": "run_slow", "defaultDatasetId": "ds_1"}}
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=run_response)

            with patch("maestro.services.apify_maps.httpx.AsyncClient", return_value=mock_client):
                with pytest.raises(ApifyError, match="timed out"):
                    await finder.search_prospects("vacation rental", ["Chatham"])
