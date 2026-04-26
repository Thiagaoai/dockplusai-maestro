from __future__ import annotations

from typing import Any

import httpx
from bs4 import BeautifulSoup

from maestro.config import Settings
from maestro.services.tavily import BAD_EMAIL_PREFIXES, EMAIL_RE, USER_AGENT, WebProspect


class GooglePlacesError(RuntimeError):
    pass


class GooglePlacesProspectFinder:
    SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

    def __init__(self, settings: Settings, timeout_seconds: int = 30) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds

    async def search_prospects(
        self,
        target: str,
        locations: list[str],
        max_results_per_location: int = 10,
    ) -> list[WebProspect]:
        if not self.settings.google_maps_api_key:
            raise GooglePlacesError("GOOGLE_MAPS_API_KEY not set")

        prospects: list[WebProspect] = []
        seen_emails: set[str] = set()
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            for location in locations:
                response = await client.get(
                    self.SEARCH_URL,
                    params={
                        "query": self._query(target, location),
                        "key": self.settings.google_maps_api_key,
                        "language": "en",
                        "region": "us",
                        "type": "establishment",
                    },
                )
                if response.status_code >= 400:
                    raise GooglePlacesError(
                        f"Google Places request failed: {response.status_code}: {response.text[:200]}"
                    )
                for place in response.json().get("results", [])[:max_results_per_location]:
                    for p in await self._prospects_from_place(client, place, target, location):
                        key = p.email.casefold()
                        if key not in seen_emails:
                            seen_emails.add(key)
                            prospects.append(p)
        return prospects

    def _query(self, target: str, location: str) -> str:
        normalized = target.strip().casefold()
        if normalized in {"hoa", "hoas", "homeowners association"}:
            return f"HOA homeowners association property management {location} MA"
        return f"{target} {location} MA"

    async def _prospects_from_place(
        self,
        client: httpx.AsyncClient,
        place: dict[str, Any],
        target: str,
        location: str,
    ) -> list[WebProspect]:
        name = place.get("name", "")
        website = place.get("website", "")
        address = place.get("formatted_address", "")

        if not website and place.get("place_id"):
            website = await self._get_website(client, place["place_id"])

        if not website:
            return []

        emails = await self._emails_from_site(client, website)
        return [
            WebProspect(
                name=name,
                email=email,
                source_url=website,
                source_title=name,
                verification_note=(
                    f"Google Places: {name} ({address}) — email found on {website}"
                ),
                location=location,
                target=target,
                raw=place,
            )
            for email in emails
        ]

    async def _get_website(self, client: httpx.AsyncClient, place_id: str) -> str:
        try:
            r = await client.get(
                self.DETAILS_URL,
                params={
                    "place_id": place_id,
                    "fields": "website",
                    "key": self.settings.google_maps_api_key,
                },
            )
            if r.status_code < 400:
                return r.json().get("result", {}).get("website", "")
        except httpx.HTTPError:
            pass
        return ""

    async def _emails_from_site(self, client: httpx.AsyncClient, url: str) -> list[str]:
        try:
            r = await client.get(url)
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
