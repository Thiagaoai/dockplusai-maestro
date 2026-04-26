from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from maestro.config import Settings
from maestro.services.tavily import BAD_EMAIL_PREFIXES, EMAIL_RE, USER_AGENT, WebProspect

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
_MODEL = "sonar"

_SKIP_DOMAINS = {
    "yelp.com", "facebook.com", "linkedin.com", "instagram.com",
    "twitter.com", "x.com", "google.com", "wikipedia.org", "bbb.org",
    "angi.com", "houzz.com", "yellowpages.com", "mapquest.com",
    "foursquare.com", "nextdoor.com", "tripadvisor.com", "apartments.com",
    "zillow.com", "realtor.com", "trulia.com",
}

_URL_RE = re.compile(r'https?://[^\s\'"<>()\]]+')


class PerplexityError(RuntimeError):
    pass


class PerplexityProspectFinder:
    """Uses Perplexity sonar to discover businesses, then scrapes their sites for emails.

    Perplexity returns `citations` — actual source URLs — which map directly to
    business websites. Much cleaner signal than raw search snippets.
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
        if not self.settings.perplexity_api_key:
            raise PerplexityError("PERPLEXITY_API_KEY not set")

        prospects: list[WebProspect] = []
        seen_emails: set[str] = set()

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            for location in locations:
                urls = await self._search_urls(client, target, location)
                for url in urls[:max_results_per_location]:
                    for email in await self._emails_from_site(client, url):
                        key = email.casefold()
                        if key in seen_emails:
                            continue
                        seen_emails.add(key)
                        prospects.append(
                            WebProspect(
                                name=url,
                                email=key,
                                source_url=url,
                                source_title=url,
                                verification_note=f"Perplexity sonar search for '{target}' in {location}",
                                location=location,
                                target=target,
                                raw={"url": url, "location": location},
                            )
                        )

        return prospects

    async def _search_urls(
        self, client: httpx.AsyncClient, target: str, location: str
    ) -> list[str]:
        headers = {
            "Authorization": f"Bearer {self.settings.perplexity_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": _MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a business research assistant. "
                        "Return only a plain numbered list of businesses with their official website URLs. "
                        "No markdown, no extra explanation."
                    ),
                },
                {"role": "user", "content": self._build_prompt(target, location)},
            ],
        }
        try:
            r = await client.post(PERPLEXITY_URL, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise PerplexityError(f"Perplexity request failed: {exc}") from exc

        if r.status_code >= 400:
            raise PerplexityError(f"Perplexity API error {r.status_code}: {r.text[:200]}")

        data = r.json()
        citations: list[str] = data.get("citations", [])
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        seen: set[str] = set()
        results: list[str] = []

        for raw_url in [*citations, *_URL_RE.findall(text)]:
            clean = self._clean_url(raw_url)
            if clean and clean not in seen:
                seen.add(clean)
                results.append(clean)

        return results

    def _build_prompt(self, target: str, location: str) -> str:
        normalized = target.strip().casefold()
        if normalized in {"hoa", "hoas", "homeowners association"}:
            return (
                f"List homeowners associations (HOA), condo associations, and property management "
                f"companies in {location}, Massachusetts. Include each organization's official website URL."
            )
        return (
            f"List {target} companies and organizations in {location}, Massachusetts. "
            f"Include each organization's official website URL."
        )

    def _clean_url(self, url: str) -> str | None:
        url = url.rstrip(".,;:)\"'")
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return None
            domain = parsed.netloc.lower().lstrip("www.")
            if any(skip in domain for skip in _SKIP_DOMAINS):
                return None
            return f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            return None

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
