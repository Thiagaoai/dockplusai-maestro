from maestro.profiles._schema import BusinessProfile


def write_caption(topic: str, profile: BusinessProfile) -> str:
    offering = profile.offerings[0].name if profile.offerings else "service"
    return (
        f"{topic.title()} is not just about looking better. It should create trust, "
        f"solve a real problem, and move the customer closer to a clear decision.\n\n"
        f"For {profile.business_name}, the focus is simple: show the work, explain the value, "
        f"and make the next step easy.\n\n"
        f"Want help with {offering}? Send a message and we will point you in the right direction."
    )
