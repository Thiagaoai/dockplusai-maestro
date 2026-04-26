from __future__ import annotations

from urllib.parse import urlparse

import httpx

from maestro.config import Settings
from maestro.services.tavily import BAD_EMAIL_PREFIXES, WebProspect


class HunterError(RuntimeError):
    pass


MIN_CONFIDENCE = 70

_AGGREGATOR_DOMAINS = {
    "marinas.com", "snagaslip.com", "usharbors.com", "boattrader.com",
    "activecaptain.com", "dockwa.com", "yachtworld.com", "boats.com",
    "yelp.com", "yellowpages.com", "tripadvisor.com", "google.com",
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com",
    "bing.com", "mapquest.com", "foursquare.com", "angi.com",
    "thumbtack.com", "homeadvisor.com", "capecodchamber.org",
    "findmarina.com", "marinemax.com", "boatdealers.com",
}


class HunterProspectFinder:
    """Discovers domains via Tavily, then enriches with Hunter.io domain-search."""

    HUNTER_URL = "https://api.hunter.io/v2/domain-search"

    def __init__(self, settings: Settings, timeout_seconds: int = 30) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds

    async def search_prospects(
        self,
        target: str,
        locations: list[str],
        max_results_per_location: int = 5,
    ) -> list[WebProspect]:
        if not self.settings.hunter_api_key:
            raise HunterError("HUNTER_API_KEY not set")

        domain_infos = await self._discover_domains(target, locations, max_results_per_location)

        prospects: list[WebProspect] = []
        seen_emails: set[str] = set()
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for info in domain_infos:
                for email, confidence in await self._hunter_emails(client, info["domain"]):
                    key = email.casefold()
                    if key in seen_emails:
                        continue
                    seen_emails.add(key)
                    prospects.append(
                        WebProspect(
                            name=info["name"],
                            email=key,
                            source_url=info["url"],
                            source_title=info["name"],
                            verification_note=(
                                f"Hunter.io domain-search {info['domain']} — confidence {confidence}%"
                            ),
                            location=info["location"],
                            target=target,
                            raw={"domain": info["domain"], "confidence": confidence},
                        )
                    )
        return prospects

    async def _discover_domains(
        self, target: str, locations: list[str], max_per_location: int
    ) -> list[dict]:
        if not self.settings.tavily_api_key:
            return []

        from maestro.services.tavily import TavilyProspectFinder

        tavily = TavilyProspectFinder(self.settings)
        infos: list[dict] = []
        seen: set[str] = set()

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for location in locations:
                payload = {
                    "query": tavily._query(target, location),
                    "search_depth": "basic",
                    "max_results": max_per_location,
                    "include_answer": False,
                    "include_raw_content": False,
                    "country": "united states",
                }
                try:
                    r = await client.post(
                        tavily.base_url,
                        json=payload,
                        headers={
                            "Authorization": f"Bearer {self.settings.tavily_api_key}",
                            "Content-Type": "application/json",
                        },
                    )
                    if r.status_code >= 400:
                        continue
                    for result in r.json().get("results", []):
                        url = str(result.get("url") or "")
                        domain = urlparse(url).netloc.replace("www.", "")
                        if not domain or domain in seen or domain in _AGGREGATOR_DOMAINS:
                            continue
                        seen.add(domain)
                        infos.append(
                            {
                                "domain": domain,
                                "url": url,
                                "name": str(result.get("title") or domain),
                                "location": location,
                            }
                        )
                except httpx.HTTPError:
                    continue
        return infos

    async def _hunter_emails(
        self, client: httpx.AsyncClient, domain: str
    ) -> list[tuple[str, int]]:
        try:
            r = await client.get(
                self.HUNTER_URL,
                params={"domain": domain, "api_key": self.settings.hunter_api_key, "limit": 10},
            )
            if r.status_code >= 400:
                return []
            results = []
            for item in r.json().get("data", {}).get("emails", []):
                email = (item.get("value") or "").casefold()
                confidence = item.get("confidence", 0)
                if email and confidence >= MIN_CONFIDENCE:
                    if not any(email.startswith(p) for p in BAD_EMAIL_PREFIXES):
                        results.append((email, confidence))
            return results
        except httpx.HTTPError:
            return []
