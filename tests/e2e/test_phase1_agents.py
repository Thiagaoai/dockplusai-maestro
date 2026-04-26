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


def test_cfo_agent_recommends_actions_with_conditional_approval(client):
    response = telegram_message(client, "cfo what is margin this month", 102)

    assert response.status_code == 200
    data = response.json()
    # Roberts has avg_ticket=20000, margin analysis triggers actions > $500 threshold
    assert data["status"] == "approval_requested"
    assert data["agent"] == "cfo"
    assert data["profit_signal"] == "margin"
    assert data["approval_id"] in store.approvals
    approval = store.approvals[data["approval_id"]]
    assert approval.action == "cfo_financial_actions_dry_run"
    assert "actions" in approval.preview
    assert len(approval.preview["actions"]) > 0


def test_cmo_agent_skips_approval_when_below_threshold(client):
    response = telegram_message(client, "cmo ads roas campaign review", 103)

    assert response.status_code == 200
    data = response.json()
    # Roberts budget=$3000, 10% shift=$300, below $500 threshold → no approval
    assert data["status"] == "completed"
    assert data["agent"] == "cmo"
    assert data["profit_signal"] == "roas"
    # No approval created, but agent run and business metric are recorded
    assert len(store.agent_runs) == 1
    assert store.agent_runs[0].agent_name == "cmo"


def test_ceo_agent_generates_briefing_with_strategic_approval(client):
    response = telegram_message(client, "ceo weekly briefing and decisions", 104)

    assert response.status_code == 200
    data = response.json()
    # CEO decisions have estimated_impact_usd > $500 threshold (avg_ticket * 0.05 = 1000)
    assert data["status"] == "approval_requested"
    assert data["agent"] == "ceo"
    assert data["profit_signal"] == "decision_quality"
    assert data["approval_id"] in store.approvals
    approval = store.approvals[data["approval_id"]]
    assert approval.action == "ceo_strategic_decisions_dry_run"
    assert "decisions" in approval.preview
    assert "briefing_summary" in approval.preview


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
