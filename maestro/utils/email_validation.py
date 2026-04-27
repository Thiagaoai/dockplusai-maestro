from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")


def is_valid_email_address(value: str | None) -> bool:
    if not value:
        return False
    email = value.strip()
    if email != value or email.count("@") != 1:
        return False
    if any(separator in email for separator in (" ", ",", ";", "\n", "\t")):
        return False
    if len(email) > 254:
        return False
    local, _, domain = email.partition("@")
    if not local or not domain or len(local) > 64:
        return False
    if ".." in local or ".." in domain:
        return False
    return bool(_EMAIL_RE.fullmatch(email))
