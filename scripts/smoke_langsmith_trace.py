"""Controlled production dry-run smoke for LangSmith + LLM accounting.

Run with DRY_RUN=true and real LANGSMITH/ANTHROPIC credentials.
"""

import asyncio

from maestro.agents.cfo import CFOAgent
from maestro.config import get_settings
from maestro.profiles import load_profile
from maestro.repositories import create_store
from maestro.utils.langsmith import trace_agent_run
from maestro.utils.llm import setup_langsmith


async def main() -> None:
    settings = get_settings()
    setup_langsmith(settings)
    store = create_store()
    business = "roberts"

    async with trace_agent_run(
        settings,
        name="cfo_smoke_dry_run",
        agent="cfo",
        business=business,
        event_id="smoke:cfo:langsmith",
        inputs={"question": "controlled production dry-run smoke"},
    ) as trace_run:
        result, run = await CFOAgent(settings, load_profile(business)).run(
            "controlled production dry-run smoke"
        )
        trace_run.end(
            {
                "agent_name": result.agent_name,
                "profit_signal": result.profit_signal,
                "has_approval": result.approval is not None,
            }
        )
        trace_run.apply_to_run(run)

    await store.add_agent_run(run)
    print(
        {
            "agent_run_id": str(run.id),
            "business": run.business,
            "agent": run.agent_name,
            "prompt_version": run.prompt_version,
            "tokens_in": run.tokens_in,
            "tokens_out": run.tokens_out,
            "cost_usd": run.cost_usd,
            "langsmith_trace_url": run.langsmith_trace_url,
            "dry_run": run.dry_run,
        }
    )


if __name__ == "__main__":
    asyncio.run(main())
