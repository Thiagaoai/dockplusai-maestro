import re

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")


def redact_pii(value: object) -> object:
    if not isinstance(value, str):
        return value
    value = EMAIL_RE.sub("[redacted-email]", value)
    return PHONE_RE.sub("[redacted-phone]", value)


def mask_email(email: str) -> str:
    """Partially mask an email for safe logging: sarah@example.com → s***@e***.com"""
    if not email or "@" not in email:
        return "[invalid-email]"
    local, domain = email.split("@", 1)
    domain_parts = domain.split(".", 1)
    masked_local = local[0] + "***" if local else "***"
    masked_domain = domain_parts[0][0] + "***" if domain_parts[0] else "***"
    suffix = "." + domain_parts[1] if len(domain_parts) > 1 else ""
    return f"{masked_local}@{masked_domain}{suffix}"
