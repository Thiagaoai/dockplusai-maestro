import re

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")


def redact_pii(value: object) -> object:
    if not isinstance(value, str):
        return value
    value = EMAIL_RE.sub("[redacted-email]", value)
    return PHONE_RE.sub("[redacted-phone]", value)
