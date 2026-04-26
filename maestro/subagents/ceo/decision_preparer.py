def prepare_decisions(business_name: str) -> list[dict]:
    return [
        {
            "title": "Approve next growth test",
            "options": ["Approve controlled dry-run", "Wait for more data"],
            "recommendation": "Approve controlled dry-run",
            "reason": f"{business_name} needs compounding growth tests with audit trail.",
        },
        {
            "title": "Tighten response speed",
            "options": ["Keep SDR first", "Shift focus to reporting"],
            "recommendation": "Keep SDR first",
            "reason": "Lead response has direct revenue impact.",
        },
    ]
