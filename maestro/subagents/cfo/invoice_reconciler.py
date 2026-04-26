def reconcile_invoices(business: str) -> dict:
    return {
        "business": business,
        "stripe_charges_checked": 0,
        "ghl_won_checked": 0,
        "discrepancies": [],
        "sources": ["dry_run:stripe", "dry_run:ghl"],
    }
