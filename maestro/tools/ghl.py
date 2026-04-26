"""
GoHighLevel (GHL) tool — contacts, opportunities, conversations via Private Integration Token.
Base URL: https://services.leadconnectorhq.com
"""
import os
from typing import Optional

import httpx
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

from maestro.utils.logging import get_logger
from maestro.utils.pii import mask_email

log = get_logger(__name__)

GHL_BASE_URL = "https://services.leadconnectorhq.com"
GHL_VERSION = "2021-07-28"

PIPELINE_CONFIG = {
    "roberts": {
        "pipeline_id": "n0Fsi2qAcXh9bkiudqPy",
        "stages": {
            "new_lead": "72df40f9-f564-4813-a79f-09ff08200060",
            "contacted": "f630ce9d-8575-4e27-86fe-22396cc5d25c",
            "call_booked": "cf59aaed-9053-4959-bf62-03bd2fec4453",
            "missed_appointment": "4e505da8-ef20-48f5-ab20-c4187c30b94a",
            "attended_follow_up": "6929b315-f260-4319-98ea-4f598869daa9",
            "sent_contract": "81e5e60b-d6c5-40e2-beb2-b94c92ed5aa1",
            "closed": "7ad58f1a-0f2b-447b-8dbf-b933fae882d6",
            "ghosted": "26ddde3d-0f43-4877-9fd4-a410ab6e21f2",
        },
    },
    "dockplusai": {
        "pipeline_id": "U9WUrJSwziyPlg3JdR0G",
        "stages": {
            "new_lead": "a33f975c-7cc3-4362-beec-0d2bfc864fb3",
            "hot_lead": "37d12952-07b4-4a22-bb7b-03f649340ccc",
            "new_booking": "fb2194b3-9039-471f-ab42-2ed741b76656",
            "visit_attended": "720fe610-ea06-4066-baa8-1c35d20f6a88",
            "sale": "9c0fcbb4-c547-470d-8919-0fe4b89f4464",
            "left_review": "ea308072-cdc1-4bea-a0bf-b1a5660d3594",
        },
    },
}


def _headers(business_id: str) -> dict:
    token_key = f"GHL_TOKEN_{business_id.upper()}"
    token = os.getenv(token_key, "")
    if not token:
        raise ValueError(f"{token_key} not set")
    return {
        "Authorization": f"Bearer {token}",
        "Version": GHL_VERSION,
        "Content-Type": "application/json",
    }


def _location_id(business_id: str) -> str:
    key = f"GHL_LOCATION_ID_{business_id.upper()}"
    loc = os.getenv(key, "")
    if not loc:
        raise ValueError(f"{key} not set")
    return loc


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def get_contact(business_id: str, contact_id: str) -> dict:
    """Get a GHL contact by ID. business_id: roberts|dockplusai."""
    log.info("ghl_get_contact", business_id=business_id, contact_id=contact_id)
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{GHL_BASE_URL}/contacts/{contact_id}",
            headers=_headers(business_id),
        )
        r.raise_for_status()
    contact = r.json().get("contact", r.json())
    log.info("ghl_get_contact_success", contact_id=contact_id)
    return contact


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def search_contacts(
    business_id: str,
    query: str,
    limit: int = 10,
) -> list:
    """Search GHL contacts by name, email, or phone. business_id: roberts|dockplusai."""
    location_id = _location_id(business_id)
    log.info("ghl_search_contacts", business_id=business_id, query=query)
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{GHL_BASE_URL}/contacts/search",
            headers=_headers(business_id),
            params={"locationId": location_id, "query": query, "limit": limit},
        )
        r.raise_for_status()
    contacts = r.json().get("contacts", [])
    log.info("ghl_search_contacts_success", count=len(contacts))
    return [
        {
            "id": c.get("id"),
            "name": f"{c.get('firstName', '')} {c.get('lastName', '')}".strip(),
            "email": mask_email(c.get("email", "")),
            "phone": c.get("phone", ""),
            "tags": c.get("tags", []),
        }
        for c in contacts
    ]


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def create_contact(
    business_id: str,
    first_name: str,
    last_name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    address: Optional[str] = None,
    city: Optional[str] = None,
    source: Optional[str] = None,
    tags: Optional[list] = None,
    *,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Create a new contact in GHL. business_id: roberts|dockplusai. Returns contact ID."""
    location_id = _location_id(business_id)
    log.info("ghl_create_contact", business_id=business_id, email=mask_email(email or ""))

    payload: dict = {
        "locationId": location_id,
        "firstName": first_name,
        "lastName": last_name,
    }
    if email:
        payload["email"] = email
    if phone:
        payload["phone"] = phone
    if address:
        payload["address1"] = address
    if city:
        payload["city"] = city
    if source:
        payload["source"] = source
    if tags:
        payload["tags"] = tags

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{GHL_BASE_URL}/contacts/",
            headers=_headers(business_id),
            json=payload,
        )
        r.raise_for_status()

    contact = r.json().get("contact", r.json())
    log.info("ghl_create_contact_success", contact_id=contact.get("id"))
    return {"contact_id": contact.get("id"), "name": f"{first_name} {last_name}"}


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def update_contact(
    business_id: str,
    contact_id: str,
    tags: Optional[list] = None,
    custom_fields: Optional[dict] = None,
    notes: Optional[str] = None,
) -> dict:
    """Update a GHL contact's tags or custom fields. business_id: roberts|dockplusai."""
    log.info("ghl_update_contact", business_id=business_id, contact_id=contact_id)

    payload: dict = {}
    if tags is not None:
        payload["tags"] = tags
    if custom_fields:
        payload["customFields"] = [
            {"key": k, "field_value": v} for k, v in custom_fields.items()
        ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.put(
            f"{GHL_BASE_URL}/contacts/{contact_id}",
            headers=_headers(business_id),
            json=payload,
        )
        r.raise_for_status()

    log.info("ghl_update_contact_success", contact_id=contact_id)
    return {"contact_id": contact_id, "updated": True}


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def create_opportunity(
    business_id: str,
    contact_id: str,
    name: str,
    pipeline_id: Optional[str] = None,
    stage_id: Optional[str] = None,
    monetary_value: Optional[float] = None,
    status: str = "open",
    *,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Create an opportunity in GHL pipeline. Defaults to Roberts LEADS pipeline at New Lead stage. business_id: roberts|dockplusai."""
    location_id = _location_id(business_id)

    if not pipeline_id:
        pipeline_id = PIPELINE_CONFIG[business_id]["pipeline_id"]
    if not stage_id:
        stage_id = PIPELINE_CONFIG[business_id]["stages"]["new_lead"]

    log.info(
        "ghl_create_opportunity",
        business_id=business_id,
        contact_id=contact_id,
        pipeline_id=pipeline_id,
        stage_id=stage_id,
    )

    payload: dict = {
        "locationId": location_id,
        "contactId": contact_id,
        "name": name,
        "pipelineId": pipeline_id,
        "pipelineStageId": stage_id,
        "status": status,
    }
    if monetary_value is not None:
        payload["monetaryValue"] = monetary_value

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{GHL_BASE_URL}/opportunities/",
            headers=_headers(business_id),
            json=payload,
        )
        r.raise_for_status()

    opp = r.json().get("opportunity", r.json())
    log.info("ghl_create_opportunity_success", opportunity_id=opp.get("id"))
    return {
        "opportunity_id": opp.get("id"),
        "name": name,
        "stage": stage_id,
        "contact_id": contact_id,
    }


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def move_opportunity_stage(
    business_id: str,
    opportunity_id: str,
    stage_name: str,
) -> dict:
    """Move an opportunity to a named stage. Roberts stages: new_lead|contacted|call_booked|missed_appointment|attended_follow_up|sent_contract|closed|ghosted. DockPlus AI stages: new_lead|hot_lead|new_booking|visit_attended|sale|left_review. business_id: roberts|dockplusai."""
    stages = PIPELINE_CONFIG.get(business_id, {}).get("stages", {})
    stage_id = stages.get(stage_name)
    if not stage_id:
        raise ValueError(f"Unknown stage '{stage_name}' for {business_id}. Valid: {list(stages)}")

    log.info(
        "ghl_move_stage",
        opportunity_id=opportunity_id,
        stage_name=stage_name,
        stage_id=stage_id,
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.put(
            f"{GHL_BASE_URL}/opportunities/{opportunity_id}",
            headers=_headers(business_id),
            json={"pipelineStageId": stage_id},
        )
        r.raise_for_status()

    log.info("ghl_move_stage_success", opportunity_id=opportunity_id, stage_name=stage_name)
    return {"opportunity_id": opportunity_id, "stage": stage_name, "updated": True}


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def send_sms(
    business_id: str,
    contact_id: str,
    message: str,
    *,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Send an SMS to a GHL contact via the conversations API. business_id: roberts|dockplusai."""
    location_id = _location_id(business_id)
    log.info("ghl_send_sms", business_id=business_id, contact_id=contact_id)

    payload = {
        "type": "SMS",
        "contactId": contact_id,
        "locationId": location_id,
        "message": message,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{GHL_BASE_URL}/conversations/messages",
            headers=_headers(business_id),
            json=payload,
        )
        r.raise_for_status()

    result = r.json()
    log.info("ghl_send_sms_success", contact_id=contact_id, message_id=result.get("messageId"))
    return {"message_id": result.get("messageId"), "contact_id": contact_id, "status": "sent"}


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def get_contact_opportunities(business_id: str, contact_id: str) -> list:
    """Get all opportunities for a contact in GHL. business_id: roberts|dockplusai."""
    log.info("ghl_get_opportunities", business_id=business_id, contact_id=contact_id)
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{GHL_BASE_URL}/opportunities/search",
            headers=_headers(business_id),
            params={"contact_id": contact_id},
        )
        r.raise_for_status()

    opps = r.json().get("opportunities", [])
    log.info("ghl_get_opportunities_success", count=len(opps))
    return [
        {
            "id": o.get("id"),
            "name": o.get("name"),
            "status": o.get("status"),
            "stage": o.get("pipelineStage", {}).get("name"),
            "value": o.get("monetaryValue"),
        }
        for o in opps
    ]
