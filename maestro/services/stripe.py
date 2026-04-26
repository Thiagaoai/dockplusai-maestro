from typing import Any

import httpx

from maestro.config import Settings


class StripeError(RuntimeError):
    pass


class StripeClient:
    def __init__(
        self,
        settings: Settings,
        base_url: str = "https://api.stripe.com/v1",
        timeout_seconds: int = 30,
    ) -> None:
        self.settings = settings
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def recent_charges_summary(self, business: str, limit: int = 100) -> dict[str, Any]:
        secret_key = self.settings.stripe_secret_key_for_business(business)
        if not secret_key:
            return {"status": "skipped", "reason": "missing_stripe_secret_key", "sources": []}

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.base_url}/charges",
                params={"limit": limit},
                auth=(secret_key, ""),
            )
        if response.status_code >= 400:
            raise StripeError(f"Stripe request failed: {response.status_code}: {response.text[:500]}")

        charges = response.json().get("data", [])
        succeeded = [charge for charge in charges if charge.get("status") == "succeeded"]
        total_cents = sum(int(charge.get("amount") or 0) for charge in succeeded)
        refunded_cents = sum(int(charge.get("amount_refunded") or 0) for charge in charges)
        return {
            "status": "ok",
            "charges_checked": len(charges),
            "succeeded_count": len(succeeded),
            "gross_revenue_usd": round(total_cents / 100, 2),
            "refunded_usd": round(refunded_cents / 100, 2),
            "sources": ["stripe"],
        }
