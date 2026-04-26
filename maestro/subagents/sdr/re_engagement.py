"""
Re-engagement subagent — finds cold/stale GHL contacts and drafts personalized follow-up.

Flow:
  1. Pull contacts from GHL filtered by tag or last activity date
  2. Skip contacts with active open opportunities (already in pipeline)
  3. For each cold contact: check qualification criteria from profile
  4. Draft a re-engagement SMS or email via LLM
  5. Return list of (contact, message) pairs for HITL approval before sending
"""
import json
import os
from typing import Optional

import httpx
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

from maestro.utils.logging import get_logger

log = get_logger(__name__)

GHL_BASE = "https://services.leadconnectorhq.com"
GHL_VERSION = "2021-07-28"


def _ghl_headers(business_id: str) -> dict:
    token = os.getenv(f"GHL_TOKEN_{business_id.upper()}", "")
    if not token:
        raise ValueError(f"GHL_TOKEN_{business_id.upper()} not set")
    return {
        "Authorization": f"Bearer {token}",
        "Version": GHL_VERSION,
        "Content-Type": "application/json",
    }


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def get_cold_contacts(
    business_id: str,
    tag: Optional[str] = None,
    limit: int = 25,
) -> list:
    """Pull GHL contacts that have no open opportunities — candidates for re-engagement. Optionally filter by tag. business_id: roberts|dockplusai. Returns up to `limit` contacts."""
    location_id = os.getenv(f"GHL_LOCATION_ID_{business_id.upper()}", "")
    if not location_id:
        raise ValueError(f"GHL_LOCATION_ID_{business_id.upper()} not set")

    log.info("re_engagement_get_cold", business_id=business_id, tag=tag, limit=limit)

    params: dict = {"locationId": location_id, "limit": limit}
    if tag:
        params["tags"] = tag

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{GHL_BASE}/contacts/",
            headers=_ghl_headers(business_id),
            params=params,
        )
        r.raise_for_status()

    contacts = r.json().get("contacts", [])

    # Filter: keep only contacts with no open opportunities
    cold = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for c in contacts:
            opp_r = await client.get(
                f"{GHL_BASE}/opportunities/search",
                headers=_ghl_headers(business_id),
                params={"contact_id": c["id"], "status": "open"},
            )
            if opp_r.is_success:
                opps = opp_r.json().get("opportunities", [])
                if not opps:
                    cold.append(c)

    log.info("re_engagement_cold_found", business_id=business_id, total=len(contacts), cold=len(cold))

    return [
        {
            "id": c.get("id"),
            "name": f"{c.get('firstName', '')} {c.get('lastName', '')}".strip(),
            "email": c.get("email", ""),
            "phone": c.get("phone", ""),
            "tags": c.get("tags", []),
            "date_added": c.get("dateAdded", ""),
            "last_activity": c.get("lastActivity", ""),
            "source": c.get("source", ""),
        }
        for c in cold
    ]


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def get_ghosted_opportunities(
    business_id: str,
    limit: int = 25,
) -> list:
    """Pull GHL opportunities that are open but haven't moved in a long time — contacts who went silent. business_id: roberts|dockplusai."""
    location_id = os.getenv(f"GHL_LOCATION_ID_{business_id.upper()}", "")
    if not location_id:
        raise ValueError(f"GHL_LOCATION_ID_{business_id.upper()} not set")

    log.info("re_engagement_get_ghosted", business_id=business_id)

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{GHL_BASE}/opportunities/search",
            headers=_ghl_headers(business_id),
            params={"locationId": location_id, "status": "open", "limit": limit},
        )
        r.raise_for_status()

    opps = r.json().get("opportunities", [])
    log.info("re_engagement_ghosted_found", count=len(opps))

    return [
        {
            "opportunity_id": o.get("id"),
            "opportunity_name": o.get("name"),
            "stage": o.get("pipelineStage", {}).get("name"),
            "value": o.get("monetaryValue"),
            "contact_id": o.get("contact", {}).get("id"),
            "contact_name": o.get("contact", {}).get("name"),
            "contact_email": o.get("contact", {}).get("email", ""),
            "contact_phone": o.get("contact", {}).get("phone", ""),
            "last_stage_change": o.get("lastStageChangeAt", ""),
            "date_added": o.get("dateAdded", ""),
        }
        for o in opps
    ]
