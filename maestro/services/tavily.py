from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from maestro.config import Settings


class TavilyError(RuntimeError):
    pass


@dataclass(frozen=True)
class WebProspect:
    name: str
    email: str
    source_url: str
    source_title: str
    verification_note: str
    location: str
    target: str
    raw: dict[str, Any]


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
BAD_EMAIL_PREFIXES = ("example@", "privacy@", "noreply@", "no-reply@", "donotreply@")
CONTACT_LINK_RE = re.compile(r"(contact|about|management|team|board|association)", re.IGNORECASE)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


class TavilyProspectFinder:
    def __init__(
        self,
        settings: Settings,
        base_url: str = "https://api.tavily.com/search",
        timeout_seconds: int = 30,
    ) -> None:
        self.settings = settings
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    async def search_prospects(
        self,
        target: str,
        locations: list[str],
        max_results_per_location: int = 5,
        max_prospects: int | None = None,
    ) -> list[WebProspect]:
        if not self.settings.tavily_api_key:
            raise TavilyError("TAVILY_API_KEY not set")

        prospects: list[WebProspect] = []
        seen_emails: set[str] = set()
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
        ) as client:
            for location in locations:
                payload = {
                    "query": self._query(target, location),
                    "search_depth": "advanced",
                    "max_results": max_results_per_location,
                    "include_answer": False,
                    "include_raw_content": "text",
                    "include_images": False,
                    "country": "united states",
                }
                response = await client.post(
                    self.base_url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.settings.tavily_api_key}",
                        "Content-Type": "application/json",
                    },
                )
                if response.status_code >= 400:
                    raise TavilyError(
                        f"Tavily request failed: {response.status_code}: {response.text[:300]}"
                    )
                for result in response.json().get("results", []):
                    source_text = await self._source_text(client, str(result.get("url") or ""))
                    for prospect in self._prospects_from_result(
                        target,
                        location,
                        result,
                        source_text=source_text,
                    ):
                        email_key = prospect.email.casefold()
                        if email_key in seen_emails:
                            continue
                        seen_emails.add(email_key)
                        prospects.append(prospect)
                        if max_prospects is not None and len(prospects) >= max_prospects:
                            return prospects
        return prospects

    def _query(self, target: str, location: str) -> str:
        from maestro.utils.verticals import expand_target

        terms = expand_target(target)
        target_terms = " OR ".join(f'"{t}"' for t in terms[:3])
        return f"{target_terms} contact email {location} MA official website"

    def _prospects_from_result(
        self,
        target: str,
        location: str,
        result: dict[str, Any],
        source_text: str = "",
    ) -> list[WebProspect]:
        source_url = str(result.get("url") or "")
        title = str(result.get("title") or "Web prospect").strip()
        content = " ".join(
            str(result.get(key) or "") for key in ("title", "content", "raw_content")
        )
        content = f"{content}\n{source_text}"
        prospects: list[WebProspect] = []
        for email in EMAIL_RE.findall(content):
            email = email.strip().strip(".,;:()[]<>").casefold()
            if self._skip_email(email):
                continue
            prospects.append(
                WebProspect(
                    name=title,
                    email=email,
                    source_url=source_url,
                    source_title=title,
                    verification_note=(
                        f"Tavily result for {target} in {location} found this email on "
                        f"{source_url or 'the source page'}."
                    ),
                    location=location,
                    target=target,
                    raw=result,
                )
            )
        return prospects

    def _skip_email(self, email: str) -> bool:
        return any(email.startswith(prefix) for prefix in BAD_EMAIL_PREFIXES)

    async def _source_text(self, client: httpx.AsyncClient, url: str) -> str:
        if not url.startswith(("http://", "https://")):
            return ""
        pages: list[tuple[str, str]] = []
        first_html = await self._fetch_html(client, url)
        if first_html:
            pages.append((url, first_html))
            pages.extend(await self._contact_pages(client, url, first_html))
        text_parts: list[str] = []
        for page_url, html in pages[:4]:
            soup = BeautifulSoup(html, "html.parser")
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            mailtos = [
                link.get("href", "").replace("mailto:", "").split("?", 1)[0]
                for link in soup.find_all("a", href=True)
                if link.get("href", "").lower().startswith("mailto:")
            ]
            text = soup.get_text(separator="\n", strip=True)
            text_parts.append("\n".join([page_url, title, *mailtos, text[:12000]]))
        return "\n".join(text_parts)

    async def _fetch_html(self, client: httpx.AsyncClient, url: str) -> str:
        try:
            response = await client.get(url)
        except httpx.HTTPError:
            return ""
        content_type = response.headers.get("content-type", "")
        if response.status_code >= 400 or "text/html" not in content_type:
            return ""
        return response.text

    async def _contact_pages(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        html: str,
    ) -> list[tuple[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        base_domain = urlparse(base_url).netloc
        urls: list[str] = []
        seen: set[str] = set()
        for link in soup.find_all("a", href=True):
            href = urljoin(base_url, link["href"])
            parsed = urlparse(href)
            if parsed.netloc != base_domain:
                continue
            label = f"{href} {link.get_text(' ', strip=True)}"
            if not CONTACT_LINK_RE.search(label):
                continue
            normalized = href.split("#", 1)[0]
            if normalized in seen:
                continue
            seen.add(normalized)
            urls.append(normalized)
        pages: list[tuple[str, str]] = []
        for url in urls[:3]:
            html = await self._fetch_html(client, url)
            if html:
                pages.append((url, html))
        return pages
