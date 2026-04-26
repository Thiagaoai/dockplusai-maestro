# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project overview

**MAESTRO v2.0** — multi-agent AI automation platform for Thiago do Carmo's business ecosystem (Roberts Landscape, DockPlus AI, and 5 others). This is a Python/LangGraph system deployed on a VPS, controlled entirely via a Telegram bot.

**Core mission — never lose sight of this:**
MAESTRO's primary role is **prospector, marketer, and creator**. Every agent, every tool, every automation exists to make the businesses bigger, smarter, faster, and more profitable. Operational efficiency is a means to that end — not the goal. When prioritizing features or making implementation decisions, always ask: does this directly grow revenue, generate leads, or compound the brand? If not, it's secondary.

Design documents: [PRD.md](./PRD.md) and [SDD.md](./SDD.md). Read both before implementing anything non-trivial.

---

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.11 |
| Orchestration | LangGraph 0.2.50+ |
| Agents/Tools | LangChain 0.3+ |
| Observability | LangSmith |
| API | FastAPI 0.115+ |
| DB | Supabase Postgres + pgvector |
| Sessions/Checkpoints | Redis 7+ |
| HTTP client | httpx (async) |
| Validation | Pydantic v2 |
| Retry | tenacity |
| Scheduler | APScheduler |
| Logs | structlog → JSON stdout |
| Deploy | Docker + Compose + Traefik |
| CI/CD | GitHub Actions → SSH deploy |

**Models:** Claude Haiku 4.5 (triage/classification), Claude Sonnet 4.6 (most agents), Claude Opus 4.7 (CEO agent only).

---

## Project folder structure (to be created)

```
maestro/                        ← Python source (main app package)
├── main.py                     ← FastAPI app entry point
├── config.py                   ← Pydantic Settings (reads .env)
├── graph.py                    ← LangGraph orchestrator
├── agents/                     ← 10 main agents (one file each)
├── subagents/                  ← Grouped by parent agent; _shared/brand_guardian.py is transversal
├── tools/                      ← LangChain @tool functions; _enrichment/ subdir for Fase 2
├── memory/                     ← Redis (sessions) + Supabase (long-term + pgvector)
├── profiles/                   ← Business JSON files + _schema.py (Pydantic model)
├── webhooks/                   ← FastAPI routers: telegram.py, ghl.py, gmail.py
├── schedulers/                 ← weekly.py (CFO/CMO/CEO), daily.py (prospecting), monitoring.py
├── prompts/v1/                 ← System prompts, versioned in subdirectories
├── evals/                      ← LangSmith evaluation runners + datasets (Fase 2+)
└── utils/                      ← logging.py, security.py, idempotency.py, pii.py
tests/unit/ tests/integration/ tests/e2e/
scripts/                        ← deploy.sh, seed_supabase.sql, cost_monitor.py, etc.
docs/                           ← SDD.md, PRD.md, RUNBOOK.md, ADR/, TASK.md
```

---

## Architecture

### Entry points → routing

Every inbound event hits FastAPI first, which validates HMAC/secrets and checks idempotency, then dispatches to LangGraph:

- **Telegram message** → Triage node → routes to the correct agent subgraph
- **GHL webhook** → skips Triage, goes directly to SDR Agent
- **Gmail webhook** (Fase 2) → Prospecting reply_classifier subagent
- **APScheduler crons** → CFO (Mon 7h UTC), CMO (Mon 8h UTC), CEO (Mon 9h UTC), Prospecting (daily 6h UTC)

### Agent model

Agents are organized by **function** (SDR, Marketing, CFO, etc.), not by business. Business context is injected via a **profile JSON** file loaded by Triage. This is the function-first pattern — never create per-business agents.

Each main agent is a **LangGraph subgraph**. Each subagent is a **LangChain agent**. Subagents are specialists; agents are orchestrators.

### Human-in-the-loop (HITL)

LangGraph `interrupt()` pauses execution and persists state in Redis. Thiago approves/rejects via Telegram inline keyboards. All external actions (email send, IG post, calendar event, pipeline move) require HITL in Fase 1. Actions >$500 always require HITL in all phases.

### Memory

- **Short-term:** Redis (LangGraph checkpoints, session state, rate limits)
- **Long-term:** Supabase `memory_chunks` table with `VECTOR(1536)` embeddings (OpenAI `text-embedding-3-small`). Hybrid scoring: cosine similarity + recency + importance. `/lembrar isso` sets `importance_score=1.0` manually.

---

## Tools — mandatory pattern

Every tool must follow this template (see SDD §7.2):

```python
@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def tool_name(arg: str, *, idempotency_key: str | None = None) -> dict:
    """Docstring required — LangChain uses it for tool selection."""
    log.info("tool_name_start", ...)
    if idempotency_key and await _is_processed(idempotency_key):
        return await _get_processed_result(idempotency_key)
    # ... implementation with httpx, 30s timeout
    log.info("tool_name_success", ...)
```

Rules: async, type-annotated, retry+tenacity, idempotency check, structlog with PII redacted, 30s timeout on HTTP calls.

---

## Profiles

`maestro/profiles/{business_id}.json` — full schema in `maestro/profiles/_schema.py`. Each profile holds tone, offerings, qualification criteria, decision thresholds, marketing settings, and (for B2B) ICP definition.

Active businesses: `roberts`, `dockplusai` (Fase 1). Adding a profile = 1 JSON file + ~3 days dev, no agent changes.

`decision_thresholds.thiago_approval_above_usd` defaults to 500 — never hardcode this value in agent code.

---

## Supabase schema

Core tables (Fase 1): `conversations`, `agent_runs`, `processed_events`, `audit_log`, `business_metrics`, `leads`, `memory_chunks`, `corrections`, `daily_costs`.

`audit_log` is **append-only** — enforced by Postgres triggers. Never attempt UPDATE/DELETE on it.

`processed_events` is the idempotency table — check before processing any webhook or cron action.

Full DDL: `scripts/seed_supabase.sql`.

---

## Kill switch and cost control

Implemented in `schedulers/monitoring.py`:
- Daily cost >$15 → Telegram INFO alert to Thiago
- Daily cost >$30 → kill switch: cron jobs pause, webhooks still receive but don't invoke LLM
- Monthly cost >$500 → hard kill, SSH manual restart required

`DAILY_COST_KILL_USD` and `DAILY_COST_ALERT_USD` come from `.env`, never hardcoded.

---

## Security requirements (non-negotiable)

- Telegram: validate `X-Telegram-Bot-Api-Secret-Token` + `chat_id` whitelist (Thiago only)
- GHL: HMAC SHA-256 per business, secret from env
- PII (names, phones, emails) must be redacted via `utils/pii.py` before logging
- `.env` never committed — use `.env.example` for documentation
- Stripe is read-only in Fase 1

---

## Testing

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires sandbox Telegram bot + GHL sandbox + Stripe test mode)
pytest tests/integration/ -v

# Single test
pytest tests/unit/test_sdr_qualifier.py::test_name -v

# Coverage check (target ≥70%)
pytest --cov=maestro --cov-report=term-missing
```

Mocks required for all external APIs in unit tests. Integration tests use a separate `@maestro_dev_bot` Telegram bot and a dedicated GHL sandbox location — never run integration tests against production credentials.

---

## Development setup

```bash
# Install dependencies (uses uv)
uv sync

# Local dev with Docker
docker compose -f docker-compose.dev.yml up

# Health check
curl https://localhost/health

# Deploy to VPS (CI/CD also does this on push to main)
bash scripts/deploy.sh
```

`.env` must be populated from `.env.example` before running locally.

---

## Non-obvious implementation gotchas

These are the things that won't be obvious from reading the SDD and will cost hours of debugging. Update this section every time something bites you in production.

### LangGraph + Redis checkpointing
`interrupt()` only works if the graph is compiled with a checkpointer — without it, state is lost on container restart and HITL breaks silently:
```python
from langgraph.checkpoint.redis import RedisSaver
checkpointer = RedisSaver.from_conn_string(settings.REDIS_URL)
graph = workflow.compile(checkpointer=checkpointer, interrupt_before=["hitl_node"])
```

### APScheduler distributed lock
APScheduler fires per-process. With Docker restarts or multi-replica deploys, crons (CFO/CMO/CEO/Prospecting) can fire twice. Always acquire a Redis lock at the start of every cron job:
```python
lock = redis.lock(f"cron:{job_name}", timeout=300)
if not lock.acquire(blocking=False):
    return  # another instance is already running
```

### GHL token scope
GHL has two token types: **location token** (per business) and **agency token** (cross-location). Most endpoints (`/contacts`, `/opportunities`, `/pipelines`) require the location token. Using the agency token returns 403 with a misleading "unauthorized" message.

### `agent_runs.prompt_version` is mandatory
Every agent run must record which prompt version was used. If this field is null, LangSmith evals can't compare across prompt versions. Always read `settings.PROMPT_VERSION` and pass it through to the log call.

### Supabase `audit_log` is append-only
Postgres triggers reject any UPDATE or DELETE on `audit_log`. If code tries to "correct" a log entry it will raise and kill the request. Write a new entry instead.

### structlog JSON output
LangSmith expects structured logs with specific processor order. Use this chain exactly:
```python
structlog.configure(processors=[
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.JSONRenderer(),
])
```

---

## Language rules

- **Thiago → MAESTRO**: always in Portuguese. The system must understand Portuguese input.
- **MAESTRO → Thiago**: Portuguese (summaries, alerts, briefings, inline keyboard labels).
- **MAESTRO → external** (leads, clients, cold email, IG posts, review responses): always in English, matching the business profile tone.
- Never mix languages in a single external-facing output.

## Telegram output format (mobile-first, always)

Every message sent to Thiago via Telegram must follow these rules — he reads on phone, in motion:

- Max 5-6 lines of body text before a decision section
- Use `*bold*` for key numbers and names, not walls of prose
- Every actionable message ends with inline keyboard buttons — never ask for free-text approval
- Button labels: max 3 words, verb-first ("Aprovar", "Editar email", "Rejeitar")
- Never send raw JSON, full email bodies, or data tables — summarize, then offer "Ver completo" button
- One Telegram message per event — never split into multiple sequential messages

## `/stop` kill switch implementation

`/stop` must pause **all** agents, including webhook-triggered ones — not just cron jobs. Implementation:

1. `/stop` command sets `maestro:stopped = 1` in Redis (TTL none)
2. Every agent execution starts with: `if await redis.get("maestro:stopped"): return early`
3. Webhooks still receive and acknowledge (200 OK) to avoid GHL/Telegram retries — events are queued, not dropped
4. `/start` deletes the Redis key and flushes the queue
5. Audit log records every stop/start with timestamp

---

## Pitfalls log

> Update this section after every production incident or hard-won debugging session. One line per entry: date, what happened, what fixed it.

*(empty — fill as lessons are learned)*

---

## Commands — verified ✅

```bash
# Instalar dependências (ambiente local)
pip install -e ".[dev]"

# Rodar todos os testes
python -m pytest tests/ -v

# Rodar um teste específico
python -m pytest tests/e2e/test_vertical_slice.py::test_fake_ghl_lead_creates_approval_card -v

# Cobertura (target ≥70%)
python -m pytest --cov=maestro --cov-report=term-missing

# Dev local com hot reload
docker compose -f docker-compose.dev.yml up

# Prod local
docker compose up -d --build

# Health check
curl http://localhost:8000/health
```

---

## Key constraints

- **No n8n / Make / Zapier** — all integrations are Python tools (ADR-002)
- **No OpenClaw in Fase 1** — Telegram only (ADR-003)
- **No self-hosted LLM in Fase 1** — Anthropic/OpenAI API only (ADR-004)
- **No per-business agents** — function-first, profiles inject business context (ADR-005)
- **Always human approval before external action** — email, post, calendar event, pipeline move
- **Observabilidade total** — every agent run logged to LangSmith + `agent_runs` table, including `prompt_version` field

---

## Roadmap phases

- **Fase 1** (weeks 1-8): 7 agents, Roberts + DockPlus AI, Telegram HITL, crons, hardening
- **Fase 2** (weeks 9-16): Prospecting Agent, Customer Success, Brand Guardian, All Granite + Cape Codder profiles
- **Fase 3** (weeks 17-24): remaining 3 business profiles, Competitive Intelligence, evals, dual-run with Bruna/Joana, gradual release (25→50→75→100%)
