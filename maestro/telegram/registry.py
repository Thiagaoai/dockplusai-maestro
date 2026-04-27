from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WorkflowSpec:
    aliases: tuple[str, ...]
    required_fields: tuple[str, ...] = ()
    requires_hitl: bool = True
    risk: str = "medium"


@dataclass(frozen=True)
class AgentSpec:
    aliases: tuple[str, ...]
    workflows: dict[str, WorkflowSpec]
    subagents: tuple[str, ...] = ()
    default_workflow: str = "run_agent"
    active: bool = True
    metadata: dict[str, str] = field(default_factory=dict)


BUSINESS_ALIASES = {
    "roberts": "roberts",
    "roberts landscape": "roberts",
    "landscape": "roberts",
    "dockplus": "dockplusai",
    "dockplus ai": "dockplusai",
    "dockplusai": "dockplusai",
}


AGENT_REGISTRY: dict[str, AgentSpec] = {
    "sdr": AgentSpec(
        aliases=("sdr", "sales", "lead", "leads", "vendas", "follow-up", "follow up"),
        workflows={
            "process_sdr_lead": WorkflowSpec(("qualifica lead", "qualify lead", "lead"), ("lead_text", "business")),
            "follow_up": WorkflowSpec(("follow up", "follow-up", "reengage", "reengajar"), ("business",)),
        },
        subagents=("lead_qualifier", "email_drafter", "meeting_scheduler", "re_engagement"),
        default_workflow="process_sdr_lead",
    ),
    "prospecting": AgentSpec(
        aliases=("prospecting", "prospect", "prospecta", "prospectar", "outbound"),
        workflows={
            "run_prospecting_batch": WorkflowSpec(("batch", "roberts 10", "owned list"), ("business",)),
            "run_web_prospecting": WorkflowSpec(("web", "busca", "search"), ("target", "business")),
            "run_dockplus_apollo": WorkflowSpec(("apollo", "dockplus apollo"), ("business",)),
        },
        subagents=("icp_definer", "list_builder", "enricher", "personalizer"),
        default_workflow="run_prospecting_batch",
    ),
    "marketing": AgentSpec(
        aliases=("marketing", "mkt", "post", "posts", "caption", "instagram", "conteudo", "content"),
        workflows={
            "create_marketing_post": WorkflowSpec(("post", "caption", "instagram", "conteudo"), ("topic", "business")),
            "revise_brand": WorkflowSpec(("brand", "tom", "review"), ("text", "business")),
        },
        subagents=("content_creator", "caption_writer", "hashtag_strategist", "posting_scheduler", "brand_guardian"),
        default_workflow="create_marketing_post",
    ),
    "cfo": AgentSpec(
        aliases=("cfo", "finance", "financeiro", "margin", "margem", "cashflow", "invoice"),
        workflows={"run_cfo_briefing": WorkflowSpec(("cfo", "finance", "margin", "cashflow"), ("business",), False)},
        subagents=("invoice_reconciler", "margin_analyst", "cashflow_forecaster", "recommend_actions"),
        default_workflow="run_cfo_briefing",
    ),
    "cmo": AgentSpec(
        aliases=("cmo", "ads", "roas", "meta", "google ads", "campaign", "budget"),
        workflows={"run_cmo_review": WorkflowSpec(("cmo", "ads", "roas", "budget"), ("business",), False)},
        subagents=("ad_performance_analyst", "budget_allocator", "creative_tester"),
        default_workflow="run_cmo_review",
    ),
    "ceo": AgentSpec(
        aliases=("ceo", "briefing", "strategy", "estrategia", "summary", "resumo"),
        workflows={"run_ceo_briefing": WorkflowSpec(("ceo", "briefing", "strategy"), ("business",), False)},
        subagents=("weekly_briefing", "decision_preparer"),
        default_workflow="run_ceo_briefing",
    ),
    "operations": AgentSpec(
        aliases=("operations", "ops", "calendar", "agenda", "agendar", "pipeline", "task", "tarefa"),
        workflows={"prepare_operations_task": WorkflowSpec(("calendar", "agenda", "pipeline", "task"), ("text", "business"))},
        subagents=("calendar_manager", "follow_up_sender", "ghl_pipeline_mover"),
        default_workflow="prepare_operations_task",
    ),
    "brand_guardian": AgentSpec(
        aliases=("brand", "brand guardian", "guardian", "tom", "tone"),
        workflows={"revise_brand": WorkflowSpec(("review", "revisar", "tom"), ("text", "business"), False)},
        subagents=(),
        default_workflow="revise_brand",
    ),
}


def normalize_business(text: str, default: str = "roberts") -> str:
    lowered = text.lower()
    for alias, business in BUSINESS_ALIASES.items():
        if alias in lowered:
            return business
    return default


def normalize_agent(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.lower().strip()
    if lowered in AGENT_REGISTRY:
        return lowered
    for agent, spec in AGENT_REGISTRY.items():
        if lowered in spec.aliases:
            return agent
    return None


def find_agent_in_text(text: str) -> str | None:
    lowered = text.lower()
    matches: list[tuple[int, str]] = []
    for agent, spec in AGENT_REGISTRY.items():
        for alias in spec.aliases:
            idx = lowered.find(alias)
            if idx >= 0:
                matches.append((idx, agent))
                break
    if not matches:
        return None
    return sorted(matches, key=lambda item: item[0])[0][1]

