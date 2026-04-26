# AGENTS.md — MAESTRO v2.0

> This file is for AI coding agents. Read it before modifying anything.
> For human contributors, see [README.md](./README.md).
> For product requirements, see [PRD.md](./PRD.md) (Portuguese).
> For system design, see [SDD.md](./SDD.md) (Portuguese).
> For Claude Code guidance, see [CLAUDE.md](./CLAUDE.md).

---

## Project overview

**MAESTRO v2.0** is a FastAPI-based operational growth automation platform for Thiago do Carmo's business ecosystem (Roberts Landscape, DockPlus AI, and others planned).

**Current reality (as of repo state):** This is an early MVP vertical slice. Only the SDR inbound-lead flow is wired end-to-end, and it runs deterministically (no LLM yet). Everything else is planned or stubbed.

**Core mission:** MAESTRO exists to grow the businesses — prospecting, marketing, and creation first. Operational efficiency is a means to that end.

**Language conventions:**
- **Thiago → MAESTRO:** Portuguese (Telegram commands, summaries, alerts).
- **MAESTRO → external** (leads, clients, emails, posts): English, matching the business profile tone.
- **Code, docstrings, logs:** English.

---

## Tech stack

| Layer | Choice | Status |
|---|---|---|
| Language | Python 3.11 | Implemented |
| API framework | FastAPI 0.115+ | Implemented |
| Validation | Pydantic v2 + pydantic-settings | Implemented |
| HTTP client | httpx (async) | Implemented |
| Logs | structlog → JSON stdout | Implemented |
| Retry | tenacity | In `pyproject.toml`, not yet wired in tools |
| Scheduler | APScheduler | Planned (Fase 1) |
| Orchestration | LangGraph 0.2.50+ | Planned — `graph.py` is a deterministic shell |
| Agents/Tools | LangChain 0.3+ | Planned |
| Observability | LangSmith | Config vars exist, not wired |
| DB | Supabase Postgres + pgvector | Schema exists in `scripts/seed_supabase.sql`; runtime uses in-memory store |
| Sessions/Checkpoints | Redis 7+ | `docker-compose.yml` includes Redis; not wired to app yet |
| Deploy | Docker + Compose | Implemented |
| CI/CD | GitHub Actions → pytest + coverage | Implemented |

**Models (planned, not wired):**
- Claude Haiku 4.5 (triage/classification)
- Claude Sonnet 4.6 (most agents)
- Claude Opus 4.7 (CEO agent only)

---

## Build and run commands

```bash
# Local Python setup
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
# ... edit .env with your secrets ...

# Run locally (Python)
.venv/bin/uvicorn maestro.main:app --reload

# Run locally (Docker)
docker compose -f docker-compose.dev.yml up

# Health check
curl http://localhost:8000/health

# Run tests
.venv/bin/pytest
# With coverage
.venv/bin/pytest --cov=maestro --cov-report=term-missing
```

**CI:** `.github/workflows/ci.yml` runs `pytest --cov=maestro --cov-report=term-missing` on every push and PR.

**Adding a new dependency:** If you introduce a new external package, add it to `pyproject.toml` under `[project.dependencies]` (or `[project.optional-dependencies.dev]` for test/lint tools). Do not run `pip install` directly without updating `pyproject.toml`.

---

## Project structure

```
maestro/                         ← Python source package
├── main.py                      ← FastAPI app factory (create_app)
├── config.py                    ← Pydantic Settings, reads .env
├── graph.py                     ← MaestroOrchestrator (deterministic shell, not LangGraph yet)
├── agents/
│   ├── triage.py                ← Keyword-based stub (will become LLM-based)
│   └── sdr.py                   ← SDRAgent: deterministic qualification, email draft, slot suggestion
├── webhooks/
│   ├── telegram.py              ← Telegram webhook: /stop, /start, approval callbacks
│   └── ghl.py                   ← GHL webhook: HMAC validation, lead extraction, dispatch to SDR
├── services/
│   ├── telegram.py              ← TelegramService: send approval cards / messages (dry-run aware)
│   └── actions.py               ← DryRunActionExecutor: records what would happen without calling APIs
├── repositories/
│   └── store.py                 ← InMemoryStore: mirrors Supabase core tables for dev/test
├── schemas/
│   └── events.py                ← Pydantic models: LeadIn, LeadRecord, ApprovalRequest, AgentRunRecord, AuditLogRecord, ProcessedEvent
├── profiles/
│   ├── _schema.py               ← Pydantic model for business profiles
│   ├── loader.py                ← JSON profile loader (cached)
│   ├── roberts.json             ← Roberts Landscape profile
│   └── dockplusai.json          ← DockPlus AI profile
├── utils/
│   ├── logging.py               ← structlog JSON configuration
│   ├── security.py              ← HMAC verification, Telegram secret/chat validation
│   └── pii.py                   ← Email/phone redaction for logs
└── tools/                       ← LangChain @tool functions (placeholder, empty init)

tests/
├── conftest.py                  ← pytest fixtures: reset_state, client, signed_json helper
├── unit/test_health.py          ← Health endpoint test
└── e2e/test_vertical_slice.py   ← Full E2E: fake GHL lead → approval card → approve → dry-run action

scripts/
├── seed_supabase.sql            ← Core Supabase DDL (conversations, agent_runs, processed_events, audit_log, etc.)
├── cost_monitor.py              ← Planned: cost kill switch
└── healthcheck.sh               ← VPS health check script

docs/
├── ADR/                         ← Architectural Decision Records (empty, to be created)
├── RUNBOOK.md                   ← Incident runbook (emergency stop, rollback, first checks)
├── PRD.md                       ← Product Requirements Document (Portuguese)
├── SDD.md                       ← System Design Document (Portuguese)
├── TASK.md                      ← Detailed implementation task list (Portuguese)
└── CLAUDE.md                    ← Claude Code guidance
```

### How to add a new agent (current deterministic shell)

The orchestrator is a plain Python class (`MaestroOrchestrator`), not LangGraph yet.
To wire a new agent end-to-end:

1. **Create the agent class** in `maestro/agents/{name}.py`  
   Accept `(settings: Settings, profile: BusinessProfile)` in `__init__`.
2. **Add schema models** in `maestro/schemas/events.py` if the agent produces new records.
3. **Wire into the orchestrator** in `maestro/graph.py` — add a new `handle_{name}_*` method and call it from the appropriate webhook/router.
4. **Add unit tests** in `tests/unit/test_{name}.py` — mock all external APIs.
5. **Add E2E test** in `tests/e2e/` using the in-memory store and `client` fixture.

Follow the SDR agent as the reference implementation.

---

## Code style guidelines

- **Python 3.11+** with type hints everywhere.
- **Pydantic v2** for all data models and settings.
- **Async-first:** all I/O-bound code is `async`.
- **Line length:** 100 (Ruff config in `pyproject.toml`).
- **Logs:** structured JSON via `structlog`. Do not use `print` or plain `logging` directly.
- **PII:** redact emails and phones before logging using `utils/pii.redact_pii`.
- **Tool pattern (planned, not yet enforced):**
  - `async` function with type annotations
  - `@tool` + `@retry(stop=stop_after_attempt(3), wait=wait_exponential(...))`
  - `idempotency_key` parameter and `_is_processed()` / `_mark_processed()` guards
  - `structlog` start/success events
  - 30s timeout on HTTP calls

---

## Testing instructions

```bash
# All tests (default)
pytest

# Unit only
pytest tests/unit/ -v

# E2E only
pytest tests/e2e/ -v

# Single test
pytest tests/e2e/test_vertical_slice.py::test_fake_ghl_lead_creates_approval_card -v

# Coverage check (target ≥70%)
pytest --cov=maestro --cov-report=term-missing
```

**Test conventions:**
- `conftest.py` resets the global `InMemoryStore` and `Settings` cache before every test (`autouse=True`).
- Unit tests mock all external APIs.
- E2E tests use the in-memory store and deterministic agents — no external API calls are made.
- Integration tests (not yet written) would use a sandbox Telegram bot and GHL sandbox.

### Testing webhooks

Use the `signed_json` fixture from `conftest.py` to generate valid HMAC signatures for GHL tests:

```python
def test_ghl_webhook(client, signed_json):
    payload = {"event": "addContact", "contact": {"name": "Alice"}}
    body, headers = signed_json("roberts-test-secret", payload)
    resp = client.post("/webhooks/ghl/roberts", content=body, headers=headers)
    assert resp.status_code == 200
```

### InMemoryStore is async-by-contract

All store methods are `async` even though the current in-memory implementation does not perform I/O. This is intentional: when the backend switches to Supabase, callers will not need to change. Always `await` store calls.

---

## Architecture (current implementation)

### Entry points

1. **Telegram webhook** `POST /webhooks/telegram`
   - Validates `X-Telegram-Bot-Api-Secret-Token` and `chat_id` whitelist.
   - Handles `/stop` (pauses agents), `/start` (resumes agents), and approval callback queries.
   - Idempotency checked via `processed_events`.

2. **GHL webhook** `POST /webhooks/ghl/{business}`
   - Validates HMAC SHA-256 per business.
   - Extracts lead, checks idempotency, dispatches to `MaestroOrchestrator.handle_inbound_lead`.
   - If agents are paused (`store.paused == True`), acknowledges with 200 but skips execution.

### Orchestration flow (SDR vertical slice)

```
GHL webhook → verify HMAC → idempotency check → MaestroOrchestrator
  → load business profile → SDRAgent.prepare_lead()
    → _qualify() (deterministic scoring)
    → _draft_email() (template-based, profile-aware)
    → _suggest_slots() (next 3 weekday afternoons)
    → create LeadRecord + ApprovalRequest + AgentRunRecord
    → store in InMemoryStore
    → telegram.send_approval_card()
    → mark event processed
```

When Thiago clicks **Approve** via Telegram inline keyboard:
```
POST /webhooks/telegram (callback query)
  → extract approval_id + action from callback_data
  → verify duplicate via processed_events
  → update InMemoryStore.approvals[approval_id].status
  → if approved:
       DryRunActionExecutor.execute_sdr_approval()
         → record in dry_run_actions table
         → append to audit_log
  → send confirmation / rejection message to Thiago via Telegram
```

**Callback data format:** `approval:{approval_id}:action` where action is `approve`, `reject`, or `edit`.

**Duplicate protection:** Every callback query is checked against `processed_events` before mutating state. Telegram may retry failed deliveries.

### Memory / persistence

**Current:** `InMemoryStore` (singleton in `repositories/store.py`) mirrors these Supabase tables:
- `processed_events` — idempotency
- `leads` — lead records
- `agent_runs` — every agent execution
- `audit_log` — append-only hash chain (SHA-256 Merkle-style)
- `approvals` — human approval requests
- `dry_run_actions` — recorded actions when `DRY_RUN=true`

**Planned:** Swap to Supabase by changing `storage_backend` setting. The `scripts/seed_supabase.sql` file contains the full DDL including append-only audit_log triggers.

### Profiles

Business context is injected via JSON profiles in `maestro/profiles/{business_id}.json`. Each profile contains tone, offerings, qualification criteria, decision thresholds, marketing settings, and (for B2B) ICP definition.

Active profiles: `roberts`, `dockplusai`.

Adding a new business = 1 JSON file following `_schema.py` + no agent code changes.

**Never hardcode `thiago_approval_above_usd` (default 500) in agent code.** Read it from the profile.

**Profile loader cache:** `maestro/profiles/loader.py` caches JSON profiles on first read. Restart the dev server after editing a `.json` profile to see changes.

---

## Security considerations

These are non-negotiable and already enforced where marked:

- **Telegram:** `X-Telegram-Bot-Api-Secret-Token` header validation + `chat_id` whitelist (Thiago only) — ✅ enforced.
- **GHL:** HMAC SHA-256 per business, secret from `.env` — ✅ enforced.
- **PII:** redact names, phones, emails before logging — ✅ `utils/pii.py` exists, used in some log calls.
- **Secrets:** `.env` never committed — `.env.example` documents all vars.
- **Stripe:** read-only in Fase 1 (not yet wired).
- **Kill switch:** `/stop` pauses all agent execution while keeping webhooks alive — ✅ implemented.

---

## Configuration

All config lives in `maestro/config.py` (Pydantic Settings) and reads from `.env`.

Key settings:
- `APP_ENV` — `dev`, `staging`, `production`, `test`
- `DRY_RUN` — `true` by default. When `true`, Telegram messages and external actions are logged but not sent.
- `STORAGE_BACKEND` — `memory` (current) or `supabase` (planned)
- `TELEGRAM_THIAGO_CHAT_ID` — whitelist for Telegram access
- `GHL_WEBHOOK_SECRET_*` — per-business HMAC secrets
- `PROMPT_VERSION` — recorded in every `agent_run`
- Cost thresholds: `DAILY_COST_ALERT_USD` (15), `DAILY_COST_KILL_USD` (30), `MONTHLY_COST_KILL_USD` (500)

---

## Configuration gotcha: settings are cached

`get_settings()` uses `@lru_cache`. Changing `.env` or `os.environ` at runtime has **no effect** until you call `get_settings.cache_clear()`.

Tests that mutate env vars (via `monkeypatch`) must always clear the cache. The `conftest.py` `reset_state` fixture does this automatically (`autouse=True`). If you write a test that touches settings, ensure the cache is cleared before assertions.

---

## Adding a new configuration variable

When introducing a new env var / setting:

1. Add the typed field to `maestro/config.py` with a sensible default for dev/test.
2. Document it in `.env.example` with a comment.
3. If tests need a specific value, add it to the `reset_state` fixture in `tests/conftest.py`.

---

## Deployment

- **Docker:** `Dockerfile` uses Python 3.11 slim. `docker-compose.yml` runs app + Redis.
- **Dev compose:** `docker-compose.dev.yml` mounts source for hot reload.
- **CI/CD:** GitHub Actions runs tests on every push/PR. Deploy to VPS is planned (SSH via `scripts/deploy.sh`).
- **VPS target:** Ubuntu 22+, Docker, Traefik (reverse proxy + Let's Encrypt).

---

## What is implemented vs. planned

### Implemented (Week 0.5–1)
- FastAPI scaffold, `/health`
- Telegram webhook: `/stop`, `/start`, approval callbacks
- GHL webhook: HMAC validation, lead extraction, business routing
- Chat ID whitelist
- In-memory dev store (idempotency, audit log, approvals, agent runs)
- Deterministic SDR vertical slice (rule-based scoring, email drafting, slot suggestion)
- Dry-run approval action executor
- Core tests (unit + e2e)
- Pydantic profile schema + loader + 2 real profiles

### External / dry-run (not calling real APIs yet)
- Real Telegram Bot API sends (dry-run logs payload instead)
- Real GHL contact/opportunity creation
- Real Gmail send
- Real Google Calendar events
- Real Postforme publishing
- Supabase persistence (in-memory only)

### Planned (Fase 1, weeks 1–8)
- LangGraph orchestrator with Redis checkpointing
- LLM-based Triage (Claude Haiku 4.5)
- Real tools: `telegram.py`, `gmail.py`, `calendar.py`, `ghl.py`, `postforme.py`, `meta_ads.py`, `google_ads.py`, `stripe.py`, `gbp.py`
- Marketing, CFO, CMO, CEO, Operations agents
- APScheduler weekly crons (CFO Mon 7h, CMO Mon 8h, CEO Mon 9h)
- Cost monitor + kill switch
- Supabase backend switch

### Planned (Fase 2+, weeks 9–24)
- Prospecting Agent (B2B outbound for DockPlus AI)
- Customer Success Agent
- Brand Guardian (transversal subagent)
- Competitive Intelligence Agent
- Evals automation
- Dual-run with human team (Bruna/Joana)
- Gradual release (25% → 50% → 75% → 100%)

---

## Dry-run pattern

All external-facing services branch on `settings.dry_run`:

- `TelegramService.send_approval_card()` — logs the payload to stdout instead of calling the Bot API.
- `DryRunActionExecutor.execute_sdr_approval()` — writes to `dry_run_actions` table and `audit_log`, but never calls Gmail, Calendar, or GHL.

**Rule:** when adding any new external action (send email, publish post, create calendar event, move pipeline stage), always provide a dry-run branch that records what *would* happen without calling the real API.

---

## Common mistakes to avoid

- **Forgetting `get_settings.cache_clear()` in tests** — If you monkeypatch env vars and don't clear the cache, tests will see stale settings.
- **Skipping idempotency** — Every webhook handler and cron entry must check `is_processed()` before acting and call `mark_processed()` after success.
- **Hardcoding business thresholds** — `thiago_approval_above_usd`, `min_ticket_usd`, and similar values live in the profile JSON. Never hardcode them in agent logic.
- **Sending raw data to Telegram** — Thiago reads on mobile. Use short summaries (`*bold*` for numbers), inline keyboards, and never send JSON dumps or email full bodies.
- **Modifying `audit_log` entries** — The table is append-only by design. If you need to "correct" something, write a new entry.
- **Forgetting `await` on store calls** — `InMemoryStore` methods are all `async`. Missing `await` silently returns a coroutine object instead of the value.
- **Adding a profile field without updating `_schema.py`** — The Pydantic model enforces the JSON shape. Update `_schema.py` first, then the JSON files.

---

## Non-obvious gotchas

1. **`InMemoryStore` is a global singleton.** Tests rely on `conftest.py` calling `store.reset()` and `get_settings.cache_clear()` before/after each test.

2. **Audit log is append-only in design.** The in-memory store implements a SHA-256 hash chain. The Supabase DDL in `scripts/seed_supabase.sql` has Postgres triggers that reject any UPDATE or DELETE on `audit_log`. Never attempt to modify audit log entries.

3. **GHL token types:** location token (per business) vs. agency token. Most endpoints require the location token. Using the agency token returns 403.

4. **`agent_runs.prompt_version` is mandatory.** Every agent run must record `settings.PROMPT_VERSION`. If null, LangSmith evals can't compare across versions.

5. **structlog processor order matters for LangSmith.** The current chain in `utils/logging.py` is the exact required order.

6. **Telegram output is mobile-first.** Keep approval cards under 5–6 lines of body before buttons. Use `*bold*` for key numbers. Button labels: max 3 words, verb-first. Never send raw JSON or walls of text.

7. **Function-first, not business-first.** Agents are organized by function (SDR, Marketing, CFO). Business context comes from the profile JSON. Never create per-business agent files.

8. **Adding a profile requires no code changes.** Drop a new `{business}.json` into `maestro/profiles/` following `_schema.py`.

---

## Commands cheat sheet

```bash
# Install
pip install -e ".[dev]"

# Dev server
uvicorn maestro.main:app --reload

# Tests
pytest
pytest --cov=maestro --cov-report=term-missing

# Docker dev
docker compose -f docker-compose.dev.yml up

# Health
curl http://localhost:8000/health
```

---

## Key constraints (from ADRs)

- **No n8n / Make / Zapier** — all integrations are Python tools.
- **No OpenClaw in Fase 1** — Telegram only.
- **No self-hosted LLM in Fase 1** — Anthropic/OpenAI API only.
- **No per-business agents** — function-first, profiles inject business context.
- **Always human approval before external action** — email, post, calendar event, pipeline move.
- **Total observability** — every agent run logged to LangSmith + `agent_runs` table, including `prompt_version`.
