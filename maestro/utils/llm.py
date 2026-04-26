"""Shared Anthropic client helpers, usage accounting, and LangSmith setup."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import json
import os
from typing import Any

import structlog
from anthropic import AsyncAnthropic

log = structlog.get_logger()

SONNET = "claude-sonnet-4-6"
OPUS = "claude-opus-4-7"
HAIKU = "claude-haiku-4-5-20251001"

_MILLION = 1_000_000
_USAGE_COLLECTOR: ContextVar["LlmUsageCollector | None"] = ContextVar(
    "maestro_llm_usage_collector",
    default=None,
)


class UnknownModelPricingError(ValueError):
    """Raised when production would call an LLM with unknown pricing."""


@dataclass
class LlmUsageCollector:
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0

    def add(self, *, model: str, tokens_in: int, tokens_out: int) -> None:
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.cost_usd = round(
            self.cost_usd + calculate_cost_usd(model, tokens_in=tokens_in, tokens_out=tokens_out),
            6,
        )

    def model_dump(self) -> dict[str, int | float]:
        return {
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_usd": self.cost_usd,
        }


@contextmanager
def collect_llm_usage() -> Iterator[LlmUsageCollector]:
    collector = LlmUsageCollector()
    token = _USAGE_COLLECTOR.set(collector)
    try:
        yield collector
    finally:
        _USAGE_COLLECTOR.reset(token)


def current_llm_usage() -> LlmUsageCollector | None:
    return _USAGE_COLLECTOR.get()


def pricing_for_model(model: str) -> tuple[float, float] | None:
    normalized = model.lower()
    if "opus" in normalized and "-4" in normalized:
        return 15.0, 75.0
    if "sonnet" in normalized and "-4" in normalized:
        return 3.0, 15.0
    if "haiku" in normalized:
        return 0.80, 4.0
    return None


def calculate_cost_usd(model: str, *, tokens_in: int, tokens_out: int) -> float:
    pricing = pricing_for_model(model)
    if pricing is None:
        return 0.0
    input_per_mtok, output_per_mtok = pricing
    return round(
        (tokens_in / _MILLION * input_per_mtok)
        + (tokens_out / _MILLION * output_per_mtok),
        6,
    )


def ensure_known_pricing(model: str, settings: Any) -> None:
    if pricing_for_model(model) is not None:
        return
    message = f"Unknown LLM pricing for model: {model}"
    if settings.app_env == "production":
        raise UnknownModelPricingError(message)
    log.warning("llm_unknown_model_pricing", model=model, app_env=settings.app_env)


def usage_from_response(response: Any) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    if isinstance(usage, dict):
        return int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
    return int(getattr(usage, "input_tokens", 0) or 0), int(getattr(usage, "output_tokens", 0) or 0)


def setup_langsmith(settings) -> None:
    """Enable LangSmith tracing if credentials are configured."""
    if settings.langsmith_tracing and settings.langchain_api_key:
        os.environ["LANGSMITH_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.langchain_api_key
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
        os.environ["LANGSMITH_PROJECT"] = settings.langchain_project
        log.info("langsmith_tracing_enabled", project=settings.langchain_project)
        return

    os.environ["LANGSMITH_TRACING_V2"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    if settings.langsmith_tracing:
        log.warning("langsmith_tracing_disabled_missing_api_key", project=settings.langchain_project)


def get_client(settings) -> AsyncAnthropic:
    return AsyncAnthropic(api_key=settings.anthropic_api_key)


async def call_claude(
    system: str,
    user: str,
    *,
    settings,
    model: str = SONNET,
    max_tokens: int = 1024,
) -> str:
    ensure_known_pricing(model, settings)
    client = get_client(settings)
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    tokens_in, tokens_out = usage_from_response(response)
    collector = current_llm_usage()
    if collector is not None:
        collector.add(model=model, tokens_in=tokens_in, tokens_out=tokens_out)
    return response.content[0].text


async def call_claude_json(
    system: str,
    user: str,
    *,
    settings,
    model: str = SONNET,
    max_tokens: int = 1024,
) -> dict:
    """Call Claude and parse JSON from the response. Returns {} on parse failure."""
    import re

    raw = await call_claude(system, user, settings=settings, model=model, max_tokens=max_tokens)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        log.warning("llm_json_parse_failed", raw=raw[:200])
        return {}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError as exc:
        log.warning("llm_json_decode_error", error=str(exc), raw=raw[:200])
        return {}
