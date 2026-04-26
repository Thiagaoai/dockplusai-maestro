"""Gmail API client for reading cold email replies."""
from __future__ import annotations

import base64
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from maestro.config import Settings

log = structlog.get_logger()

_COLD_SOURCES = frozenset({
    "tavily_web_search",
    "google_web_search",
    "apify_web_search",
    "hunter_web_search",
    "apollo_web_search",
    "perplexity_web_search",
    "cold_email_reply",
})


@dataclass
class GmailReply:
    message_id: str
    thread_id: str
    sender_email: str
    sender_name: str
    subject: str
    body_text: str
    is_stop_request: bool


class GmailClient:
    BASE_URL = "https://gmail.googleapis.com/gmail/v1"
    TOKEN_URL = "https://oauth2.googleapis.com/token"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    def is_configured(self) -> bool:
        return bool(
            self.settings.google_client_id
            and self.settings.google_client_secret
            and self.settings.google_refresh_token
        )

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token
        r = await client.post(
            self.TOKEN_URL,
            data={
                "client_id": self.settings.google_client_id,
                "client_secret": self.settings.google_client_secret,
                "refresh_token": self.settings.google_refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + int(data.get("expires_in", 3600))
        return self._access_token

    async def list_history(
        self,
        client: httpx.AsyncClient,
        start_history_id: str,
    ) -> list[dict[str, Any]]:
        token = await self._get_token(client)
        r = await client.get(
            f"{self.BASE_URL}/users/me/history",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "startHistoryId": start_history_id,
                "historyTypes": "messageAdded",
                "maxResults": 50,
            },
            timeout=15,
        )
        if r.status_code == 404:
            # History expired — treat as empty, caller should reset baseline
            log.warning("gmail_history_expired", start_history_id=start_history_id)
            return []
        r.raise_for_status()
        return r.json().get("history", [])

    async def get_message(
        self,
        client: httpx.AsyncClient,
        message_id: str,
    ) -> dict[str, Any]:
        token = await self._get_token(client)
        r = await client.get(
            f"{self.BASE_URL}/users/me/messages/{message_id}",
            headers={"Authorization": f"Bearer {token}"},
            params={"format": "full"},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    async def setup_watch(
        self,
        client: httpx.AsyncClient,
        topic_name: str,
    ) -> dict[str, Any]:
        token = await self._get_token(client)
        r = await client.post(
            f"{self.BASE_URL}/users/me/watch",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"labelIds": ["INBOX"], "topicName": topic_name},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    def parse_reply(self, raw_message: dict[str, Any]) -> GmailReply | None:
        """Extract reply metadata from a raw Gmail message. Returns None if not a reply."""
        headers = {
            h["name"].lower(): h["value"]
            for h in raw_message.get("payload", {}).get("headers", [])
        }
        from_header = headers.get("from", "")
        subject = headers.get("subject", "")
        message_id = raw_message.get("id", "")
        thread_id = raw_message.get("threadId", "")

        sender_email, sender_name = _parse_from_header(from_header)
        if not sender_email:
            return None

        # Only process replies — subject starts with Re: or has threading headers
        is_reply = (
            subject.lower().startswith("re:")
            or bool(headers.get("in-reply-to"))
            or bool(headers.get("references"))
        )
        if not is_reply:
            return None

        body_text = _extract_body(raw_message.get("payload", {}))
        is_stop = bool(re.search(r"\bSTOP\b", body_text, re.IGNORECASE))

        return GmailReply(
            message_id=message_id,
            thread_id=thread_id,
            sender_email=sender_email.casefold(),
            sender_name=sender_name,
            subject=subject,
            body_text=body_text[:2000],
            is_stop_request=is_stop,
        )


def _parse_from_header(from_header: str) -> tuple[str, str]:
    """Parse 'Display Name <email@example.com>' or bare 'email@example.com'."""
    m = re.match(r'^"?([^"<]*)"?\s*<([^>]+)>$', from_header.strip())
    if m:
        return m.group(2).strip(), m.group(1).strip().strip('"')
    if re.match(r"^[\w.+%-]+@[\w.-]+\.\w+$", from_header.strip()):
        return from_header.strip(), ""
    return "", ""


def _extract_body(payload: dict[str, Any], _depth: int = 0) -> str:
    """Recursively extract plain-text body from a Gmail message payload."""
    if _depth > 5:
        return ""
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            try:
                return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
            except Exception:
                return ""
    for part in payload.get("parts", []):
        text = _extract_body(part, _depth + 1)
        if text:
            return text
    return ""
