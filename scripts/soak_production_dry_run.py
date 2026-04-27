"""Production dry-run soak runner for MAESTRO.

This script performs repeated controlled agent executions and verifies that
each run persists a complete operational history:
- agent_runs has prompt_version, tokens, cost, LangSmith URL, dry_run=true
- business_metrics receives the agent output
- audit_log records the soak completion
- cost guard is evaluated before each execution
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass

from maestro.agents.ceo import CEOAgent
from maestro.agents.cfo import CFOAgent
from maestro.agents.cmo import CMOAgent
from maestro.config import Settings, get_settings
from maestro.profiles import load_profile
from maestro.repositories import create_store
from maestro.schemas.events import AgentResult, AgentRunRecord
from maestro.services.cost_monitor import evaluate_cost_guard
from maestro.utils.langsmith import trace_agent_run
from maestro.utils.llm import setup_langsmith


@dataclass
class SoakRecord:
    iteration: int
    business: str
    agent: str
    agent_run_id: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    langsmith_trace_url: str
    dry_run: bool


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run production dry-run soak checks.")
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--interval-seconds", type=float, default=0)
    parser.add_argument("--business", default="roberts")
    parser.add_argument("--agents", default="cfo", help="Comma-separated: cfo,cmo,ceo")
    return parser.parse_args()


async def _run_agent(settings: Settings, agent_name: str, business: str, question: str):
    profile = load_profile(business)
    if agent_name == "cfo":
        return await CFOAgent(settings, profile).run(question)
    if agent_name == "cmo":
        return await CMOAgent(settings, profile).run(question)
    if agent_name == "ceo":
        return await CEOAgent(settings, profile).run(question)
    raise ValueError(f"unsupported soak agent: {agent_name}")


async def _verify_supabase_row(store, run: AgentRunRecord) -> None:
    if not hasattr(store, "client"):
        return
    response = (
        store.client.table("agent_runs")
        .select("id,prompt_version,tokens_in,tokens_out,cost_usd,langsmith_trace_url,dry_run")
        .eq("id", str(run.id))
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    if not rows:
        raise RuntimeError(f"agent_run not found in Supabase: {run.id}")
    row = rows[0]
    required = ("prompt_version", "tokens_in", "tokens_out", "cost_usd", "langsmith_trace_url")
    missing = [key for key in required if row.get(key) in (None, "")]
    if missing:
        raise RuntimeError(f"agent_run missing fields {missing}: {run.id}")
    if row.get("dry_run") is not True:
        raise RuntimeError(f"soak run was not dry_run=true: {run.id}")


def _validate_run(run: AgentRunRecord) -> None:
    if not run.prompt_version:
        raise RuntimeError("missing prompt_version")
    if not run.tokens_in or not run.tokens_out:
        raise RuntimeError(f"missing token usage for run {run.id}")
    if not run.cost_usd:
        raise RuntimeError(f"missing cost_usd for run {run.id}")
    if not run.langsmith_trace_url:
        raise RuntimeError(f"missing langsmith_trace_url for run {run.id}")
    if run.dry_run is not True:
        raise RuntimeError(f"soak run must remain dry_run=true: {run.id}")


async def _main() -> list[SoakRecord]:
    args = _parse_args()
    settings = get_settings()
    if not settings.dry_run:
        raise RuntimeError("Refusing to run soak unless DRY_RUN=true")
    setup_langsmith(settings)
    store = create_store()
    agents = [agent.strip() for agent in args.agents.split(",") if agent.strip()]
    records: list[SoakRecord] = []

    for iteration in range(1, args.cycles + 1):
        for agent_name in agents:
            cost_guard = await evaluate_cost_guard(settings, store, source="soak")
            if cost_guard.should_block:
                raise RuntimeError(f"cost guard blocked soak: {cost_guard.model_dump()}")

            question = f"production dry-run soak iteration {iteration}"
            async with trace_agent_run(
                settings,
                name=f"{agent_name}_soak_dry_run",
                agent=agent_name,
                business=args.business,
                event_id=f"soak:{agent_name}:{args.business}:{iteration}",
                inputs={"question": question, "iteration": iteration},
            ) as trace_run:
                result, run = await _run_agent(settings, agent_name, args.business, question)
                trace_run.end(
                    {
                        "agent_name": result.agent_name,
                        "profit_signal": result.profit_signal,
                        "has_approval": result.approval is not None,
                    }
                )
                trace_run.apply_to_run(run)

            _validate_run(run)
            await store.add_agent_run(run)
            await store.add_business_metric(
                {
                    "business": result.business,
                    "metric_type": f"soak_{agent_name}",
                    "metric_data": result.data,
                    "generated_by": result.agent_name,
                }
            )
            await store.add_audit_log(
                event_type="soak",
                business=result.business,
                agent=result.agent_name,
                action="soak_agent_run_completed",
                payload={
                    "iteration": iteration,
                    "agent_run_id": str(run.id),
                    "tokens_in": run.tokens_in,
                    "tokens_out": run.tokens_out,
                    "cost_usd": run.cost_usd,
                    "langsmith_trace_url": run.langsmith_trace_url,
                    "dry_run": run.dry_run,
                },
            )
            await _verify_supabase_row(store, run)
            records.append(
                SoakRecord(
                    iteration=iteration,
                    business=result.business,
                    agent=result.agent_name,
                    agent_run_id=str(run.id),
                    tokens_in=int(run.tokens_in or 0),
                    tokens_out=int(run.tokens_out or 0),
                    cost_usd=float(run.cost_usd or 0.0),
                    langsmith_trace_url=str(run.langsmith_trace_url),
                    dry_run=run.dry_run,
                )
            )
        if args.interval_seconds and iteration < args.cycles:
            await asyncio.sleep(args.interval_seconds)

    return records


if __name__ == "__main__":
    soak_records = asyncio.run(_main())
    print(json.dumps([asdict(record) for record in soak_records], indent=2, sort_keys=True))
