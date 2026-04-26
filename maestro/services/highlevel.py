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
            "sources": ["ghl:pipelines"],
        }

    async def pipeline_summary(self, business: str) -> dict[str, Any]:
        """Read GHL pipeline structure and aggregate visible opportunity values."""
        pipelines = await self.get_pipelines(business)
        if pipelines.get("status") != "ok":
            return {**pipelines, "sources": pipelines.get("sources", [])}

        open_count = 0
        won_count = 0
        open_value = 0.0
        won_value = 0.0
        stage_count = 0
        for pipeline in pipelines.get("pipelines", []):
            for stage in pipeline.get("stages", []) or []:
                stage_count += 1
                opportunities = stage.get("opportunities") or []
                for opportunity in opportunities:
                    value = float(opportunity.get("monetaryValue") or opportunity.get("value") or 0.0)
                    status = str(opportunity.get("status") or "").lower()
                    stage_name = str(stage.get("name") or "").lower()
                    if status in {"won", "closed"} or "won" in stage_name or "closed" in stage_name:
                        won_count += 1
                        won_value += value
                    else:
                        open_count += 1
                        open_value += value

        return {
            "status": "ok",
            "location_id": pipelines["location_id"],
            "pipeline_count": pipelines["pipeline_count"],
            "stage_count": stage_count,
            "open_count": open_count,
            "open_value_usd": round(open_value, 2),
            "won_count": won_count,
            "won_value_usd": round(won_value, 2),
            "sources": ["ghl:pipelines"],
        }

    async def move_opportunity_stage(
        self,
        business: str,
        opportunity_id: str,
        stage_id: str,
    ) -> dict[str, Any]:
        token = self.settings.ghl_token_for_business(business)
        if not token:
            return {"status": "skipped", "reason": "missing_ghl_token"}
        if not opportunity_id or not stage_id:
            return {"status": "skipped", "reason": "missing_opportunity_or_stage"}

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.put(
                f"{self.base_url}/opportunities/{opportunity_id}",
                json={"pipelineStageId": stage_id},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Version": "2021-07-28",
                    "Content-Type": "application/json",
                },
            )
        if response.status_code >= 400:
            raise HighLevelError(
                f"HighLevel request failed: {response.status_code}: {response.text[:500]}"
            )
        return {"status": "ok", "opportunity_id": opportunity_id, "stage_id": stage_id}
