import os

from maestro.config import Settings, get_settings
from maestro.utils.llm import setup_langsmith


def test_langchain_tracing_v2_env_enables_langsmith(monkeypatch):
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "lsv2-test")
    monkeypatch.setenv("LANGCHAIN_PROJECT", "maestro-test")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.langsmith_tracing is True
    assert settings.langchain_api_key == "lsv2-test"
    assert settings.langchain_project == "maestro-test"


def test_setup_langsmith_exports_langsmith_and_langchain_env(monkeypatch):
    keys = (
        "LANGSMITH_TRACING_V2",
        "LANGCHAIN_TRACING_V2",
        "LANGSMITH_API_KEY",
        "LANGCHAIN_API_KEY",
        "LANGSMITH_PROJECT",
        "LANGCHAIN_PROJECT",
    )
    for key in keys:
        monkeypatch.setenv(key, "")

    settings = Settings(
        app_env="test",
        langsmith_tracing=True,
        langchain_api_key="lsv2-test",
        langchain_project="maestro-test",
    )

    setup_langsmith(settings)

    assert os.environ["LANGSMITH_TRACING_V2"] == "true"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "lsv2-test"
    assert os.environ["LANGCHAIN_API_KEY"] == "lsv2-test"
    assert os.environ["LANGSMITH_PROJECT"] == "maestro-test"
    assert os.environ["LANGCHAIN_PROJECT"] == "maestro-test"
