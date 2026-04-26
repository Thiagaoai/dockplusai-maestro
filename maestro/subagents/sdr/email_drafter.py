from maestro.profiles._schema import BusinessProfile
from maestro.schemas.events import LeadRecord


def draft_email(lead: LeadRecord, profile: BusinessProfile) -> dict[str, str]:
    first_name = (lead.name or "there").split(" ")[0]
    top_offering = profile.offerings[0].name if profile.offerings else "your project"
    subject = f"Thanks for reaching out about {top_offering}"
    body = (
        f"Hi {first_name},\n\n"
        f"Thanks for reaching out to {profile.business_name}. "
        "We received your request and can help you think through the next best step.\n\n"
        "I can take a quick look at the details, confirm fit, and suggest a time to talk. "
        "If you have photos, measurements, or timing constraints, send them over before the call.\n\n"
        f"{profile.tone.signature}"
    )
    return {"subject": subject, "body": body}
