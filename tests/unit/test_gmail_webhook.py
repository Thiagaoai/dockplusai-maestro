"""Unit tests for Gmail webhook — cold email reply → SDR routing."""
import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maestro.config import get_settings
from maestro.repositories.store import InMemoryStore
from maestro.schemas.events import LeadRecord
from maestro.services.gmail import GmailClient, GmailReply, _extract_body, _parse_from_header


# ── helpers ───────────────────────────────────────────────────────────────────

def _pubsub_body(history_id: str = "12345") -> dict:
    data = base64.b64encode(json.dumps({"historyId": history_id, "emailAddress": "test@gmail.com"}).encode()).decode()
    return {"message": {"data": data, "messageId": "pub-123"}, "subscription": "projects/p/subscriptions/s"}


def _raw_gmail_message(
    from_header: str = "HOA Manager <manager@falmouth-hoa.org>",
    subject: str = "Re: Cape Cod landscape help",
    body_text: str = "Yes, we are interested. Please send more info.",
    has_in_reply_to: bool = True,
) -> dict:
    headers = [
        {"name": "From", "value": from_header},
        {"name": "Subject", "value": subject},
    ]
    if has_in_reply_to:
        headers.append({"name": "In-Reply-To", "value": "<sent123@resend.dev>"})
    encoded_body = base64.urlsafe_b64encode(body_text.encode()).decode()
    return {
        "id": "msg_abc",
        "threadId": "thread_xyz",
        "payload": {
            "mimeType": "text/plain",
            "headers": headers,
            "body": {"data": encoded_body},
        },
    }


def _make_lead(email: str = "manager@falmouth-hoa.org", business: str = "roberts") -> LeadRecord:
    from uuid import UUID, uuid4, NAMESPACE_URL, uuid5
    return LeadRecord(
        id=uuid5(NAMESPACE_URL, email),
        event_id=f"apify:roberts:hoa:{email}",
        business=business,
        name="Falmouth HOA",
        email=email,
        source="apify_web_search",
        status="prospect_imported",
        raw={},
    )


# ── GmailClient.parse_reply ───────────────────────────────────────────────────

class TestGmailParseReply:
    def test_parses_valid_reply(self):
        client = GmailClient(MagicMock())
        raw = _raw_gmail_message()
        reply = client.parse_reply(raw)
        assert reply is not None
        assert reply.sender_email == "manager@falmouth-hoa.org"
        assert reply.sender_name == "HOA Manager"
        assert "interested" in reply.body_text
        assert not reply.is_stop_request

    def test_stop_request_detected(self):
        client = GmailClient(MagicMock())
        raw = _raw_gmail_message(body_text="STOP please remove me from your list.")
        reply = client.parse_reply(raw)
        assert reply is not None
        assert reply.is_stop_request

    def test_stop_case_insensitive(self):
        client = GmailClient(MagicMock())
        raw = _raw_gmail_message(body_text="stop emailing me")
        reply = client.parse_reply(raw)
        assert reply is not None
        assert reply.is_stop_request

    def test_returns_none_if_not_a_reply(self):
        client = GmailClient(MagicMock())
        raw = _raw_gmail_message(subject="Cape Cod landscape help", has_in_reply_to=False)
        reply = client.parse_reply(raw)
        assert reply is None

    def test_returns_none_if_no_from(self):
        client = GmailClient(MagicMock())
        raw = _raw_gmail_message(from_header="")
        reply = client.parse_reply(raw)
        assert reply is None

    def test_re_subject_counts_as_reply(self):
        client = GmailClient(MagicMock())
        raw = _raw_gmail_message(subject="Re: landscape quote", has_in_reply_to=False)
        reply = client.parse_reply(raw)
        assert reply is not None


class TestParseFromHeader:
    def test_display_name_and_email(self):
        email, name = _parse_from_header("John Smith <john@example.com>")
        assert email == "john@example.com"
        assert name == "John Smith"

    def test_bare_email(self):
        email, name = _parse_from_header("john@example.com")
        assert email == "john@example.com"
        assert name == ""

    def test_quoted_display_name(self):
        email, name = _parse_from_header('"Cape Cod HOA" <hoa@example.org>')
        assert email == "hoa@example.org"
        assert name == "Cape Cod HOA"

    def test_invalid_returns_empty(self):
        email, name = _parse_from_header("not an email")
        assert email == ""
        assert name == ""


class TestExtractBody:
    def test_extracts_plain_text(self):
        body = "Hello, I saw your email."
        encoded = base64.urlsafe_b64encode(body.encode()).decode()
        payload = {"mimeType": "text/plain", "body": {"data": encoded}}
        assert _extract_body(payload) == body

    def test_recurses_into_parts(self):
        body = "Reply body here."
        encoded = base64.urlsafe_b64encode(body.encode()).decode()
        payload = {
            "mimeType": "multipart/mixed",
            "parts": [
                {"mimeType": "text/html", "body": {"data": ""}},
                {"mimeType": "text/plain", "body": {"data": encoded}},
            ],
        }
        assert _extract_body(payload) == body

    def test_returns_empty_if_no_body(self):
        assert _extract_body({"mimeType": "text/plain", "body": {}}) == ""


# ── webhook endpoint ──────────────────────────────────────────────────────────

class TestGmailWebhookEndpoint:
    async def test_rejects_invalid_token(self, monkeypatch):
        from fastapi.testclient import TestClient
        from maestro.main import create_app

        monkeypatch.setenv("GMAIL_WEBHOOK_SECRET", "correct-secret")
        get_settings.cache_clear()
        app = create_app()
        client = TestClient(app)
        response = client.post("/webhooks/gmail?token=wrong", json=_pubsub_body())
        assert response.status_code == 403

    async def test_returns_skipped_when_not_configured(self, monkeypatch):
        from fastapi.testclient import TestClient
        from maestro.main import create_app

        monkeypatch.setenv("GMAIL_WEBHOOK_SECRET", "secret123")
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")
        monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "")
        get_settings.cache_clear()
        app = create_app()
        client = TestClient(app)
        response = client.post("/webhooks/gmail?token=secret123", json=_pubsub_body())
        assert response.status_code == 200
        assert response.json()["status"] == "skipped"

    async def test_ignores_invalid_pubsub_payload(self, monkeypatch):
        from fastapi.testclient import TestClient
        from maestro.main import create_app

        monkeypatch.setenv("GMAIL_WEBHOOK_SECRET", "secret123")
        get_settings.cache_clear()
        app = create_app()
        client = TestClient(app)
        response = client.post("/webhooks/gmail?token=secret123", json={"message": {"data": "!!!"}})
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"


# ── reply routing logic ───────────────────────────────────────────────────────

class TestGmailReplyRouting:
    async def test_routes_reply_to_sdr(self, monkeypatch):
        from maestro.webhooks.gmail import _handle_reply

        lead = _make_lead()
        mock_store = InMemoryStore()
        await mock_store.upsert_lead(lead)

        reply = GmailReply(
            message_id="msg_001",
            thread_id="thread_001",
            sender_email="manager@falmouth-hoa.org",
            sender_name="HOA Manager",
            subject="Re: landscape",
            body_text="Yes please call us.",
            is_stop_request=False,
        )

        mock_graph = AsyncMock()
        mock_graph.handle_inbound_lead = AsyncMock(return_value={"status": "approval_requested"})

        settings = MagicMock()
        settings.google_client_id = "test"

        with patch("maestro.webhooks.gmail.store", mock_store):
            with patch("maestro.webhooks.gmail.MaestroGraph", return_value=mock_graph):
                result = await _handle_reply(reply, settings)

        assert result["status"] == "routed_to_sdr"
        mock_graph.handle_inbound_lead.assert_called_once()
        lead_in = mock_graph.handle_inbound_lead.call_args[0][0]
        assert lead_in.email == "manager@falmouth-hoa.org"
        assert lead_in.source == "cold_email_reply"
        assert lead_in.business == "roberts"

    async def test_stop_request_logs_compliance_not_sdr(self, monkeypatch):
        from maestro.webhooks.gmail import _handle_reply

        lead = _make_lead()
        mock_store = InMemoryStore()
        await mock_store.upsert_lead(lead)

        reply = GmailReply(
            message_id="msg_stop",
            thread_id="thread_stop",
            sender_email="manager@falmouth-hoa.org",
            sender_name="HOA Manager",
            subject="Re: landscape",
            body_text="STOP",
            is_stop_request=True,
        )

        settings = MagicMock()

        with patch("maestro.webhooks.gmail.store", mock_store):
            result = await _handle_reply(reply, settings)

        assert result["status"] == "stop_request"
        assert any(e.action == "stop_request_received" for e in mock_store.audit_log)

    async def test_returns_no_lead_for_unknown_sender(self, monkeypatch):
        from maestro.webhooks.gmail import _handle_reply

        mock_store = InMemoryStore()
        reply = GmailReply(
            message_id="msg_unknown",
            thread_id="thread_unknown",
            sender_email="stranger@unknown.com",
            sender_name="Stranger",
            subject="Re: hi",
            body_text="Hello",
            is_stop_request=False,
        )

        settings = MagicMock()

        with patch("maestro.webhooks.gmail.store", mock_store):
            result = await _handle_reply(reply, settings)

        assert result["status"] == "no_lead"
