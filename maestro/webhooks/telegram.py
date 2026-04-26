import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from maestro.agents.prospecting import ProspectingAgent
from maestro.config import Settings, get_settings
from maestro.graph import MaestroGraph
from maestro.memory.redis_session import (
    clear_stopped,
    delete_session,
    get_session,
    set_session,
    set_stopped,
)
from maestro.repositories import store
from maestro.schemas.events import ApprovalStatus
from maestro.services import DryRunActionExecutor, TelegramService
from maestro.utils.security import verify_telegram_chat, verify_telegram_secret
from maestro.utils.telegram_commands import parse_prospect_web_command

router = APIRouter(prefix="/webhooks/telegram", tags=["webhooks"])

PENDING_COMMAND_TTL_SECONDS = 900
_PENDING_COMMANDS_FALLBACK: dict[int, dict[str, Any]] = {}


def _chat_id_from_update(payload: dict) -> int:
    if "message" in payload:
        return int(payload["message"].get("chat", {}).get("id") or 0)
    if "callback_query" in payload:
        return int(payload["callback_query"].get("message", {}).get("chat", {}).get("id") or 0)
    return 0


def _prospecting_summary_text(action_result: dict) -> str | None:
    if action_result.get("action") != "prospecting_batch_send_html":
        return None
    attempted = action_result.get("attempted_count")
    if attempted is None:
        attempted = (
            action_result.get("sent_count", 0)
            + action_result.get("skipped_count", 0)
            + action_result.get("failed_count", 0)
        )
    sent = action_result.get("sent_count", 0)
    failed = action_result.get("failed_count", 0)
    skipped = action_result.get("skipped_count", 0)
    table_errors = action_result.get("table_error_count", 0)
    names = [
        item.get("property_name") or item.get("email") or item.get("source_ref")
        for item in action_result.get("sent", [])[:10]
    ]
    sent_lines = "\n".join(f"- {name}" for name in names if name)
    suffix = f"\n\nSent properties:\n{sent_lines}" if sent_lines else ""
    return (
        "Prospecting emails completed.\n"
        f"Attempted/Sent: {attempted}/{sent}\n"
        f"Failed: {failed}\n"
        f"Skipped: {skipped}\n"
        f"Clients Web Verified table errors: {table_errors}"
        f"{suffix}"
    )


@router.post("")
async def telegram_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    verify_telegram_secret(x_telegram_bot_api_secret_token, settings.telegram_webhook_secret)
    payload = await request.json()
    verify_telegram_chat(_chat_id_from_update(payload), settings.telegram_thiago_chat_id)

    if "message" in payload:
        return await _handle_message(payload, settings)
    if "callback_query" in payload:
        return await _handle_callback(payload, settings)
    return {"status": "ignored"}


async def _handle_message(payload: dict, settings: Settings) -> dict:
    update_id = str(payload.get("update_id", ""))
    message = payload["message"]
    chat_id = int(message.get("chat", {}).get("id") or 0)
    text = _message_text(message)
    command = parse_prospect_web_command(text)
    if update_id and await store.is_processed(f"telegram:{update_id}"):
        return {"status": "duplicate"}

    telegram = TelegramService(settings)
    if text == "/stop":
        _clear_pending_command(chat_id)
        result = await _do_stop(update_id, telegram)
    elif text == "/start":
        _clear_pending_command(chat_id)
        result = await _do_start(update_id, telegram)
    elif command is not None:
        target = command["target"]
        source = command.get("source", "tavily")
        if not target:
            _set_pending_command(chat_id, {"command": "prospect_web", "business": "roberts", "source": source})
            src_hint = f" [{source}]" if source != "tavily" else ""
            await telegram.send_message(
                f"Qual target voce quer prospectar{src_hint}? Exemplo: hoa"
            )
            result = {"status": "needs_target", "agent": "prospecting", "business": "roberts", "source": source}
        else:
            _clear_pending_command(chat_id)
            result = await _run_roberts_web_prospecting(target, source, settings, telegram)
    elif text.lower().startswith("prospect roberts"):
        parts = text.split()
        batch_size = settings.prospecting_batch_size_roberts
        mode = "owned"
        if len(parts) >= 3:
            if parts[2].isdigit():
                batch_size = int(parts[2])
            elif parts[2].lower() in {"web", "scrape"}:
                mode = "web"
            elif parts[2].lower() == "hybrid":
                mode = "hybrid"
        if len(parts) >= 4 and parts[3].isdigit():
            batch_size = int(parts[3])
        result = await _do_roberts_batch(batch_size, mode, settings, telegram)
    else:
        result = await _handle_nlp(text, chat_id, update_id, settings, telegram)

    if update_id:
        await store.mark_processed(f"telegram:{update_id}", "telegram", result)
    return result


async def _do_stop(update_id: str, telegram: TelegramService) -> dict:
    store.paused = True
    set_stopped()
    await store.add_audit_log(
        event_type="config_change",
        action="agents_paused",
        payload={"source": "telegram", "update_id": update_id},
    )
    await telegram.send_message("🔴 MAESTRO pausado. Webhooks recebidos mas agentes não vão rodar.")
    return {"status": "paused"}


async def _do_start(update_id: str, telegram: TelegramService) -> dict:
    store.paused = False
    clear_stopped()
    await store.add_audit_log(
        event_type="config_change",
        action="agents_resumed",
        payload={"source": "telegram", "update_id": update_id},
    )
    await telegram.send_message("🟢 MAESTRO retomado. Todos os agentes ativos.")
    return {"status": "resumed"}


async def _do_roberts_batch(
    batch_size: int,
    mode: str,
    settings: Settings,
    telegram: TelegramService,
) -> dict:
    approval, run = await ProspectingAgent(settings, store).prepare_roberts_batch(batch_size, mode=mode)
    await store.add_agent_run(run)
    if approval:
        await store.create_approval(approval)
        await store.add_audit_log(
            event_type="agent_decision",
            business="roberts",
            agent="prospecting",
            action="approval_requested",
            payload={"approval_id": approval.id, "batch_size": len(approval.preview.get("prospects", []))},
        )
        await telegram.send_approval_card(approval.id, approval.preview)
        return {
            "status": "approval_requested",
            "agent": "prospecting",
            "business": "roberts",
            "approval_id": approval.id,
            "batch_size": len(approval.preview.get("prospects", [])),
            "mode": mode,
        }
    return {"status": "empty", "agent": "prospecting", "business": "roberts", "mode": mode}


async def _handle_nlp(
    text: str,
    chat_id: int,
    update_id: str,
    settings: Settings,
    telegram: TelegramService,
) -> dict:
    from maestro.utils.intent import parse_telegram_intent

    intent = await parse_telegram_intent(text, settings)

    if intent.action == "stop":
        _clear_pending_command(chat_id)
        return await _do_stop(update_id, telegram)

    if intent.action == "start":
        _clear_pending_command(chat_id)
        return await _do_start(update_id, telegram)

    if intent.action == "prospect_web":
        if not intent.target:
            _set_pending_command(chat_id, {"command": "prospect_web", "business": "roberts", "source": intent.source})
            src_hint = f" [{intent.source}]" if intent.source != "tavily" else ""
            await telegram.send_message(
                f"Qual tipo de negócio voce quer prospectar{src_hint}? Exemplo: hoa, escola, hotel, marina"
            )
            return {"status": "needs_target", "agent": "prospecting", "business": "roberts", "source": intent.source}
        _clear_pending_command(chat_id)
        return await _run_roberts_web_prospecting(intent.target, intent.source, settings, telegram)

    if intent.action == "prospect_batch":
        _clear_pending_command(chat_id)
        return await _do_roberts_batch(
            intent.batch_size or settings.prospecting_batch_size_roberts,
            intent.mode,
            settings,
            telegram,
        )

    # NLP returned unknown — use pending command as fallback before giving up
    pending = _get_pending_command(chat_id)
    if pending.get("command") == "prospect_web":
        source = pending.get("source", "tavily")
        target = text.strip()
        if not target or target.startswith("/"):
            _clear_pending_command(chat_id)
            return {"status": "cancelled", "agent": "prospecting", "business": "roberts"}
        _clear_pending_command(chat_id)
        return await _run_roberts_web_prospecting(target, source, settings, telegram)

    await telegram.send_message(
        "Não entendi. Exemplos:\n"
        "• *quero prospectar escolas*\n"
        "• *busca hotéis com perplexity*\n"
        "• *prospect web hoa*\n"
        "• *roda um batch de 5*\n"
        "• */stop* ou */start*"
    )
    graph = MaestroGraph(settings, store)
    return await graph.handle_text_message(text)


def _agent_run_output(run) -> dict:
    try:
        return json.loads(run.output)
    except (TypeError, json.JSONDecodeError):
        return {}


def _message_text(message: dict[str, Any]) -> str:
    return str(message.get("text") or message.get("caption") or "").strip()


def _set_pending_command(chat_id: int, command: dict[str, Any]) -> None:
    set_session(_pending_command_session_id(chat_id), command, ttl=PENDING_COMMAND_TTL_SECONDS)
    _PENDING_COMMANDS_FALLBACK[chat_id] = command


def _get_pending_command(chat_id: int) -> dict[str, Any]:
    pending = get_session(_pending_command_session_id(chat_id))
    if pending:
        return pending
    return _PENDING_COMMANDS_FALLBACK.get(chat_id, {})


def _clear_pending_command(chat_id: int) -> None:
    delete_session(_pending_command_session_id(chat_id))
    _PENDING_COMMANDS_FALLBACK.pop(chat_id, None)


def _pending_command_session_id(chat_id: int) -> str:
    return f"telegram:pending:{chat_id}"


async def _run_roberts_web_prospecting(
    target: str,
    source: str,
    settings: Settings,
    telegram: TelegramService,
) -> dict:
    approval, run = await ProspectingAgent(settings, store).prepare_roberts_web_search_batch(
        target, source=source
    )
    await store.add_agent_run(run)
    if approval:
        await store.create_approval(approval)
        await store.add_audit_log(
            event_type="agent_decision",
            business="roberts",
            agent="prospecting",
            action="approval_requested",
            payload={
                "approval_id": approval.id,
                "target": target,
                "source": source,
                "batch_size": len(approval.preview.get("prospects", [])),
            },
        )
        await telegram.send_approval_card(approval.id, approval.preview)
        return {
            "status": "approval_requested",
            "agent": "prospecting",
            "business": "roberts",
            "approval_id": approval.id,
            "batch_size": len(approval.preview.get("prospects", [])),
            "mode": "web",
            "source": source,
            "target": target,
        }

    output = _agent_run_output(run)
    if output.get("status") == "error":
        await telegram.send_message(
            f"Falha na busca web [{source}].\n"
            f"Target: {target}\n"
            f"Erro: {output.get('error')}"
        )
        return {
            "status": "error",
            "agent": "prospecting",
            "business": "roberts",
            "mode": "web",
            "source": source,
            "target": target,
            "error": output.get("error"),
        }

    await telegram.send_message(
        f"Nao encontrei contatos com email para '{target}' [{source}] nas regioes configuradas."
    )
    return {
        "status": "empty",
        "agent": "prospecting",
        "business": "roberts",
        "mode": "web",
        "source": source,
        "target": target,
    }


async def _handle_callback(payload: dict, settings: Settings) -> dict:
    query = payload["callback_query"]
    callback_id = str(query.get("id") or "")
    data = query.get("data") or ""
    event_key = f"telegram_callback:{callback_id or data}"
    if await store.is_processed(event_key):
        return {"status": "duplicate"}

    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "approval":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_callback")
    decision_str, approval_id = parts[1], parts[2]
    if decision_str not in {"approve", "reject"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_decision")

    approval = await store.get_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="approval_not_found")
    if approval.status != ApprovalStatus.pending:
        result = {"status": "already_decided", "approval_status": approval.status}
        await store.mark_processed(event_key, "telegram", result, business=approval.business)
        return result

    thread_id = await store.get_thread_for_approval(approval_id)
    if not thread_id:
        # Fallback for approvals created before graph migration
        approved = decision_str == "approve"
        approval = await store.decide_approval(approval_id, approved)
        await store.add_audit_log(
            event_type="human_approval",
            business=approval.business if approval else None,
            agent="sdr",
            action="approved" if approved else "rejected",
            payload={"approval_id": approval_id, "callback_id": callback_id},
        )
        if approved and approval:
            executor = DryRunActionExecutor(store)
            action_result = await executor.execute_approval(approval)
            summary_text = _prospecting_summary_text(action_result)
            if summary_text:
                await TelegramService(settings).send_message(summary_text)
            result = {"status": "approved", "action": action_result}
        else:
            result = {"status": "rejected"}
        await store.mark_processed(event_key, "telegram", result, business=approval.business if approval else None)
        return result

    approved = decision_str == "approve"
    await store.decide_approval(approval_id, approved)
    graph = MaestroGraph(settings, store)
    result = await graph.resume(thread_id, approved)

    telegram = TelegramService(settings)
    status_text = "approved" if approved else "rejected"
    execution_result = result.get("result", {}).get("execution_result", {})
    summary_text = _prospecting_summary_text(execution_result) if approved else None
    if summary_text:
        await telegram.send_message(summary_text)
    else:
        await telegram.send_message(f"✅ Ação {status_text} e executada." if approved else f"❌ Ação {status_text}.")

    await store.mark_processed(
        event_key, "telegram", {"status": status_text, "graph_result": result}, business=approval.business
    )
    return {"status": status_text, "graph_result": result}
