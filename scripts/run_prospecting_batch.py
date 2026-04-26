"""
Fluxo completo de Prospecting no LangGraph + Telegram + Resend.

1. Cria 10 leads + prospectos na fila (InMemoryStore isolado)
2. Roda LangGraph: triage -> prospecting -> hitl (interrupt)
3. Envia card de aprovação no Telegram REAL
4. Auto-aprova e envia 10 emails via Resend

Rode:
  .venv/bin/python scripts/run_prospecting_batch.py
"""
import asyncio
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv

sys.path.insert(0, "/Users/thiagodocarmo/Downloads/agent.maestro")
load_dotenv("/Users/thiagodocarmo/Downloads/agent.maestro/.env")

from langgraph.types import Command

from maestro.config import Settings, get_settings
from maestro.graph import MaestroGraph, clear_checkpointer
from maestro.graph_state import MaestroState
from maestro.repositories import store as store_singleton
from maestro.repositories.store import InMemoryStore
from maestro.schemas.events import LeadRecord
from maestro.utils.logging import configure_logging

configure_logging("INFO")


TEST_CONTACTS = [
    {"name": "Alice Johnson", "email": "dockplusai+1@gmail.com", "phone": "508-111-0001"},
    {"name": "Bob Smith", "email": "dockplusai+2@gmail.com", "phone": "508-111-0002"},
    {"name": "Carol White", "email": "dockplusai+3@gmail.com", "phone": "508-111-0003"},
    {"name": "David Brown", "email": "dockplusai+4@gmail.com", "phone": "508-111-0004"},
    {"name": "Eva Davis", "email": "dockplusai+5@gmail.com", "phone": "508-111-0005"},
    {"name": "Frank Miller", "email": "dockplusai+6@gmail.com", "phone": "508-111-0006"},
    {"name": "Grace Wilson", "email": "dockplusai+7@gmail.com", "phone": "508-111-0007"},
    {"name": "Henry Moore", "email": "dockplusai+8@gmail.com", "phone": "508-111-0008"},
    {"name": "Ivy Taylor", "email": "dockplusai+9@gmail.com", "phone": "508-111-0009"},
    {"name": "Jack Anderson", "email": "dockplusai+10@gmail.com", "phone": "508-111-0010"},
]


async def seed_prospects(store: InMemoryStore) -> list[str]:
    source_refs = []
    for i, contact in enumerate(TEST_CONTACTS, 1):
        lead = LeadRecord(
            event_id=f"seed:prospect:{i}",
            business="roberts",
            name=contact["name"],
            email=contact["email"],
            phone=contact["phone"],
            source="manual_seed",
        )
        await store.upsert_lead(lead)
        source_ref = f"seed_ref_{i:03d}"
        source_refs.append(source_ref)
        await store.upsert_prospect_queue_item({
            "business": "roberts",
            "lead_id": str(lead.id),
            "source_type": "customer_file",
            "source_name": "manual_seed_batch",
            "source_ref": source_ref,
            "status": "queued",
            "priority": 90,
            "sequence_bucket": "batch_a",
            "payload": {
                "lead_name": contact["name"],
                "has_email": True,
                "has_phone": True,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    return source_refs


async def main():
    print("=" * 60)
    print("MAESTRO — Prospecting Batch Flow (LangGraph + Telegram)")
    print("=" * 60)

    # Forca settings fresh com dry_run=False e storage=memory
    get_settings.cache_clear()
    os.environ["STORAGE_BACKEND"] = "memory"
    settings = Settings(dry_run=False, storage_backend="memory", app_env="dev")

    # Substitui o singleton store por um InMemoryStore fresco
    fresh_store = InMemoryStore()
    import maestro.repositories
    maestro.repositories.store = fresh_store
    # Tambem precisa injetar nos modulos que ja importaram o singleton
    import maestro.graph_nodes as gn
    gn.store = fresh_store

    clear_checkpointer()

    # 1. Popula fila
    print("\n[1/5] Criando 10 leads + prospectos na fila...")
    source_refs = await seed_prospects(fresh_store)
    print(f"       {len(source_refs)} prospectos criados.")

    # 2. Monta grafo
    print("\n[2/5] Iniciando LangGraph...")
    graph = MaestroGraph(settings=settings, store=fresh_store)

    event_id = f"prospecting:roberts:{uuid4()}"
    thread_id = f"prospecting:{event_id}"
    initial_state: MaestroState = {
        "business": "roberts",
        "event_id": event_id,
        "input_type": "cron",
        "target_agent": "prospecting",
        "input_data": {
            "text": "prepare prospecting batch",
            "last_business": "roberts",
            "mode": "owned",
            "batch_size": 10,
        },
    }

    # 3. Roda ate o HITL (interrupt)
    print("\n[3/5] Executando grafo ate o HITL (Telegram approval card)...")
    config = {"configurable": {"thread_id": thread_id}}
    result = await graph._graph.ainvoke(initial_state, config=config)

    if result.get("__interrupt__"):
        approval = result.get("approval")
        approval_id = approval["id"] if approval else None
        print(f"       Pause no HITL. Approval ID: {approval_id}")
        print(f"       Card enviado para Telegram chat {settings.telegram_thiago_chat_id}")

        # 4. Auto-aprova
        print("\n[4/5] Resumindo grafo com aprovacao...")
        result2 = await graph._graph.ainvoke(
            Command(resume=True), config=config
        )
        print("       Grafo completado.")

        execution = result2.get("execution_result", {})
        print(f"\n[5/5] RESULTADO:")
        print(f"       Status: {execution.get('status', 'N/A')}")
        print(f"       Enviados: {execution.get('sent_count', 'N/A')}")
        print(f"       Pulados:  {execution.get('skipped_count', 'N/A')}")
        for s in execution.get("sent", []):
            print(f"         ✉️  {s.get('source_ref')} -> email_id={s.get('email_id')}")
        for s in execution.get("skipped", []):
            print(f"         ⚠️  {s.get('source_ref')} -> {s.get('reason')}")
    else:
        print("       Grafo finalizado sem HITL.")
        print(f"       Resultado: {result.get('agent_message')}")

    print("\n" + "=" * 60)
    print("FIM")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
