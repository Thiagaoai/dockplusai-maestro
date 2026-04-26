from typing import Any

import httpx

from maestro.config import Settings


class HighLevelError(RuntimeError):
    pass


class HighLevelClient:
    def __init__(
        self,
        settings: Settings,
        base_url: str = "https://services.leadconnectorhq.com",
        timeout_seconds: int = 30,
    ) -> None:
        self.settings = settings
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def get_pipelines(self, business: str) -> dict[str, Any]:
        token = self.settings.ghl_token_for_business(business)
        location_id = self.settings.ghl_location_for_business(business)
        if not token:
            return {"status": "skipped", "reason": "missing_ghl_token"}
        if not location_id:
            return {"status": "skipped", "reason": "missing_ghl_location_id"}

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.base_url}/opportunities/pipelines",
                params={"locationId": location_id},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Version": "2021-07-28",
                    "Accept": "application/json",
                },
            )

        if response.status_code >= 400:
            raise HighLevelError(
                f"HighLevel request failed: {response.status_code}: {response.text[:500]}"
            )
        data = response.json()
        return {
            "status": "ok",
            "location_id": location_id,
            "pipeline_count": len(data.get("pipelines", [])),
            "pipelines": data.get("pipelines", []),
        }
