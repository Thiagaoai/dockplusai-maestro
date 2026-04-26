from datetime import datetime, timedelta, timezone


def suggest_meeting_slots() -> list[str]:
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    slots: list[str] = []
    cursor = now + timedelta(days=1)
    while len(slots) < 3:
        if cursor.weekday() < 5:
            candidate = cursor.replace(hour=14 + len(slots), minute=0)
            slots.append(candidate.isoformat())
        cursor += timedelta(days=1)
    return slots
