import csv
import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
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
    queued: int = 0
    skipped: list[dict[str, Any]] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return {
            "business": self.business,
            "path": self.path,
            "rows_seen": self.rows_seen,
            "imported": self.imported,
            "queued": self.queued,
            "skipped_do_not_contact": self.skipped_do_not_contact,
            "skipped_duplicates": self.skipped_duplicates,
            "skipped_invalid": self.skipped_invalid,
            "imported_event_ids": self.imported_event_ids,
            "skipped": self.skipped,
        }

SOURCE_TYPE_CUSTOMER_FILE = "customer_file"


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


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_xls_rows(path: Path) -> list[dict[str, str]]:
    try:
        import xlrd
    except ImportError as exc:
        raise RuntimeError("xlrd is required to import .xls files") from exc

    workbook = xlrd.open_workbook(str(path))
    sheet = workbook.sheet_by_index(0)
    if sheet.nrows < 1:
        return []
    headers = [str(sheet.cell_value(0, col)).strip() for col in range(sheet.ncols)]
    rows: list[dict[str, str]] = []
    for row_idx in range(1, sheet.nrows):
        row: dict[str, str] = {}
        for col_idx, header in enumerate(headers):
            if not header:
                continue
            value = sheet.cell_value(row_idx, col_idx)
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            row[header] = str(value).strip()
        rows.append(row)
    return rows


def read_prospect_rows(path: str | Path) -> list[dict[str, str]]:
    file_path = Path(path).expanduser()
    suffix = file_path.suffix.casefold()
    if suffix == ".csv":
        return _read_csv_rows(file_path)
    if suffix == ".xls":
        return _read_xls_rows(file_path)
    raise ValueError(f"Unsupported prospect file type: {suffix}")


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

    for row in read_prospect_rows(csv_path):
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
        if hasattr(store, "upsert_prospect_queue_item"):
            await store.upsert_prospect_queue_item(
                prospect_queue_item(
                    business=business,
                    lead=lead,
                    source_name=csv_path.name,
                    source_ref=lead.event_id,
                )
            )
            result.queued += 1
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


def prospect_queue_item(
    business: str,
    lead: LeadRecord,
    source_name: str,
    source_ref: str,
    source_type: str = SOURCE_TYPE_CUSTOMER_FILE,
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    return {
        "id": str(uuid5(NAMESPACE_URL, f"prospect_queue:{business}:{source_type}:{source_ref}")),
        "business": business,
        "lead_id": str(lead.id),
        "source_type": source_type,
        "source_name": source_name,
        "source_ref": source_ref,
        "status": "queued",
        "priority": 70 if source_type == SOURCE_TYPE_CUSTOMER_FILE else 50,
        "sequence_bucket": "owned_list" if source_type == SOURCE_TYPE_CUSTOMER_FILE else "scrape",
        "payload": {
            "lead_event_id": lead.event_id,
            "lead_name": lead.name,
            "has_email": bool(lead.email),
            "has_phone": bool(lead.phone),
            "source": lead.source,
        },
        "created_at": now,
        "updated_at": now,
    }


def interleave_prospect_sources(
    owned_list_items: list[dict[str, Any]],
    scrape_items: list[dict[str, Any]],
    owned_per_cycle: int = 2,
    scrape_per_cycle: int = 1,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    owned_idx = 0
    scrape_idx = 0
    while owned_idx < len(owned_list_items) or scrape_idx < len(scrape_items):
        for _ in range(owned_per_cycle):
            if owned_idx < len(owned_list_items):
                result.append(owned_list_items[owned_idx])
                owned_idx += 1
        for _ in range(scrape_per_cycle):
            if scrape_idx < len(scrape_items):
                result.append(scrape_items[scrape_idx])
                scrape_idx += 1
    return result
