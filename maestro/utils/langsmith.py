"""LangSmith tracing helpers for MAESTRO agent runs."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import structlog
from langsmith.run_helpers import trace

from maestro.config import Settings
from maestro.utils.llm import LlmUsageCollector, collect_llm_usage

log = structlog.get_logger()


@dataclass
class AgentTrace:
    run: Any | None = None
    usage: LlmUsageCollector | None = None

    def end(self, outputs: dict[str, Any]) -> None:
        if self.usage is not None:
            outputs = {**outputs, "llm_usage": self.usage.model_dump()}
        if self.run is not None:
            self.run.end(outputs=outputs)

    def apply_to_run(self, run: Any) -> None:
        if self.usage is not None:
            run.tokens_in = self.usage.tokens_in or None
            run.tokens_out = self.usage.tokens_out or None
            run.cost_usd = self.usage.cost_usd or None
        run.langsmith_trace_url = self.url

    @property
    def url(self) -> str | None:
        if self.run is None:
            return None
        try:
            return self.run.get_url()
        except Exception as exc:
            log.warning("langsmith_trace_url_unavailable", error=str(exc))
            return None


def langsmith_enabled(settings: Settings) -> bool:
    return bool(settings.langsmith_tracing and settings.langchain_api_key)


@asynccontextmanager
async def trace_agent_run(
    settings: Settings,
    *,
    name: str,
    agent: str,
    business: str,
    event_id: str | None,
    inputs: dict[str, Any],
) -> AsyncIterator[AgentTrace]:
    """Create a LangSmith root trace for one MAESTRO agent execution."""
    with collect_llm_usage() as usage:
        if not langsmith_enabled(settings):
            yield AgentTrace(usage=usage)
            return

        tags = [
            f"business={business}",
            f"agent={agent}",
            f"prompt_version={settings.prompt_version}",
        ]
        metadata = {
            "business": business,
            "agent": agent,
            "event_id": event_id,
            "prompt_version": settings.prompt_version,
            "dry_run": settings.dry_run,
            "app_env": settings.app_env,
        }

        async with trace(
            name,
            run_type="chain",
            inputs=inputs,
            project_name=settings.langchain_project,
            tags=tags,
            metadata=metadata,
        ) as run:
            yield AgentTrace(run=run, usage=usage)
