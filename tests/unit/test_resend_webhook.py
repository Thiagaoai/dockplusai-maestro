import base64
import hashlib
import hmac
import json
import time


def _svix_headers(payload: dict, event_id: str = "evt_1") -> dict[str, str]:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    secret = base64.b64decode("dGVzdF9zZWNyZXQ=")
    signed = b".".join([event_id.encode("utf-8"), timestamp.encode("utf-8"), raw])
    signature = base64.b64encode(hmac.new(secret, signed, hashlib.sha256).digest()).decode("utf-8")
    return {
        "content-type": "application/json",
        "svix-id": event_id,
        "svix-timestamp": timestamp,
        "svix-signature": f"v1,{signature}",
    }


def test_resend_webhook_records_bounce_event(client):
    payload = {
        "id": "evt_1",
        "type": "email.bounced",
        "data": {
            "email_id": "email_1",
            "to": ["lead@example.com"],
            "from": "Roberts Landscape <info@robertslandscapecod.com>",
        },
    }
    response = client.post(
        "/webhooks/resend",
        content=json.dumps(payload, separators=(",", ":")),
        headers=_svix_headers(payload),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "recorded"
    assert data["event_type"] == "email.bounced"
    assert data["business"] == "roberts"


def test_resend_webhook_rejects_bad_token(client):
    response = client.post(
        "/webhooks/resend?token=wrong",
        json={"id": "evt_bad", "type": "email.delivered", "data": {}},
    )

    assert response.status_code == 403
