from __future__ import annotations

from typing import Any

import httpx
from bs4 import BeautifulSoup

from maestro.config import Settings
from maestro.services.tavily import BAD_EMAIL_PREFIXES, EMAIL_RE, USER_AGENT, WebProspect

APOLLO_SEARCH_URL = "https://api.apollo.io/v1/mixed_companies/search"


class ApolloWebError(RuntimeError):
    pass


class ApolloWebProspectFinder:
    """Uses Apollo organization search to find companies for Roberts prospecting.

    Searches by keyword + location, then scrapes each org's website for email.
    Works even on free Apollo plans since it uses organization search, not people.
    """

    def __init__(self, settings: Settings, timeout_seconds: int = 30) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds

    async def search_prospects(
        self,
        target: str,
        locations: list[str],
        max_results_per_location: int = 10,
    ) -> list[WebProspect]:
        if not self.settings.apollo_api_key:
            raise ApolloWebError("APOLLO_API_KEY not set")

        org_locations = [f"{loc}, Massachusetts, United States" for loc in locations]
        payload = {
            "q_keywords": " ".join(self._keywords(target)),
            "organization_locations": org_locations,
            "per_page": max_results_per_location * len(locations),
            "page": 1,
        }

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            r = await client.post(
                APOLLO_SEARCH_URL,
                json=payload,
                headers={
                    "X-Api-Key": self.settings.apollo_api_key,
                    "Content-Type": "application/json",
                },
            )
            if r.status_code == 422:
                raise ApolloWebError("Apollo organization search requires paid plan (422)")
            if r.status_code >= 400:
                raise ApolloWebError(
                    f"Apollo search failed: {r.status_code}: {r.text[:200]}"
                )

            organizations: list[dict[str, Any]] = r.json().get("organizations", [])

            prospects: list[WebProspect] = []
            seen_emails: set[str] = set()
            for org in organizations:
                website = org.get("website_url") or org.get("primary_domain") or ""
                if website and not website.startswith("http"):
                    website = f"https://{website}"
                if not website:
                    continue

                name = org.get("name", "")
                city = org.get("city", "")
                state = org.get("state", "")
                location = self._best_location(city, state, locations)

                for email in await self._emails_from_site(client, website):
                    key = email.casefold()
                    if key in seen_emails:
                        continue
                    seen_emails.add(key)
                    prospects.append(
                        WebProspect(
                            name=name,
                            email=key,
                            source_url=website,
                            source_title=name,
                            verification_note=(
                                f"Apollo org search for '{target}': {name} in {city}, {state}"
                            ),
                            location=location,
                            target=target,
                            raw=org,
                        )
                    )
        return prospects

    def _keywords(self, target: str) -> list[str]:
        normalized = target.strip().casefold()
        if normalized in {"hoa", "hoas", "homeowners association"}:
            return ["HOA", "homeowners association", "property management", "condominium"]
        return [target.strip()]

    def _best_location(self, city: str, state: str, locations: list[str]) -> str:
        combined = f"{city} {state}".casefold()
        for loc in locations:
            if any(part.strip().casefold() in combined for part in loc.split(",")):
                return loc
        return locations[0] if locations else "Cape Cod"

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
