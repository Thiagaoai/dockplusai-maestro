from typing import Any

import httpx

from maestro.config import Settings


class MarketingChannelError(RuntimeError):
    pass


class MetaAdsClient:
    def __init__(
        self,
        settings: Settings,
        base_url: str = "https://graph.facebook.com/v19.0",
        timeout_seconds: int = 30,
    ) -> None:
        self.settings = settings
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def account_insights(self, business: str) -> dict[str, Any]:
        if not self.settings.meta_access_token:
            return {"status": "skipped", "reason": "missing_meta_access_token", "sources": []}
        account_id = self.settings.meta_ad_account_for_business(business)
        if not account_id:
            return {"status": "skipped", "reason": "missing_meta_ad_account", "sources": []}
        if not account_id.startswith("act_"):
            account_id = f"act_{account_id}"

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.base_url}/{account_id}/insights",
                params={
                    "fields": "spend,impressions,clicks,cpc,cpm,ctr,actions",
                    "date_preset": "last_30d",
                    "access_token": self.settings.meta_access_token,
                },
            )
        if response.status_code >= 400:
            raise MarketingChannelError(
                f"Meta Ads request failed: {response.status_code}: {response.text[:500]}"
            )
        rows = response.json().get("data", [])
        row = rows[0] if rows else {}
        return {
            "status": "ok",
            "spend_usd": float(row.get("spend") or 0),
            "impressions": int(row.get("impressions") or 0),
            "clicks": int(row.get("clicks") or 0),
            "ctr": float(row.get("ctr") or 0),
            "sources": ["meta_ads"],
        }


class GoogleAdsClient:
    def __init__(
        self,
        settings: Settings,
        base_url: str = "https://googleads.googleapis.com/v17",
        token_url: str = "https://oauth2.googleapis.com/token",
        timeout_seconds: int = 30,
    ) -> None:
        self.settings = settings
        self.base_url = base_url.rstrip("/")
        self.token_url = token_url
        self.timeout_seconds = timeout_seconds

    async def customer_insights(self, business: str) -> dict[str, Any]:
        missing = [
            name
            for name, value in {
                "google_ads_developer_token": self.settings.google_ads_developer_token,
                "google_client_id": self.settings.google_client_id,
                "google_client_secret": self.settings.google_client_secret,
                "google_refresh_token": self.settings.google_refresh_token,
                "google_ads_customer_id": self.settings.google_ads_customer_id_for_business(business),
            }.items()
            if not value
        ]
        if missing:
            return {"status": "skipped", "reason": "missing_google_ads_credentials", "missing": missing, "sources": []}

        access_token = await self._access_token()
        customer_id = self.settings.google_ads_customer_id_for_business(business).replace("-", "")
        query = """
            SELECT metrics.cost_micros, metrics.impressions, metrics.clicks
            FROM customer
            WHERE segments.date DURING LAST_30_DAYS
        """
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/customers/{customer_id}/googleAds:searchStream",
                json={"query": query},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "developer-token": self.settings.google_ads_developer_token,
                    "Content-Type": "application/json",
                },
            )
        if response.status_code >= 400:
            raise MarketingChannelError(
                f"Google Ads request failed: {response.status_code}: {response.text[:500]}"
            )
        chunks = response.json() if response.text else []
        results = []
        for chunk in chunks:
            results.extend(chunk.get("results", []))
        cost_micros = sum(int(item.get("metrics", {}).get("costMicros") or 0) for item in results)
        impressions = sum(int(item.get("metrics", {}).get("impressions") or 0) for item in results)
        clicks = sum(int(item.get("metrics", {}).get("clicks") or 0) for item in results)
        return {
            "status": "ok",
            "spend_usd": round(cost_micros / 1_000_000, 2),
            "impressions": impressions,
            "clicks": clicks,
            "sources": ["google_ads"],
        }

    async def _access_token(self) -> str:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                self.token_url,
                data={
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret,
                    "refresh_token": self.settings.google_refresh_token,
                    "grant_type": "refresh_token",
                },
            )
        if response.status_code >= 400:
            raise MarketingChannelError(
                f"Google OAuth refresh failed: {response.status_code}: {response.text[:500]}"
            )
        return str(response.json()["access_token"])


class GBPClient:
    def __init__(
        self,
        settings: Settings,
        base_url: str = "https://mybusinessbusinessinformation.googleapis.com/v1",
        timeout_seconds: int = 30,
    ) -> None:
        self.settings = settings
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def account_status(self) -> dict[str, Any]:
        if not self.settings.gbp_api_key:
            return {"status": "skipped", "reason": "missing_gbp_api_key", "sources": []}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.base_url}/accounts",
                params={"key": self.settings.gbp_api_key},
            )
        if response.status_code >= 400:
            raise MarketingChannelError(
                f"GBP request failed: {response.status_code}: {response.text[:500]}"
            )
        accounts = response.json().get("accounts", [])
        return {"status": "ok", "account_count": len(accounts), "sources": ["gbp"]}
