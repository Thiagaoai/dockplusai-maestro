import csv
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from maestro.profiles import load_profile
from maestro.repositories.store import InMemoryStore
from maestro.schemas.events import LeadRecord
from maestro.utils.contact_policy import find_do_not_contact_match


FIELD_ALIASES = {
    "name": ["name", "full_name", "full name", "customer", "client", "contact name"],
    "first_name": ["first_name", "first name", "firstname"],
    "last_name": ["last_name", "last name", "lastname"],
    "email": ["email", "email_address", "email address", "e-mail"],
    "phone": ["phone", "phone_number", "phone number", "mobile", "cell"],
    "message": ["message", "notes", "note", "description", "project", "job", "scope"],
    "estimated_ticket_usd": ["estimated_ticket_usd", "value", "amount", "deal value", "ticket"],
    "source": ["source", "lead source", "origin"],
    "status": ["status", "stage", "pipeline stage"],
    "address": ["address", "street"],
    "city": ["city", "town"],
}


@dataclass
class ProspectImportResult:
    business: str
    path: str
    imported: int = 0
    skipped_do_not_contact: int = 0
    skipped_duplicates: int = 0
    skipped_invalid: int = 0
    rows_seen: int = 0
    imported_event_ids: list[str] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return {
            "business": self.business,
            "path": self.path,
            "rows_seen": self.rows_seen,
            "imported": self.imported,
            "skipped_do_not_contact": self.skipped_do_not_contact,
            "skipped_duplicates": self.skipped_duplicates,
            "skipped_invalid": self.skipped_invalid,
            "imported_event_ids": self.imported_event_ids,
            "skipped": self.skipped,
        }


def _normalize_header(value: str) -> str:
    return " ".join(value.strip().casefold().replace("-", " ").replace("_", " ").split())


def _row_value(row: dict[str, str], key: str) -> str | None:
    normalized = {_normalize_header(k): v.strip() for k, v in row.items() if k and v and v.strip()}
    for alias in FIELD_ALIASES[key]:
        value = normalized.get(_normalize_header(alias))
        if value:
            return value
    return None


def _name_from_row(row: dict[str, str]) -> str | None:
    name = _row_value(row, "name")
    if name:
        return name
    parts = [_row_value(row, "first_name"), _row_value(row, "last_name")]
    return " ".join(part for part in parts if part) or None


def _ticket_from_row(row: dict[str, str]) -> float | None:
    raw = _row_value(row, "estimated_ticket_usd")
    if not raw:
        return None
    cleaned = "".join(ch for ch in raw if ch.isdigit() or ch == ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _identity(name: str | None, email: str | None, phone: str | None) -> str | None:
    if email:
        return f"email:{email.strip().casefold()}"
    if phone:
        digits = "".join(ch for ch in phone if ch.isdigit())
        if digits:
            return f"phone:{digits}"
    if name:
        return f"name:{' '.join(name.casefold().split())}"
    return None


def _event_id(business: str, identity: str) -> str:
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"csv:{business}:{digest}"


def lead_from_csv_row(row: dict[str, str], business: str) -> LeadRecord | None:
    name = _name_from_row(row)
    email = _row_value(row, "email")
    phone = _row_value(row, "phone")
    identity = _identity(name, email, phone)
    if not identity:
        return None

    event_id = _event_id(business, identity)
    city = _row_value(row, "city")
    address = _row_value(row, "address")
    raw = dict(row)
    raw["csv_identity"] = identity
    raw["city"] = city
    raw["address"] = address

    return LeadRecord(
        id=uuid5(NAMESPACE_URL, event_id),
        event_id=event_id,
        business=business,
        name=name,
        phone=phone,
        email=email,
        source=_row_value(row, "source") or "csv_customer_list",
        message=_row_value(row, "message"),
        estimated_ticket_usd=_ticket_from_row(row),
        status="prospect_imported",
        raw=raw,
    )


async def import_csv_prospects(path: str | Path, business: str, store: InMemoryStore) -> ProspectImportResult:
    csv_path = Path(path).expanduser()
    profile = load_profile(business)
    result = ProspectImportResult(business=business, path=str(csv_path))
    seen: set[str] = set()

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            result.rows_seen += 1
            lead = lead_from_csv_row(row, business)
            if not lead:
                result.skipped_invalid += 1
                result.skipped.append({"row": result.rows_seen, "reason": "missing_name_email_phone"})
                continue

            identity = lead.raw["csv_identity"]
            if identity in seen:
                result.skipped_duplicates += 1
                result.skipped.append({"row": result.rows_seen, "reason": "duplicate_in_csv", "name": lead.name})
                continue
            seen.add(identity)

            excluded = find_do_not_contact_match(lead.model_dump(mode="json"), profile)
            if excluded:
                result.skipped_do_not_contact += 1
                result.skipped.append(
                    {
                        "row": result.rows_seen,
                        "reason": "do_not_contact",
                        "name": lead.name,
                        "details": excluded.reason,
                    }
                )
                continue

            await store.upsert_lead(lead)
            result.imported += 1
            result.imported_event_ids.append(lead.event_id)

    await store.add_audit_log(
        event_type="prospecting",
        business=business,
        agent="prospecting",
        action="csv_prospects_imported",
        payload=result.model_dump(),
    )
    return result
