from maestro.repositories import store
from maestro.schemas.events import ApprovalRequest


def telegram_message(client, text: str, update_id: int = 900):
    return client.post(
        "/webhooks/telegram",
        json={"update_id": update_id, "message": {"chat": {"id": 123}, "text": text}},
        headers={"x-telegram-bot-api-secret-token": "telegram-test-secret"},
    )


def test_cockpit_status_agents_costs_and_errors(client):
    status = telegram_message(client, "/status", 901)
    assert status.status_code == 200
    assert status.json()["status"] == "ok"
    assert status.json()["system"]["dry_run"] is True

    agents = telegram_message(client, "/agents", 902)
    assert agents.status_code == 200
    assert any(item["name"] == "marketing" for item in agents.json()["agents"])

    costs = telegram_message(client, "/costs", 903)
    assert costs.status_code == 200
    assert "daily_cost_usd" in costs.json()["costs"]

    errors = telegram_message(client, "/errors", 904)
    assert errors.status_code == 200
    assert errors.json()["errors"] == []


def test_cockpit_pending_approvals_lists_items(client):
    approval = ApprovalRequest(
        business="roberts",
        event_id="pending-1",
        action="marketing_publish_or_schedule_post",
        preview={"topic": "spring cleanup"},
    )
    store.approvals[approval.id] = approval

    response = telegram_message(client, "/pending", 905)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["approvals"][0]["id"] == approval.id


def test_cockpit_can_pause_resume_agent_and_block_workflow(client):
    paused = telegram_message(client, "pausa marketing", 906)
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert paused.json()["agent"] == "marketing"

    blocked = telegram_message(client, "post about patio lighting", 907)
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "blocked"
    assert "marketing esta pausado" in blocked.json()["reason"]

    resumed = telegram_message(client, "retoma marketing", 908)
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "resumed"

    accepted = telegram_message(client, "post about patio lighting", 909)
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "approval_requested"
