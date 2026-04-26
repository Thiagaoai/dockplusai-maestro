from typing import Any

import httpx

from maestro.config import Settings


class ResendError(RuntimeError):
    pass


class ResendEmailClient:
    def __init__(
        self,
        settings: Settings,
        base_url: str = "https://api.resend.com/emails",
        timeout_seconds: int = 30,
    ) -> None:
        self.settings = settings
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    async def send_business_email(
        self,
        business: str,
        to: str,
        subject: str,
        body: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if not self.settings.resend_api_key:
            raise ResendError("RESEND_API_KEY not set")

        payload: dict[str, Any] = {
            "from": self.settings.resend_from_for_business(business),
            "to": [to],
            "subject": subject,
            "text": body,
        }
        reply_to = self.settings.resend_reply_to_for_business(business)
        if reply_to:
            payload["reply_to"] = reply_to

        headers = {
            "Authorization": f"Bearer {self.settings.resend_api_key}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(self.base_url, json=payload, headers=headers)

        if response.status_code >= 400:
            raise ResendError(f"Resend request failed: {response.status_code}: {response.text[:500]}")

        result = response.json()
        return {
            "status": "sent",
            "email_id": result.get("id"),
            "to": to,
            "subject": subject,
        }
