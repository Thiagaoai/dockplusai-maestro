from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["dev", "staging", "production", "test"] = "dev"
    app_name: str = "MAESTRO"
    log_level: str = "INFO"
    prompt_version: str = "v1"
    dry_run: bool = True

    webhook_base_url: str = "http://localhost:8000"

    telegram_bot_token: str = ""
    telegram_webhook_secret: str = "dev-telegram-secret"
    telegram_thiago_chat_id: int = 0

    ghl_webhook_secret_roberts: str = "dev-roberts-secret"
    ghl_webhook_secret_dockplusai: str = "dev-dockplusai-secret"

    supabase_url: str = ""
    supabase_service_key: str = ""
    redis_url: str = "redis://localhost:6379/0"

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    langchain_api_key: str = ""
    langchain_project: str = "maestro-dev"

    daily_cost_alert_usd: float = 15.0
    daily_cost_kill_usd: float = 30.0
    monthly_cost_kill_usd: float = 500.0
    thiago_approval_threshold_usd: float = 500.0

    storage_backend: Literal["memory", "supabase"] = "memory"

    profile_dir: str = Field(default="maestro/profiles")

    def ghl_secret_for_business(self, business: str) -> str:
        if business == "roberts":
            return self.ghl_webhook_secret_roberts
        if business == "dockplusai":
            return self.ghl_webhook_secret_dockplusai
        return ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
