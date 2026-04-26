from __future__ import annotations

import asyncio
from typing import Any

import httpx
from bs4 import BeautifulSoup

from maestro.config import Settings
from maestro.services.tavily import BAD_EMAIL_PREFIXES, EMAIL_RE, USER_AGENT, WebProspect

ACTOR_RUN_URL = "https://api.apify.com/v2/acts/compass~crawler-google-places/runs"
ACTOR_RUN_STATUS_URL = "https://api.apify.com/v2/actor-runs/{run_id}"
DATASET_URL = "https://api.apify.com/v2/datasets/{dataset_id}/items"


class ApifyError(RuntimeError):
    pass


class ApifyProspectFinder:
    """Scrapes Google Maps via Apify's compass/crawler-google-places actor."""

    def __init__(self, settings: Settings, timeout_seconds: int = 300) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds

    async def search_prospects(
        self,
        target: str,
        locations: list[str],
        max_results_per_location: int = 20,
    ) -> list[WebProspect]:
        if not self.settings.apify_token:
            raise ApifyError("APIFY_TOKEN not set")

        search_strings = [self._query(target, loc) for loc in locations]
        run_input = {
            "searchStringsArray": search_strings,
            "maxCrawledPlacesPerSearch": max_results_per_location,
            "language": "en",
            "countryCode": "us",
            "includeWebResults": True,
            "scrapeContacts": True,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.apify_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(ACTOR_RUN_URL, json=run_input, headers=headers)
            if r.status_code >= 400:
                raise ApifyError(
                    f"Apify run failed: {r.status_code}: {r.text[:200]}"
                )
            run_data = r.json().get("data", {})
            run_id = run_data.get("id")
            dataset_id = run_data.get("defaultDatasetId")
            if not run_id:
                raise ApifyError("Apify returned no run ID")

            await self._wait_for_run(client, run_id, headers)
            items = await self._fetch_dataset(client, dataset_id, headers)

        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as web_client:
            prospects: list[WebProspect] = []
            seen_emails: set[str] = set()
            for item in items:
                location = self._guess_location(item, locations)
                name = item.get("title") or item.get("name") or "Unknown"
                website = item.get("website") or ""

                emails = self._emails_from_item(item)
                if not emails and website:
                    emails = await self._emails_from_site(web_client, website)

                for email in emails:
                    key = email.casefold()
                    if key in seen_emails:
                        continue
                    seen_emails.add(key)
                    prospects.append(
                        WebProspect(
                            name=name,
                            email=key,
                            source_url=website or f"https://maps.google.com/?cid={item.get('cid', '')}",
                            source_title=name,
                            verification_note=(
                                f"Apify Google Maps: {name} in {location}"
                            ),
                            location=location,
                            target=target,
                            raw=item,
                        )
                    )
        return prospects

    def _query(self, target: str, location: str) -> str:
        from maestro.utils.verticals import expand_target

        terms = expand_target(target)
        return f"{terms[0]} {location} MA"

    async def _wait_for_run(
        self, client: httpx.AsyncClient, run_id: str, headers: dict, max_wait: int = 300
    ) -> None:
        url = ACTOR_RUN_STATUS_URL.format(run_id=run_id)
        elapsed = 0
        while elapsed < max_wait:
            await asyncio.sleep(5)
            elapsed += 5
            try:
                r = await client.get(url, headers=headers)
                if r.status_code >= 400:
                    continue
                status = r.json().get("data", {}).get("status", "")
                if status == "SUCCEEDED":
                    return
                if status in {"FAILED", "ABORTED", "TIMED-OUT"}:
                    raise ApifyError(f"Apify run {run_id} ended with status {status}")
            except httpx.HTTPError:
                continue
        raise ApifyError(f"Apify run {run_id} timed out after {max_wait}s")

    async def _fetch_dataset(
        self, client: httpx.AsyncClient, dataset_id: str, headers: dict
    ) -> list[dict[str, Any]]:
        try:
            r = await client.get(
                DATASET_URL.format(dataset_id=dataset_id),
                headers=headers,
                params={"format": "json", "limit": 200},
            )
            if r.status_code >= 400:
                return []
            data = r.json()
            return data if isinstance(data, list) else []
        except httpx.HTTPError:
            return []

    def _emails_from_item(self, item: dict[str, Any]) -> list[str]:
        emails: list[str] = []
        for e in item.get("emails", []):
            raw = e.get("email") if isinstance(e, dict) else str(e)
            email = (raw or "").casefold()
            if email and not any(email.startswith(p) for p in BAD_EMAIL_PREFIXES):
                emails.append(email)
        if not emails:
            text = str(item.get("description") or "") + " " + str(item.get("website") or "")
            for m in EMAIL_RE.findall(text):
                email = m.casefold()
                if not any(email.startswith(p) for p in BAD_EMAIL_PREFIXES):
                    emails.append(email)
        return emails

    async def _emails_from_site(self, client: httpx.AsyncClient, url: str) -> list[str]:
        try:
            r = await client.get(url, timeout=15.0)
            if r.status_code >= 400 or "text/html" not in r.headers.get("content-type", ""):
                return []
            html = r.text
        except httpx.HTTPError:
            return []
        soup = BeautifulSoup(html, "html.parser")
        emails: list[str] = []
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if href.lower().startswith("mailto:"):
                email = href.replace("mailto:", "").split("?")[0].strip().casefold()
                if email and not any(email.startswith(p) for p in BAD_EMAIL_PREFIXES):
                    emails.append(email)
        if not emails:
            for m in EMAIL_RE.findall(soup.get_text()):
                email = m.casefold()
                if not any(email.startswith(p) for p in BAD_EMAIL_PREFIXES) and email not in emails:
                    emails.append(email)
        return emails

    def _guess_location(self, item: dict[str, Any], locations: list[str]) -> str:
        address = str(item.get("address") or item.get("street") or "").casefold()
        for loc in locations:
            if loc.casefold() in address:
                return loc
        return locations[0] if locations else "Cape Cod"
