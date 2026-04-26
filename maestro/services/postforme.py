from typing import Any

import httpx

from maestro.config import Settings


class PostformeError(RuntimeError):
    pass


class PostformeClient:
    def __init__(
        self,
        settings: Settings,
        base_url: str = "https://api.postforme.dev/v1",
        timeout_seconds: int = 30,
    ) -> None:
        self.settings = settings
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def publish_or_schedule(
        self,
        business: str,
        caption: str,
        image_url: str,
        platform: str = "instagram",
        scheduled_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if not self.settings.postforme_api_key:
            return {"status": "skipped", "reason": "missing_postforme_api_key"}
        account_id = self.settings.postforme_account_for_business(business, platform)
        if not account_id:
            return {"status": "skipped", "reason": "missing_postforme_account", "platform": platform}
        if not image_url:
            return {"status": "skipped", "reason": "missing_image_url", "platform": platform}

        payload: dict[str, Any] = {
            "caption": caption,
            "social_accounts": [account_id],
            "media": [{"url": image_url}],
        }
        if scheduled_at:
            payload["scheduled_at"] = scheduled_at
        if idempotency_key:
            payload["external_id"] = idempotency_key

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/social-posts",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.settings.postforme_api_key}",
                    "Content-Type": "application/json",
                },
            )
        if response.status_code >= 400:
            raise PostformeError(
                f"Postforme request failed: {response.status_code}: {response.text[:500]}"
            )
        data = response.json()
        return {
            "status": data.get("status", "ok"),
            "post_id": data.get("id"),
            "scheduled_at": data.get("scheduled_at") or scheduled_at,
            "platform": platform,
        }
