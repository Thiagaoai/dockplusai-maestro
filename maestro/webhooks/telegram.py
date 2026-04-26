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
    await telegram.send_message(f"✅ Ação {status_text} e executada." if approved else f"❌ Ação {status_text}.")

    await store.mark_processed(
        event_key, "telegram", {"status": status_text, "graph_result": result}, business=approval.business
    )
    return {"status": status_text, "graph_result": result}
