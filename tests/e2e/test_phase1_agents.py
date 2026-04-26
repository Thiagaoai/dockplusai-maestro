from maestro.repositories import store


def telegram_message(client, text: str, update_id: int = 100):
    return client.post(
        "/webhooks/telegram",
        json={"update_id": update_id, "message": {"chat": {"id": 123}, "text": text}},
        headers={"x-telegram-bot-api-secret-token": "telegram-test-secret"},
    )


def test_marketing_agent_creates_approval_from_telegram(client):
    response = telegram_message(client, "post about patio granite Falmouth", 101)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approval_requested"
    assert data["agent"] == "marketing"
    assert data["profit_signal"] == "demand_generation"
    assert data["approval_id"] in store.approvals
    approval = store.approvals[data["approval_id"]]
    assert approval.action == "marketing_publish_or_schedule_post"
    assert "caption" in approval.preview
    assert len(approval.preview["hashtags"]) >= 8


def test_cfo_agent_answers_with_sources_from_telegram(client):
    response = telegram_message(client, "cfo what is margin this month", 102)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["agent"] == "cfo"
    assert data["profit_signal"] == "margin"
    assert len(store.agent_runs) == 1
    assert "Sources" in data["telegram"]["payload"]["text"] or data["telegram"]["dry_run"] is True
    assert store.business_metrics[0]["metric_type"] == "cfo"
    assert store.business_metrics[0]["metric_data"]["sources"]


def test_cmo_agent_prepares_budget_approval(client):
    response = telegram_message(client, "cmo ads roas campaign review", 103)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approval_requested"
    assert data["agent"] == "cmo"
    assert data["profit_signal"] == "roas"
    approval = store.approvals[data["approval_id"]]
    assert approval.action == "cmo_budget_test_dry_run"
    assert approval.preview["creative_tests"]


def test_ceo_agent_generates_briefing(client):
    response = telegram_message(client, "ceo weekly briefing and decisions", 104)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["agent"] == "ceo"
    assert data["profit_signal"] == "decision_quality"
    assert "weekly briefing" in data["message"].lower()
    assert store.business_metrics[0]["metric_type"] == "ceo"


def test_operations_agent_requires_approval_for_external_action(client):
    response = telegram_message(client, "organize vendor note for tomorrow", 105)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approval_requested"
    assert data["agent"] == "operations"
    assert data["approval_id"] in store.approvals


def test_non_sdr_approval_executes_generic_dry_run(client):
    response = telegram_message(client, "post about outdoor living", 106)
    approval_id = response.json()["approval_id"]

    callback = {
        "update_id": 107,
        "callback_query": {
            "id": "callback-marketing-1",
            "data": f"approval:approve:{approval_id}",
            "message": {"chat": {"id": 123}},
        },
    }
    approved = client.post(
        "/webhooks/telegram",
        json=callback,
        headers={"x-telegram-bot-api-secret-token": "telegram-test-secret"},
    )

    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert len(store.dry_run_actions) == 1
    assert store.dry_run_actions[0]["action"] == "marketing_publish_or_schedule_post"
