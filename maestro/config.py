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

    ghl_token_roberts: str = ""
    ghl_token_dockplusai: str = ""
    ghl_webhook_secret_roberts: str = "dev-roberts-secret"
    ghl_webhook_secret_dockplusai: str = "dev-dockplusai-secret"

    supabase_url: str = ""
    supabase_service_key: str = ""
    redis_url: str = "redis://localhost:6379/0"

    resend_api_key: str = ""
    resend_from_roberts: str = "Roberts Landscape <info@robertslandscapecod.com>"
    resend_reply_to_roberts: str = "roberts.ldc.cape@gmail.com"
    resend_from_dockplusai: str = "DockPlus AI <hello@dockplusai.com>"
    resend_reply_to_dockplusai: str = ""

    composio_cli_path: str = "~/.composio/composio"
    composio_enabled: bool = True
    ghl_location_id_roberts: str = ""
    ghl_location_id_dockplusai: str = ""

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    langchain_api_key: str = ""
    langchain_project: str = "maestro-dev"

    apollo_api_key: str = ""
    hunter_api_key: str = ""
    tavily_api_key: str = ""
    google_maps_api_key: str = ""
    apify_token: str = ""
    perplexity_api_key: str = ""

    daily_cost_alert_usd: float = 15.0
    daily_cost_kill_usd: float = 30.0
    monthly_cost_kill_usd: float = 500.0
    thiago_approval_threshold_usd: float = 500.0

    prospecting_batch_size_roberts: int = 10
    prospecting_schedule_timezone: str = "America/New_York"
    prospecting_schedule_hours_roberts: str = "8,11,15,17"
    prospecting_customer_per_scrape_cycle: int = 2
    prospecting_scrape_per_cycle: int = 1
    prospecting_web_locations_roberts: str = "Cape Cod, South Shore, Martha's Vineyard, Nantucket"
    roberts_promo_discount_percent: int = 10
    roberts_website_url: str = "https://robertslandscapecod.com"

    storage_backend: Literal["memory", "supabase"] = "memory"

    profile_dir: str = Field(default="maestro/profiles")

    def ghl_secret_for_business(self, business: str) -> str:
        if business == "roberts":
            return self.ghl_webhook_secret_roberts
        if business == "dockplusai":
            return self.ghl_webhook_secret_dockplusai
        return ""

    def ghl_location_for_business(self, business: str) -> str:
        if business == "roberts":
            return self.ghl_location_id_roberts
        if business == "dockplusai":
            return self.ghl_location_id_dockplusai
        return ""

    def ghl_token_for_business(self, business: str) -> str:
        if business == "roberts":
            return self.ghl_token_roberts
        if business == "dockplusai":
            return self.ghl_token_dockplusai
        return ""

    def resend_from_for_business(self, business: str) -> str:
        if business == "roberts":
            return self.resend_from_roberts
        if business == "dockplusai":
            return self.resend_from_dockplusai
        return self.resend_from_dockplusai or self.resend_from_roberts

    def resend_reply_to_for_business(self, business: str) -> str:
        if business == "roberts":
            return self.resend_reply_to_roberts
        if business == "dockplusai":
            return self.resend_reply_to_dockplusai
        return ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
