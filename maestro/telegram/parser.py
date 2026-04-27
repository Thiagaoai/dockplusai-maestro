from __future__ import annotations

import re

from maestro.config import Settings
from maestro.telegram.registry import find_agent_in_text, normalize_agent, normalize_business
from maestro.telegram.schemas import CommandIntent, IntentType

_SOURCES = {"tavily", "google", "hunter", "apollo", "apify", "perplexity"}


async def parse_command(text: str, settings: Settings, *, last_business: str = "roberts") -> CommandIntent:
    raw = text.strip()
    lowered = raw.lower().strip()
    if not lowered:
        return CommandIntent(intent_type=IntentType.help, action="help", raw_text=raw)

    slash = _parse_slash(raw, lowered)
    if slash:
        return slash

    admin = _parse_admin(raw, lowered, last_business)
    if admin:
        return admin

    status = _parse_status(raw, lowered)
    if status:
        return status

    approval = _parse_approval(raw, lowered)
    if approval:
        return approval

    workflow = _parse_workflow(raw, lowered, last_business)
    if workflow:
        return workflow

    if settings.anthropic_api_key:
        parsed = await _parse_llm(raw, settings, last_business)
        if parsed:
            return parsed

    return CommandIntent(intent_type=IntentType.legacy, action="legacy", raw_text=raw, confidence=0.3)


def _parse_slash(raw: str, lowered: str) -> CommandIntent | None:
    if not lowered.startswith("/"):
        return None
    command = lowered.split()[0]
    mapping = {
        "/help": (IntentType.help, "help"),
        "/status": (IntentType.status, "system_status"),
        "/agents": (IntentType.status, "agent_status"),
        "/costs": (IntentType.status, "cost_status"),
        "/cost": (IntentType.status, "cost_status"),
        "/pending": (IntentType.approval, "list_pending"),
        "/approvals": (IntentType.approval, "list_pending"),
        "/errors": (IntentType.status, "recent_errors"),
        "/stop": (IntentType.admin, "pause_all"),
        "/start": (IntentType.admin, "resume_all"),
    }
    if command in mapping:
        intent_type, action = mapping[command]
        return CommandIntent(intent_type=intent_type, action=action, raw_text=raw)
    if command == "/prospect":
        return _parse_workflow(raw.replace("/", "", 1), lowered.replace("/", "", 1), "roberts")
    return CommandIntent(intent_type=IntentType.help, action="help", raw_text=raw, confidence=0.5)


def _parse_admin(raw: str, lowered: str, last_business: str) -> CommandIntent | None:
    if lowered in {"para tudo", "pausa tudo", "pause all", "stop all"}:
        return CommandIntent(intent_type=IntentType.admin, action="pause_all", raw_text=raw)
    if lowered in {"retoma tudo", "resume all", "start all", "continua tudo"}:
        return CommandIntent(intent_type=IntentType.admin, action="resume_all", raw_text=raw)

    match = re.search(r"\b(pausa|pause|parar)\s+([a-z0-9 _-]+)", lowered)
    if match:
        target = match.group(2).strip()
        agent = normalize_agent(target)
        if agent:
            return CommandIntent(intent_type=IntentType.admin, action="pause_agent", agent=agent, raw_text=raw)
        business = normalize_business(target, default="")
        if business:
            return CommandIntent(intent_type=IntentType.admin, action="pause_business", business=business, raw_text=raw)

    match = re.search(r"\b(retoma|resume|start|continua)\s+([a-z0-9 _-]+)", lowered)
    if match:
        target = match.group(2).strip()
        agent = normalize_agent(target)
        if agent:
            return CommandIntent(intent_type=IntentType.admin, action="resume_agent", agent=agent, raw_text=raw)
        business = normalize_business(target, default="")
        if business:
            return CommandIntent(intent_type=IntentType.admin, action="resume_business", business=business, raw_text=raw)
    return None


def _parse_status(raw: str, lowered: str) -> CommandIntent | None:
    if lowered in {"status", "status geral", "como esta", "saude", "health"}:
        return CommandIntent(intent_type=IntentType.status, action="system_status", raw_text=raw)
    if "custo" in lowered or "cost" in lowered or "gasto" in lowered:
        return CommandIntent(intent_type=IntentType.status, action="cost_status", raw_text=raw)
    if "erro" in lowered or "error" in lowered or "falhou" in lowered:
        return CommandIntent(intent_type=IntentType.status, action="recent_errors", raw_text=raw)
    if "agents" in lowered or "agentes" in lowered:
        return CommandIntent(intent_type=IntentType.status, action="agent_status", raw_text=raw)
    if lowered.startswith("status "):
        agent = find_agent_in_text(lowered)
        return CommandIntent(intent_type=IntentType.status, action="agent_status", agent=agent, raw_text=raw)
    return None


def _parse_approval(raw: str, lowered: str) -> CommandIntent | None:
    if "pendente" in lowered or "approval" in lowered or "aprova" in lowered:
        if lowered in {"pendentes", "aprovacoes", "aprovações", "pending approvals"}:
            return CommandIntent(intent_type=IntentType.approval, action="list_pending", raw_text=raw)
    return None


def _parse_workflow(raw: str, lowered: str, last_business: str) -> CommandIntent | None:
    business = normalize_business(lowered, last_business)
    if "prospect" in lowered or "prospecta" in lowered:
        source = next((source for source in _SOURCES if source in lowered), "tavily")
        if lowered.strip() in {"prospect roberts web", "prospectar roberts web"}:
            return CommandIntent(
                intent_type=IntentType.workflow,
                action="run_prospecting_batch",
                agent="prospecting",
                workflow="run_prospecting_batch",
                business=business,
                raw_text=raw,
                entities={"batch_size": None, "mode": "web"},
            )
        if " web" in f" {lowered}" or any(source in lowered for source in _SOURCES):
            target = _target_after_web(lowered, source)
            missing = [] if target else ["target"]
            return CommandIntent(
                intent_type=IntentType.workflow,
                action="run_web_prospecting",
                agent="prospecting",
                workflow="run_web_prospecting",
                business=business,
                raw_text=raw,
                entities={"target": target, "source": source},
                missing_fields=missing,
            )
        batch_size = _first_int(lowered)
        mode = "hybrid" if "hybrid" in lowered else "web" if "scrape" in lowered else "owned"
        return CommandIntent(
            intent_type=IntentType.workflow,
            action="run_prospecting_batch",
            agent="prospecting",
            workflow="run_prospecting_batch",
            business=business,
            raw_text=raw,
            entities={"batch_size": batch_size, "mode": mode},
        )

    if any(word in lowered for word in ("post", "caption", "instagram", "conteudo", "conteúdo")):
        topic = _topic_after(lowered, ("sobre", "about", "post", "caption"))
        return CommandIntent(
            intent_type=IntentType.workflow,
            action="create_marketing_post",
            agent="marketing",
            workflow="create_marketing_post",
            business=business,
            raw_text=raw,
            entities={"topic": topic},
            missing_fields=[] if topic else ["topic"],
        )

    agent = find_agent_in_text(lowered)
    if agent in {"cfo", "cmo", "ceo"}:
        action = {"cfo": "run_cfo_briefing", "cmo": "run_cmo_review", "ceo": "run_ceo_briefing"}[agent]
        return CommandIntent(
            intent_type=IntentType.workflow,
            action=action,
            agent=agent,
            workflow=action,
            business=business,
            raw_text=raw,
            entities={"text": raw},
        )
    if agent == "operations":
        return CommandIntent(
            intent_type=IntentType.workflow,
            action="prepare_operations_task",
            agent="operations",
            workflow="prepare_operations_task",
            business=business,
            raw_text=raw,
            entities={"text": raw},
        )
    return None


async def _parse_llm(raw: str, settings: Settings, last_business: str) -> CommandIntent | None:
    try:
        from maestro.utils.llm import HAIKU, call_claude_json

        data = await call_claude_json(
            "You parse Telegram commands for MAESTRO. Return JSON only with keys: intent_type, action, business, agent, workflow, entities, confidence, missing_fields.",
            f"Last business: {last_business}\nCommand: {raw}",
            settings=settings,
            model=HAIKU,
            max_tokens=300,
        )
        if not data:
            return None
        intent_type = IntentType(data.get("intent_type", "unknown"))
        return CommandIntent(
            intent_type=intent_type,
            action=str(data.get("action") or "unknown"),
            business=data.get("business") or last_business,
            agent=normalize_agent(data.get("agent")),
            workflow=data.get("workflow"),
            entities=data.get("entities") or {},
            confidence=float(data.get("confidence") or 0.5),
            missing_fields=data.get("missing_fields") or [],
            raw_text=raw,
        )
    except Exception:
        return None


def _first_int(text: str) -> int | None:
    match = re.search(r"\b(\d{1,3})\b", text)
    return int(match.group(1)) if match else None


def _target_after_web(text: str, source: str) -> str:
    cleaned = re.sub(r"\b(prospect|prospecta|prospectar|web|busca|buscar|com|usando|using)\b", " ", text)
    cleaned = cleaned.replace(source, " ")
    cleaned = re.sub(r"\b(roberts|dockplus|dockplusai|ai)\b", " ", cleaned)
    return " ".join(cleaned.split()).strip()


def _topic_after(text: str, markers: tuple[str, ...]) -> str:
    for marker in markers:
        if marker in text:
            candidate = text.split(marker, 1)[1]
            candidate = re.sub(r"\b(roberts|dockplus|dockplusai)\b", " ", candidate)
            return " ".join(candidate.split()).strip()
    return ""
