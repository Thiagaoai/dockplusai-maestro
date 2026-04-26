from typing import Any

from maestro.profiles._schema import BusinessProfile, DoNotContactEntry


def _normalize(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _digits(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def find_do_not_contact_match(
    contact: dict[str, Any],
    profile: BusinessProfile,
) -> DoNotContactEntry | None:
    name = _normalize(contact.get("name"))
    email = _normalize(contact.get("email"))
    phone = _digits(contact.get("phone"))

    for entry in profile.do_not_contact:
        entry_name = _normalize(entry.name)
        entry_email = _normalize(entry.email)
        entry_phone = _digits(entry.phone)

        if entry_email and email and entry_email == email:
            return entry
        if entry_phone and phone and entry_phone == phone:
            return entry
        if entry_name and name and entry_name == name:
            return entry

    return None


def is_do_not_contact(contact: dict[str, Any], profile: BusinessProfile) -> bool:
    return find_do_not_contact_match(contact, profile) is not None
