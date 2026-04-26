"""Shared Anthropic client helpers and LangSmith setup."""

import json
import os

import structlog
from anthropic import AsyncAnthropic

log = structlog.get_logger()

SONNET = "claude-sonnet-4-6"
OPUS = "claude-opus-4-7"
HAIKU = "claude-haiku-4-5-20251001"


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
    client = get_client(settings)
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
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
