from __future__ import annotations

from typing import Any

from maestro.telegram.schemas import InlineButton, TelegramReply


def button(text: str, callback_data: str) -> InlineButton:
    return InlineButton(text=text, callback_data=callback_data)


def help_reply() -> TelegramReply:
    return TelegramReply(
        text=(
            "MAESTRO cockpit\n"
            "/status - saude geral\n"
            "/agents - agents e pausas\n"
            "/costs - custo hoje/mes\n"
            "/pending - aprovacoes\n"
            "/errors - erros recentes\n\n"
            "Exemplos: CFO Roberts agora | faz post Roberts sobre spring cleanup | "
            "prospect web hoa | pausa marketing"
        ),
        buttons=[
            [button("Status", "cmd:v1:status"), button("Aprovacoes", "cmd:v1:pending")],
            [button("Custos", "cmd:v1:costs"), button("Agents", "cmd:v1:agents")],
        ],
    )


def simple_reply(text: str) -> TelegramReply:
    return TelegramReply(text=text)


def clarification_reply(message: str, options: list[tuple[str, str]] | None = None) -> TelegramReply:
    rows = [[button(label, data)] for label, data in (options or [])]
    return TelegramReply(text=message, buttons=rows)


def status_reply(data: dict[str, Any]) -> TelegramReply:
    return TelegramReply(
        text=(
            "MAESTRO status\n"
            f"Env: {data['env']} | Dry-run: {str(data['dry_run']).lower()}\n"
            f"Storage: {data['storage_backend']}\n"
            f"Paused: {data['paused']}\n"
            f"Cost today: ${data['daily_cost_usd']:.2f} / ${data['daily_alert_usd']:.2f}\n"
            f"Pending: {data['pending_approvals']} | Errors 24h: {data['recent_errors']}"
        ),
        buttons=[
            [button("Aprovacoes", "cmd:v1:pending"), button("Custos", "cmd:v1:costs")],
            [button("Erros", "cmd:v1:errors"), button("Agents", "cmd:v1:agents")],
        ],
    )


def costs_reply(data: dict[str, Any]) -> TelegramReply:
    return TelegramReply(
        text=(
            "MAESTRO custos\n"
            f"Hoje: ${data['daily_cost_usd']:.4f} / kill ${data['daily_kill_usd']:.2f}\n"
            f"Mes: ${data['monthly_cost_usd']:.4f} / kill ${data['monthly_kill_usd']:.2f}\n"
            f"Status: {data['status']}"
        )
    )


def agents_reply(agents: list[dict[str, Any]], paused: dict[str, list[str]]) -> TelegramReply:
    lines = ["MAESTRO agents"]
    for item in agents:
        status = "paused" if item["name"] in paused.get("agent", []) else "active"
        lines.append(f"- {item['name']}: {status} ({len(item['subagents'])} subagents)")
    return TelegramReply(
        text="\n".join(lines[:12]),
        buttons=[
            [button("Pausar tudo", "cmd:v1:pause_all"), button("Retomar tudo", "cmd:v1:resume_all")],
        ],
    )


def pending_reply(approvals: list[dict[str, Any]]) -> TelegramReply:
    if not approvals:
        return TelegramReply(text="Sem aprovacoes pendentes.")
    lines = ["Aprovacoes pendentes"]
    rows: list[list[InlineButton]] = []
    for approval in approvals[:8]:
        short_id = approval["id"][:8]
        lines.append(f"- {short_id}: {approval['business']} | {approval['action']}")
        rows.append([
            button(f"Aprovar {short_id}", f"approval:approve:{approval['id']}"),
            button(f"Rejeitar {short_id}", f"approval:reject:{approval['id']}"),
        ])
    return TelegramReply(text="\n".join(lines), buttons=rows)


def errors_reply(errors: list[dict[str, Any]]) -> TelegramReply:
    if not errors:
        return TelegramReply(text="Sem erros recentes registrados.")
    lines = ["Erros recentes"]
    for err in errors[:8]:
        lines.append(f"- {err.get('agent') or 'system'}: {err.get('action')} ({err.get('created_at')})")
    return TelegramReply(text="\n".join(lines))

