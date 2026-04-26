"""
Web scraping tools — LangChain @tool wrappers.
Used by ProspectingAgent to collect leads from Cape Cod directories,
and by Research subagents to gather competitive intelligence.
"""
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

from maestro.utils.logging import get_logger

log = get_logger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.0 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.0"
)


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def scrape_page(
    url: str,
    selector: Optional[str] = None,
    max_chars: int = 8000,
) -> dict:
    """Scrape a web page and return clean text + title. Use for research, prospecting, and competitive intel.

    Args:
        url: Full URL to scrape (must include https://).
        selector: Optional CSS selector to extract a specific section (e.g., '.content', '#directory').
        max_chars: Max characters to return (truncates if page is huge).
    """
    log.info("scrape_start", url=url, selector=selector)

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        html = resp.text

    soup = BeautifulSoup(html, "html.parser")

    # Remove script/style/nav/footer noise
    for tag in soup(["script", "style", "nav", "footer", "aside", "header"]):
        tag.decompose()

    title = (soup.title.string if soup.title else "").strip()

    if selector:
        node = soup.select_one(selector)
        text = node.get_text(separator="\n", strip=True) if node else ""
    else:
        text = soup.get_text(separator="\n", strip=True)

    # Collapse multiple blank lines
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    clean_text = "\n".join(lines)[:max_chars]

    log.info("scrape_success", url=url, title=title, chars=len(clean_text))
    return {
        "url": url,
        "title": title,
        "text": clean_text,
        "truncated": len(text) > max_chars,
    }


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def extract_links(
    url: str,
    pattern: Optional[str] = None,
    same_domain_only: bool = True,
) -> dict:
    """Extract all links from a page. Use to discover directory pages or listing URLs for prospecting.

    Args:
        url: Page to extract links from.
        pattern: Optional regex pattern to filter URLs (e.g., 'contact|about').
        same_domain_only: If True, only keep links from the same domain.
    """
    import re
    from urllib.parse import urljoin, urlparse

    log.info("extract_links_start", url=url, pattern=pattern)

    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        html = resp.text

    soup = BeautifulSoup(html, "html.parser")
    base_domain = urlparse(url).netloc

    links = []
    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"])
        parsed = urlparse(href)
        if same_domain_only and parsed.netloc != base_domain:
            continue
        if pattern and not re.search(pattern, href, re.IGNORECASE):
            continue
        links.append({
            "url": href,
            "text": a.get_text(strip=True),
        })

    # Deduplicate by URL
    seen = set()
    unique = []
    for link in links:
        if link["url"] not in seen:
            seen.add(link["url"])
            unique.append(link)

    log.info("extract_links_success", url=url, count=len(unique))
    return {"url": url, "links": unique[:50]}  # Cap at 50
