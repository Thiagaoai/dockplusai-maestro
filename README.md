# MAESTRO v2.0

MAESTRO is a FastAPI-based operational growth system for Roberts Landscape and DockPlus AI.

The first implemented slice is intentionally narrow:

1. GHL lead webhook enters the system.
2. HMAC and idempotency are checked.
3. SDR creates a deterministic lead score, email draft, and meeting slots.
4. Telegram approval card is sent or dry-run recorded.
5. Approval executes a dry-run external action.
6. `agent_runs`, `processed_events`, and `audit_log` are recorded.

## Local Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
.venv/bin/uvicorn maestro.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

Run tests:

```bash
.venv/bin/pytest
```

## Current Scope

Implemented:

- FastAPI app and `/health`
- Telegram webhook for `/stop`, `/start`, and approval callbacks
- GHL webhook for Roberts and DockPlus AI
- HMAC validation
- chat ID whitelist
- in-memory dev store mirroring Supabase core tables
- deterministic SDR vertical slice
- dry-run approval action
- core tests

Still external/dry-run:

- real Telegram send when `DRY_RUN=false` and token is present
- Supabase persistence
- LangGraph Redis checkpointing
- real GHL/Gmail/Calendar/Postforme integrations
