import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from maestro.agents.prospecting import ProspectingAgent
from maestro.config import Settings, get_settings
from maestro.graph import MaestroGraph
from maestro.memory.redis_session import clear_stopped, set_stopped
from maestro.repositories import store
from maestro.schemas.events import ApprovalStatus
from maestro.services import DryRunActionExecutor, TelegramService
from maestro.utils.security import verify_telegram_chat, verify_telegram_secret

router = APIRouter(prefix="/webhooks/telegram", tags=["webhooks"])


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
    text = (message.get("text") or "").strip()
    if update_id and await store.is_processed(f"telegram:{update_id}"):
        return {"status": "duplicate"}

    telegram = TelegramService(settings)
    if text == "/stop":
        store.paused = True
        set_stopped()  # persist in Redis — survives container restart
        await store.add_audit_log(
            event_type="config_change",
            action="agents_paused",
            payload={"source": "telegram", "update_id": update_id},
        )
        await telegram.send_message("🔴 MAESTRO pausado. Webhooks recebidos mas agentes não vão rodar.")
        result = {"status": "paused"}
    elif text == "/start":
        store.paused = False
        clear_stopped()  # clear Redis flag
        await store.add_audit_log(
            event_type="config_change",
            action="agents_resumed",
            payload={"source": "telegram", "update_id": update_id},
        )
        await telegram.send_message("🟢 MAESTRO retomado. Todos os agentes ativos.")
        result = {"status": "resumed"}
    elif text.lower().startswith("prospect web"):
        parts = text.split()
        target = " ".join(parts[2:]).strip()
        if not target:
            _set_pending_command(chat_id, {"command": "prospect_web", "business": "roberts"})
            await telegram.send_message(
                "Qual target voce quer prospectar? Exemplo: prospect web hoa"
            )
            result = {"status": "needs_target", "agent": "prospecting", "business": "roberts"}
        else:
            _clear_pending_command(chat_id)
            result = await _run_roberts_web_prospecting(target, settings, telegram)
    elif _get_pending_command(chat_id).get("command") == "prospect_web":
        target = text.strip()
        if not target or target.startswith("/"):
            _clear_pending_command(chat_id)
            result = {"status": "cancelled", "agent": "prospecting", "business": "roberts"}
        else:
            _clear_pending_command(chat_id)
            result = await _run_roberts_web_prospecting(target, settings, telegram)
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
            result = {
                "status": "approval_requested",
                "agent": "prospecting",
                "business": "roberts",
                "approval_id": approval.id,
                "batch_size": len(approval.preview.get("prospects", [])),
                "mode": mode,
            }
        else:
            result = {"status": "empty", "agent": "prospecting", "business": "roberts", "mode": mode}
    else:
        graph = MaestroGraph(settings, store)
        result = await graph.handle_text_message(text)

    if update_id:
        await store.mark_processed(f"telegram:{update_id}", "telegram", result)
    return result


def _agent_run_output(run) -> dict:
    try:
        return json.loads(run.output)
    except (TypeError, json.JSONDecodeError):
        return {}


def _set_pending_command(chat_id: int, command: dict[str, Any]) -> None:
    if not hasattr(store, "telegram_pending_commands"):
        return
    store.telegram_pending_commands[chat_id] = command


def _get_pending_command(chat_id: int) -> dict[str, Any]:
    if not hasattr(store, "telegram_pending_commands"):
        return {}
    return store.telegram_pending_commands.get(chat_id, {})


def _clear_pending_command(chat_id: int) -> None:
    if hasattr(store, "telegram_pending_commands"):
        store.telegram_pending_commands.pop(chat_id, None)


async def _run_roberts_web_prospecting(
    target: str,
    settings: Settings,
    telegram: TelegramService,
) -> dict:
    approval, run = await ProspectingAgent(settings, store).prepare_roberts_web_search_batch(target)
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
            "target": target,
        }

    output = _agent_run_output(run)
    if output.get("status") == "error":
        await telegram.send_message(
            "Falha na busca web de prospeccao.\n"
            f"Target: {target}\n"
            f"Erro: {output.get('error')}"
        )
        return {
            "status": "error",
            "agent": "prospecting",
            "business": "roberts",
            "mode": "web",
            "target": target,
            "error": output.get("error"),
        }

    await telegram.send_message(
        f"Nao encontrei contatos com email para '{target}' nas regioes configuradas."
    )
    return {
        "status": "empty",
        "agent": "prospecting",
        "business": "roberts",
        "mode": "web",
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
