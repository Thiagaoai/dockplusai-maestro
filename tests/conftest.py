import json
import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

os.environ["APP_ENV"] = "test"
os.environ["STORAGE_BACKEND"] = "memory"
os.environ["DRY_RUN"] = "true"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["ANTHROPIC_API_KEY"] = ""

from maestro.config import get_settings
from maestro.graph import clear_checkpointer
from maestro.main import create_app
from maestro.repositories import store
from maestro.utils.security import compute_hmac_sha256
from maestro.webhooks.telegram import _clear_pending_command


@pytest.fixture(autouse=True)
def reset_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("STORAGE_BACKEND", "memory")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("PROSPECTING_REAL_SEND_ROBERTS", "false")
    monkeypatch.setenv("PROSPECTING_DAILY_SEND_LIMIT_ROBERTS", "100")
    monkeypatch.setenv("RESEND_WEBHOOK_SECRET", "dGVzdF9zZWNyZXQ=")
    monkeypatch.setenv("TELEGRAM_THIAGO_CHAT_ID", "123")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "telegram-test-secret")
    monkeypatch.setenv("GHL_WEBHOOK_SECRET_ROBERTS", "roberts-test-secret")
    monkeypatch.setenv("GHL_WEBHOOK_SECRET_DOCKPLUSAI", "dockplus-test-secret")
    monkeypatch.setenv("APOLLO_API_KEY", "")
    monkeypatch.setenv("HUNTER_API_KEY", "")
    get_settings.cache_clear()
    store.reset()
    clear_checkpointer()
    _clear_pending_command(123)
    yield
    get_settings.cache_clear()
    store.reset()
    clear_checkpointer()
    _clear_pending_command(123)


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _signed_json(secret: str, payload: dict) -> tuple[str, dict[str, str]]:
    body = json.dumps(payload, separators=(",", ":"))
    signature = compute_hmac_sha256(secret, body.encode("utf-8"))
    return body, {"content-type": "application/json", "x-ghl-signature": signature}


@pytest.fixture
def signed_json():
    return _signed_json
