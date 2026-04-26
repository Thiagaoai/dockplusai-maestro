from maestro.repositories import store


def test_fake_ghl_lead_creates_approval_card(client, signed_json):
    payload = {
        "eventId": "lead-1",
        "contact": {
            "firstName": "Maria",
            "lastName": "Silva",
            "email": "maria@example.com",
            "phone": "508-555-0100",
        },
        "opportunity": {"monetaryValue": 22000, "source": "Meta Ads"},
        "message": "Need an estimate for a patio soon.",
    }
    body, headers = signed_json("roberts-test-secret", payload)

    response = client.post("/webhooks/ghl/roberts", content=body, headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approval_requested"
    assert data["dry_run"] is True
    assert data["approval_id"] in store.approvals
    assert len(store.agent_runs) == 1
    assert store.agent_runs[0].profit_signal == "conversion"
    assert len(store.audit_log) == 1
    assert "lead-1" in store.processed_events


def test_duplicate_ghl_webhook_does_not_duplicate_records(client, signed_json):
    payload = {
        "eventId": "lead-dup",
        "contact": {"name": "John Doe", "email": "john@example.com"},
        "opportunity": {"monetaryValue": 15000},
    }
    body, headers = signed_json("roberts-test-secret", payload)

    first = client.post("/webhooks/ghl/roberts", content=body, headers=headers)
    second = client.post("/webhooks/ghl/roberts", content=body, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    assert len(store.leads) == 1
    assert len(store.agent_runs) == 1
    assert len(store.approvals) == 1


def test_invalid_ghl_hmac_is_rejected(client):
    response = client.post(
        "/webhooks/ghl/roberts",
        json={"eventId": "bad"},
        headers={"x-ghl-signature": "wrong"},
    )

    assert response.status_code == 401


def test_telegram_chat_id_not_authorized_is_rejected(client):
    response = client.post(
        "/webhooks/telegram",
        json={"update_id": 1, "message": {"chat": {"id": 999}, "text": "/stop"}},
        headers={"x-telegram-bot-api-secret-token": "telegram-test-secret"},
    )

    assert response.status_code == 403


def test_stop_blocks_agent_execution(client, signed_json):
    stop = client.post(
        "/webhooks/telegram",
        json={"update_id": 10, "message": {"chat": {"id": 123}, "text": "/stop"}},
        headers={"x-telegram-bot-api-secret-token": "telegram-test-secret"},
    )
    assert stop.status_code == 200
    assert stop.json()["status"] == "paused"

    payload = {"eventId": "lead-paused", "contact": {"name": "Paused Lead"}}
    body, headers = signed_json("roberts-test-secret", payload)
    response = client.post("/webhooks/ghl/roberts", content=body, headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "paused"
    assert len(store.leads) == 0
    assert len(store.agent_runs) == 0


def test_approval_callback_executes_dry_run_once(client, signed_json):
    payload = {
        "eventId": "lead-approve",
        "contact": {"name": "Approve Lead", "email": "approve@example.com"},
        "opportunity": {"monetaryValue": 18000},
    }
    body, headers = signed_json("roberts-test-secret", payload)
    lead_response = client.post("/webhooks/ghl/roberts", content=body, headers=headers)
    approval_id = lead_response.json()["approval_id"]

    callback = {
        "update_id": 20,
        "callback_query": {
            "id": "callback-1",
            "data": f"approval:approve:{approval_id}",
            "message": {"chat": {"id": 123}},
        },
    }
    first = client.post(
        "/webhooks/telegram",
        json=callback,
        headers={"x-telegram-bot-api-secret-token": "telegram-test-secret"},
    )
    second = client.post(
        "/webhooks/telegram",
        json=callback,
        headers={"x-telegram-bot-api-secret-token": "telegram-test-secret"},
    )

    assert first.status_code == 200
    assert first.json()["status"] == "approved"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    assert len(store.dry_run_actions) == 1
