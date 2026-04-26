"""
Apollo.io tool — company enrichment and CRM search.
People search (mixed_people/search) requires paid Apollo plan — use GHL + Tavily for prospecting instead.
"""
import os
from typing import Optional

import httpx
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

from maestro.utils.logging import get_logger

log = get_logger(__name__)

APOLLO_BASE = "https://api.apollo.io/v1"


def _headers() -> dict:
    key = os.getenv("APOLLO_API_KEY", "")
    if not key:
        raise ValueError("APOLLO_API_KEY not set")
    return {"X-Api-Key": key, "Content-Type": "application/json"}


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def enrich_company(domain: str) -> dict:
    """Enrich a company by its domain using Apollo. Returns industry, size, location, LinkedIn. Use before outreach to personalize messaging."""
    log.info("apollo_enrich_company", domain=domain)
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{APOLLO_BASE}/organizations/enrich",
            headers=_headers(),
            params={"domain": domain},
        )
        r.raise_for_status()

    org = r.json().get("organization", {})
    log.info("apollo_enrich_company_success", domain=domain, name=org.get("name"))
    return {
        "name": org.get("name"),
        "domain": domain,
        "industry": org.get("industry"),
        "employees": org.get("estimated_num_employees"),
        "city": org.get("city"),
        "state": org.get("state"),
        "country": org.get("country"),
        "linkedin_url": org.get("linkedin_url"),
        "short_description": org.get("short_description"),
        "keywords": org.get("keywords", [])[:10],
        "phone": org.get("phone"),
        "annual_revenue": org.get("annual_revenue_printed"),
    }


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def search_apollo_accounts(
    company_name: Optional[str] = None,
    industry: Optional[str] = None,
    min_employees: Optional[int] = None,
    max_employees: Optional[int] = None,
    locations: Optional[list] = None,
    limit: int = 10,
) -> list:
    """Search companies in Apollo CRM. Use for DockPlus AI B2B prospecting to find target companies by industry/size/location."""
    log.info("apollo_search_accounts", company_name=company_name, industry=industry)

    payload: dict = {"per_page": limit}
    if company_name:
        payload["q_organization_name"] = company_name
    if industry:
        payload["organization_industry_tag_ids"] = [industry]
    if min_employees or max_employees:
        payload["organization_num_employees_ranges"] = [
            f"{min_employees or 1},{max_employees or 10000}"
        ]
    if locations:
        payload["organization_locations"] = locations

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{APOLLO_BASE}/accounts/search",
            headers=_headers(),
            json=payload,
        )
        r.raise_for_status()

    accounts = r.json().get("accounts", [])
    log.info("apollo_search_accounts_success", count=len(accounts))
    return [
        {
            "id": a.get("id"),
            "name": a.get("name"),
            "domain": a.get("domain"),
            "industry": a.get("industry"),
            "employees": a.get("estimated_num_employees"),
            "city": a.get("city"),
            "state": a.get("state"),
            "phone": a.get("phone"),
        }
        for a in accounts
    ]
