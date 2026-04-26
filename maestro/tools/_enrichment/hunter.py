"""Hunter.io enrichment tool.

Docs: https://hunter.io/api/docs
API base: https://api.hunter.io/v2

Implements:
- find_email: discover professional email by name + domain
- verify_email: verify deliverability of an email address
- domain_search: list all emails found for a domain

Hunter.io is used as a fallback/alternative to Apollo for email enrichment,
especially when Apollo's plan does not include person endpoints.
"""

from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from maestro.config import get_settings
from maestro.utils.pii import redact_pii

log = structlog.get_logger()

HUNTER_BASE_URL = "https://api.hunter.io/v2"
HUNTER_TIMEOUT = 30.0


def _auth_params() -> dict[str, str]:
    settings = get_settings()
    return {"api_key": settings.hunter_api_key}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def find_email(
    *,
    first_name: str,
    last_name: str,
    domain: str,
    company: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Find a professional email address using Hunter's email-finder.

    Returns email, confidence score, and sources.
    """
    settings = get_settings()
    log.info(
        "hunter_find_start",
        first_name=first_name,
        last_name=last_name,
        domain=domain,
        idempotency_key=idempotency_key,
    )

    if not settings.hunter_api_key:
        log.info("hunter_find_skipped", reason="no_api_key")
        return {
            "source": "hunter",
            "email": None,
            "confidence": None,
            "position": None,
            "url": None,
        }

    params = _auth_params()
    params["first_name"] = first_name
    params["last_name"] = last_name
    params["domain"] = domain
    if company:
        params["company"] = company

    async with httpx.AsyncClient(timeout=HUNTER_TIMEOUT) as client:
        response = await client.get(
            f"{HUNTER_BASE_URL}/email-finder",
            params=params,
        )
        response.raise_for_status()
        data = response.json()

    email_data = data.get("data", {})
    result = {
        "source": "hunter",
        "email": email_data.get("email"),
        "confidence": email_data.get("score"),
        "position": email_data.get("position"),
        "url": email_data.get("sources", [{}])[0].get("uri") if email_data.get("sources") else None,
    }

    log.info(
        "hunter_find_success",
        found=result["email"] is not None,
        confidence=result["confidence"],
        email=redact_pii(result["email"]),
    )
    return result


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def verify_email(
    *,
    email: str,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Verify an email address using Hunter's verifier.

    Returns status (valid, invalid, risky, unknown) and score.
    """
    settings = get_settings()
    log.info(
        "hunter_verify_start",
        email=redact_pii(email),
        idempotency_key=idempotency_key,
    )

    if not settings.hunter_api_key:
        log.info("hunter_verify_skipped", reason="no_api_key")
        return {
            "source": "hunter",
            "email": email,
            "status": "unknown",
            "result": "unknown",
            "score": None,
        }

    params = _auth_params()
    params["email"] = email

    async with httpx.AsyncClient(timeout=HUNTER_TIMEOUT) as client:
        response = await client.get(
            f"{HUNTER_BASE_URL}/email-verifier",
            params=params,
        )
        response.raise_for_status()
        data = response.json()

    verify_data = data.get("data", {})
    result = {
        "source": "hunter",
        "email": email,
        "status": verify_data.get("status"),
        "result": verify_data.get("result"),
        "score": verify_data.get("score"),
        "regexp": verify_data.get("regexp"),
        "gibberish": verify_data.get("gibberish"),
        "disposable": verify_data.get("disposable"),
        "webmail": verify_data.get("webmail"),
        "mx_records": verify_data.get("mx_records"),
        "smtp_server": verify_data.get("smtp_server"),
        "smtp_check": verify_data.get("smtp_check"),
        "accept_all": verify_data.get("accept_all"),
        "block": verify_data.get("block"),
    }

    log.info(
        "hunter_verify_success",
        status=result["status"],
        score=result["score"],
    )
    return result


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def domain_search(
    *,
    domain: str,
    limit: int = 10,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Search all emails found for a domain using Hunter's domain-search.

    Returns list of emails with confidence scores and positions.
    """
    settings = get_settings()
    log.info(
        "hunter_domain_search_start",
        domain=domain,
        limit=limit,
        idempotency_key=idempotency_key,
    )

    if not settings.hunter_api_key:
        log.info("hunter_domain_search_skipped", reason="no_api_key")
        return {
            "source": "hunter",
            "domain": domain,
            "emails": [],
            "pattern": None,
            "total": 0,
        }

    params = _auth_params()
    params["domain"] = domain
    params["limit"] = limit

    async with httpx.AsyncClient(timeout=HUNTER_TIMEOUT) as client:
        response = await client.get(
            f"{HUNTER_BASE_URL}/domain-search",
            params=params,
        )
        response.raise_for_status()
        data = response.json()

    domain_data = data.get("data", {})
    emails = [
        {
            "email": e.get("value"),
            "confidence": e.get("confidence"),
            "first_name": e.get("first_name"),
            "last_name": e.get("last_name"),
            "position": e.get("position"),
            "department": e.get("department"),
            "linkedin": e.get("linkedin"),
            "phone": e.get("phone_number"),
            "type": e.get("type"),
        }
        for e in domain_data.get("emails", [])
    ]

    result = {
        "source": "hunter",
        "domain": domain,
        "emails": emails,
        "pattern": domain_data.get("pattern"),
        "organization": domain_data.get("organization"),
        "total": domain_data.get("emails_count", 0),
    }

    log.info(
        "hunter_domain_search_success",
        found=len(emails),
        total=result["total"],
    )
    return result
