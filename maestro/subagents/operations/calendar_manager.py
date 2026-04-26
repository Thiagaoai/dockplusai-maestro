def prepare_calendar_action(text: str) -> dict:
    return {
        "kind": "calendar",
        "summary": text,
        "dry_run_action": "would_find_or_create_calendar_event",
    }
