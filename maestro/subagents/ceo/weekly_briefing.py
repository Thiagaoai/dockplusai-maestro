def create_weekly_briefing(business_name: str, cfo_data: dict, cmo_data: dict) -> str:
    margin = cfo_data.get("margin", {}).get("estimated_gross_margin_pct", "unknown")
    creative_count = len(cmo_data.get("creative_tests", []))
    return (
        f"{business_name} weekly briefing:\n"
        f"- Financial signal: estimated gross margin {margin}%.\n"
        f"- Marketing signal: {creative_count} creative tests ready.\n"
        "- Priority: convert faster, publish consistently, and protect margin."
    )
