from typing import Any

import httpx
import structlog

from maestro.config import Settings

log = structlog.get_logger()


class TelegramService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send_approval_card(self, approval_id: str, preview: dict[str, Any]) -> dict[str, Any]:
        text = self._format_approval_text(preview)
        approve_label = "Approve real send" if not preview.get("dry_run", True) else "Approve dry-run"
        payload = {
            "chat_id": self.settings.telegram_thiago_chat_id,
            "text": text,
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": approve_label, "callback_data": f"approval:approve:{approval_id}"},
                        {"text": "Reject", "callback_data": f"approval:reject:{approval_id}"},
                    ]
                ]
            },
        }
        if self.settings.app_env == "test" or not self.settings.telegram_bot_token:
            log.info("telegram_approval_card_dry_run", approval_id=approval_id)
            return {"dry_run": True, "payload": payload}
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    async def send_message(self, text: str) -> dict[str, Any]:
        payload = {"chat_id": self.settings.telegram_thiago_chat_id, "text": text}
        if self.settings.app_env == "test" or not self.settings.telegram_bot_token:
            log.info("telegram_message_dry_run", text=text[:80])
            return {"dry_run": True, "payload": payload}
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    def _format_approval_text(self, preview: dict[str, Any]) -> str:
        if "campaign" in preview:
            campaign = preview["campaign"]
            email = preview.get("email", {})
            prospects = preview.get("prospects", [])
            source_counts: dict[str, int] = {}
            for prospect in prospects:
                source = prospect.get("source_type", "unknown")
                source_counts[source] = source_counts.get(source, 0) + 1
            property_names = [p.get("property_name") or p.get("name") or "Unknown" for p in prospects[:10]]
            property_lines = "\n".join(f"- {name}" for name in property_names)
            location_text = ", ".join(campaign.get("locations") or [])
            target_text = campaign.get("target")
            lines = [
                "Prospecting batch approval",
                "",
                f"Campaign: {campaign.get('name')}",
            ]
            if target_text:
                lines.append(f"Target: {target_text}")
            if location_text:
                lines.append(f"Locations: {location_text}")
            lines.extend(
                [
                    f"Offer: {campaign.get('offer')}",
                    f"Batch size: {campaign.get('batch_size')}",
                    f"Sources: {source_counts}",
                    f"Subject: {email.get('subject')}",
                    f"CTA: {campaign.get('cta_url')}",
                    f"Properties:\n{property_lines}",
                    "",
                    f"Dry run: {preview.get('dry_run', True)}",
                ]
            )
            return "\n".join(lines)
        if "lead" not in preview:
            title = preview.get("topic") or preview.get("task") or preview.get("request") or "Action"
            signal = preview.get("profit_signal", "growth")
            return (
                "Approval needed\n\n"
                f"Item: {title}\n"
                f"Signal: {signal}\n"
                f"Dry run: {preview.get('dry_run', True)}"
            )
        lead = preview["lead"]
        email = preview["email"]
        return (
            "New lead ready for approval\n\n"
            f"Name: {lead.get('name') or 'Unknown'}\n"
            f"Source: {lead.get('source')}\n"
            f"Score: {lead.get('qualification_score')}/100\n"
            f"Reason: {lead.get('qualification_reasoning')}\n\n"
            f"Subject: {email.get('subject')}\n"
            f"Dry run: {preview.get('dry_run')}"
        )
