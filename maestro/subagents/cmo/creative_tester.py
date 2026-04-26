def suggest_creative_tests(business_name: str, business_type: str = "B2C") -> list[dict]:
    if business_type.upper() == "B2B":
        return [
            {
                "test": f"{business_name}: before/after operations bottleneck",
                "hypothesis": "Specific workflow proof will outperform generic AI messaging.",
                "channel": "linkedin",
                "estimated_budget_usd": 150,
            },
            {
                "test": f"{business_name}: ROI calculator angle",
                "hypothesis": "Decision-makers respond to measurable time and margin impact.",
                "channel": "email_linkedin",
                "estimated_budget_usd": 150,
            },
            {
                "test": f"{business_name}: founder-led case breakdown",
                "hypothesis": "A practical build narrative creates more trust than brand claims.",
                "channel": "linkedin",
                "estimated_budget_usd": 100,
            },
        ]
    return [
        {
            "test": f"{business_name}: proof-first before/after angle",
            "hypothesis": "Local proof should increase qualified patio and hardscape inquiries.",
            "channel": "instagram_meta",
            "estimated_budget_usd": 150,
        },
        {
            "test": f"{business_name}: speed/response-time angle",
            "hypothesis": "Fast response messaging should lift lead-to-call conversion.",
            "channel": "meta_ads",
            "estimated_budget_usd": 150,
        },
        {
            "test": f"{business_name}: trust/local expertise angle",
            "hypothesis": "Cape Cod-specific project details should outperform generic outdoor living copy.",
            "channel": "instagram",
            "estimated_budget_usd": 100,
        },
    ]
