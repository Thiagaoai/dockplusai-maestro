"""Apollo.io enrichment tool.

Docs: https://docs.apollo.io/docs/introduction
API base: https://api.apollo.io/v1

Implements:
- enrich_lead: match a person by name + email + company (requires paid plan)
- search_people: discover prospects by title, company, location (requires paid plan)
- search_organizations: find companies by name/industry (works on all plans)

NOTE: Person enrichment endpoints require Apollo Basic+ plan.
      Organization search works on free plans.
"""

from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from maestro.config import get_settings
from maestro.utils.pii import redact_pii

log = structlog.get_logger()

APOLLO_BASE_URL = "https://api.apollo.io/v1"
APOLLO_TIMEOUT = 30.0


def _auth_headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "X-Api-Key": settings.apollo_api_key,
        "Content-Type": "application/json",
    }


def _is_plan_limited(data: dict) -> bool:
    """Check if Apollo returned a plan-limitation error."""
    return data.get("error_code") == "API_INACCESSIBLE"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def enrich_lead(
    *,
    name: str | None = None,
    email: str | None = None,
    company_name: str | None = None,
    linkedin_url: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Enrich a lead using Apollo's people/match endpoint.

    Returns enriched contact data: email, phone, title, LinkedIn, etc.
    Falls back gracefully if Apollo is not configured, in dry-run,
    or if the API key's plan does not include person enrichment.
    """
    settings = get_settings()
    log.info(
        "apollo_enrich_start",
        name=redact_pii(name),
        email=redact_pii(email),
        company=company_name,
        idempotency_key=idempotency_key,
    )

    if not settings.apollo_api_key:
        log.info("apollo_enrich_skipped", reason="no_api_key")
        return {
            "source": "apollo",
            "person": None,
            "plan_limited": False,
            "input": {"name": name, "email": email, "company_name": company_name},
        }

    payload: dict[str, Any] = {"reveal_personal_emails": True, "reveal_phone_number": True}
    if name:
        parts = name.split(" ", 1)
        payload["first_name"] = parts[0]
        if len(parts) > 1:
            payload["last_name"] = parts[1]
    if email:
        payload["email"] = email
    if company_name:
        payload["organization_name"] = company_name
    if linkedin_url:
        payload["linkedin_url"] = linkedin_url

    async with httpx.AsyncClient(timeout=APOLLO_TIMEOUT) as client:
        response = await client.post(
            f"{APOLLO_BASE_URL}/people/match",
            headers=_auth_headers(),
            json=payload,
        )
        data = response.json()

    if _is_plan_limited(data):
        log.warning("apollo_enrich_plan_limited", error=data.get("error"))
        return {
            "source": "apollo",
            "person": None,
            "plan_limited": True,
            "error": data.get("error"),
        }

    response.raise_for_status()
    person = data.get("person")
    result = {
        "source": "apollo",
        "person": _normalize_person(person) if person else None,
        "cached": data.get("cached", False),
        "plan_limited": False,
    }

    log.info(
        "apollo_enrich_success",
        found=person is not None,
        cached=result["cached"],
        email=redact_pii(result["person"]["email"]) if result["person"] else None,
    )
    return result


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def search_people(
    *,
    q_keywords: str | None = None,
    person_titles: list[str] | None = None,
    organization_ids: list[str] | None = None,
    page: int = 1,
    per_page: int = 10,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Search for prospects using Apollo's mixed_people/search endpoint.

    Useful for B2B prospecting based on ICP criteria.
    Requires paid Apollo plan.
    """
    settings = get_settings()
    log.info(
        "apollo_search_start",
        keywords=q_keywords,
        titles=person_titles,
        page=page,
        idempotency_key=idempotency_key,
    )

    if not settings.apollo_api_key:
        log.info("apollo_search_skipped", reason="no_api_key")
        return {
            "source": "apollo",
            "people": [],
            "plan_limited": False,
            "pagination": {"page": page, "per_page": per_page, "total_entries": 0},
        }

    payload: dict[str, Any] = {"page": page, "per_page": per_page}
    if q_keywords:
        payload["q_keywords"] = q_keywords
    if person_titles:
        payload["person_titles"] = person_titles
    if organization_ids:
        payload["organization_ids"] = organization_ids

    async with httpx.AsyncClient(timeout=APOLLO_TIMEOUT) as client:
        response = await client.post(
            f"{APOLLO_BASE_URL}/mixed_people/search",
            headers=_auth_headers(),
            json=payload,
        )
        data = response.json()

    if _is_plan_limited(data):
        log.warning("apollo_search_plan_limited", error=data.get("error"))
        return {
            "source": "apollo",
            "people": [],
            "plan_limited": True,
            "error": data.get("error"),
            "pagination": {"page": page, "per_page": per_page, "total_entries": 0},
        }

    response.raise_for_status()
    people = [_normalize_person(p) for p in data.get("people", []) if p]
    result = {
        "source": "apollo",
        "people": people,
        "plan_limited": False,
        "pagination": {
            "page": data.get("page", page),
            "per_page": data.get("per_page", per_page),
            "total_entries": data.get("total_entries", 0),
        },
    }

    log.info("apollo_search_success", found=len(people), total=result["pagination"]["total_entries"])
    return result


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def search_organizations(
    *,
    q_organization_name: str | None = None,
    organization_industry_tag_ids: list[str] | None = None,
    page: int = 1,
    per_page: int = 10,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Search for companies using Apollo's organizations/search endpoint.

    Works on all Apollo plans including free tier.
    """
    settings = get_settings()
    log.info(
        "apollo_org_search_start",
        name=q_organization_name,
        page=page,
        idempotency_key=idempotency_key,
    )

    if not settings.apollo_api_key:
        log.info("apollo_org_search_skipped", reason="no_api_key")
        return {
            "source": "apollo",
            "organizations": [],
            "pagination": {"page": page, "per_page": per_page, "total_entries": 0},
        }

    payload: dict[str, Any] = {"page": page, "per_page": per_page}
    if q_organization_name:
        payload["q_organization_name"] = q_organization_name
    if organization_industry_tag_ids:
        payload["organization_industry_tag_ids"] = organization_industry_tag_ids

    async with httpx.AsyncClient(timeout=APOLLO_TIMEOUT) as client:
        response = await client.post(
            f"{APOLLO_BASE_URL}/organizations/search",
            headers=_auth_headers(),
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    orgs = [_normalize_org(o) for o in data.get("organizations", []) if o]
    result = {
        "source": "apollo",
        "organizations": orgs,
        "pagination": {
            "page": data.get("page", page),
            "per_page": data.get("per_page", per_page),
            "total_entries": data.get("total_entries", 0),
            "total_pages": data.get("total_pages", 0),
        },
    }

    log.info(
        "apollo_org_search_success",
        found=len(orgs),
        total=result["pagination"]["total_entries"],
    )
    return result


def _normalize_person(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten Apollo's nested person response into a clean dict."""
    org = raw.get("organization", {})
    return {
        "apollo_id": raw.get("id"),
        "first_name": raw.get("first_name"),
        "last_name": raw.get("last_name"),
        "name": " ".join(filter(None, [raw.get("first_name"), raw.get("last_name")])),
        "title": raw.get("title"),
        "email": raw.get("email"),
        "personal_email": raw.get("personal_emails", [None])[0] if raw.get("personal_emails") else None,
        "phone": raw.get("phone_number"),
        "linkedin_url": raw.get("linkedin_url"),
        "company": {
            "name": org.get("name") if org else None,
            "website": org.get("website_url") if org else None,
            "linkedin": org.get("linkedin_url") if org else None,
            "industry": org.get("industry") if org else None,
            "employee_count": org.get("estimated_num_employees") if org else None,
        },
        "location": raw.get("city") or raw.get("state") or raw.get("country"),
    }


def _normalize_org(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten Apollo's organization response into a clean dict."""
    return {
        "apollo_id": raw.get("id"),
        "name": raw.get("name"),
        "website": raw.get("website_url"),
        "linkedin": raw.get("linkedin_url"),
        "industry": raw.get("industry"),
        "employee_count": raw.get("estimated_num_employees"),
        "revenue": raw.get("annual_revenue_printed"),
        "location": raw.get("city") or raw.get("state") or raw.get("country"),
        "phone": raw.get("phone"),
    }
