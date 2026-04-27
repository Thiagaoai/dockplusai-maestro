# SDD — MAESTRO Telegram Cockpit

**Sistema:** MAESTRO v2.1 — Telegram Command & Control Layer  
**Documento irmão:** [PRD_TELEGRAM_COCKPIT.md](./PRD_TELEGRAM_COCKPIT.md)  
**Status:** Ready for implementation

---

## 1. Visão Técnica

O Telegram Cockpit adiciona uma camada de comando acima do LangGraph atual. Essa camada interpreta mensagens livres, comandos explícitos e callbacks, transforma tudo em uma intenção estruturada e despacha para admin actions, workflows de agents ou approval center.

Arquitetura alvo:

```text
Telegram Update
  -> webhook validation
  -> idempotency check
  -> CommandParser
  -> CommandRouter
      -> AdminController
      -> StatusController
      -> ApprovalController
      -> WorkflowController
          -> MaestroGraph / direct workflow
  -> TelegramResponseRenderer
  -> audit_log + processed_events
```

---

## 2. Princípios

1. **Telegram é interface, não regra de negócio.**  
   Webhook só valida, parseia e despacha.

2. **Toda intenção vira schema.**  
   Nada de if/else solto para cada frase nova.

3. **Registry antes de hardcode.**  
   Agents, subagents e workflows devem estar declarados em um registry central.

4. **Resposta curta primeiro, detalhes sob demanda.**  
   Telegram precisa ser operacional no celular.

5. **Cost guard antes de LLM/agent.**  
   Todo workflow passa pelo guard antes de gastar.

6. **HITL antes de ação externa.**  
   Approval center é obrigatório para qualquer ação pública/externa.

---

## 3. Novos Módulos

### 3.1 `maestro/telegram/schemas.py`

Modelos Pydantic:

```python
class IntentType(StrEnum):
    admin = "admin"
    status = "status"
    workflow = "workflow"
    approval = "approval"
    help = "help"
    unknown = "unknown"

class CommandIntent(BaseModel):
    intent_type: IntentType
    business: str | None = None
    agent: str | None = None
    subagent: str | None = None
    workflow: str | None = None
    action: str
    entities: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    missing_fields: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False
    raw_text: str
```

### 3.2 `maestro/telegram/registry.py`

Registry declarativo:

```python
AGENT_REGISTRY = {
    "sdr": {
        "aliases": ["sdr", "sales", "lead", "leads", "vendas"],
        "workflows": {
            "qualify_lead": {
                "aliases": ["qualifica lead", "qualify lead"],
                "required_fields": ["lead_text", "business"],
                "requires_hitl": True,
                "risk": "medium",
            },
            "follow_up": {...},
        },
        "subagents": ["lead_qualifier", "email_drafter", "meeting_scheduler"],
    },
}
```

Registry deve cobrir:

- `triage`
- `sdr`
- `prospecting`
- `marketing`
- `cfo`
- `cmo`
- `ceo`
- `operations`
- `brand_guardian`

### 3.3 `maestro/telegram/parser.py`

Responsável por:

- parse rápido determinístico para slash commands;
- parse por regex para comandos comuns;
- fallback LLM via `call_claude_json`;
- normalização de aliases;
- missing-field detection.

Pipeline:

```text
slash command?
  yes -> deterministic parse
known phrase/regex?
  yes -> deterministic parse
else -> LLM parser
validate against registry
return CommandIntent
```

### 3.4 `maestro/telegram/router.py`

Despacha `CommandIntent`:

```python
async def route_command(intent, context) -> TelegramReply:
    if intent.intent_type == "admin":
        return await AdminController(...).handle(intent)
    if intent.intent_type == "status":
        return await StatusController(...).handle(intent)
    if intent.intent_type == "approval":
        return await ApprovalController(...).handle(intent)
    if intent.intent_type == "workflow":
        return await WorkflowController(...).handle(intent)
    return help_reply(...)
```

### 3.5 `maestro/telegram/renderers.py`

Renderização mobile-first:

- `render_status`
- `render_agent_list`
- `render_costs`
- `render_pending_approvals`
- `render_agent_result`
- `render_error`
- `render_help`
- `render_clarification`

Todo renderer deve retornar:

```python
class TelegramReply(BaseModel):
    text: str
    buttons: list[list[InlineButton]] = []
    parse_mode: str = "Markdown"
    followup: bool = False
```

### 3.6 `maestro/telegram/controllers/`

Arquivos:

- `admin.py`
- `status.py`
- `approval.py`
- `workflow.py`

---

## 4. Estado e Persistência

### 4.1 Session state

Usar Redis quando disponível e fallback em memória no test/dev.

Chaves:

```text
telegram:session:{chat_id}
telegram:pending:{chat_id}
telegram:last_context:{chat_id}
agent_pause:{agent}
business_pause:{business}
```

Payload:

```json
{
  "last_business": "roberts",
  "last_agent": "marketing",
  "pending_intent": {},
  "missing_fields": ["topic"],
  "approval_editing": "approval-id",
  "updated_at": "..."
}
```

TTL:

- pending command: 15 min;
- last context: 24h;
- pause flags: no TTL.

### 4.2 Novas tabelas recomendadas

Se não quiser nova migration agora, pode começar com Redis/session + audit_log. Para produção completa:

```sql
CREATE TABLE agent_control_state (
  scope TEXT NOT NULL, -- global | business | agent
  key TEXT NOT NULL,
  paused BOOLEAN NOT NULL DEFAULT false,
  reason TEXT,
  updated_by TEXT,
  updated_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (scope, key)
);

CREATE TABLE telegram_command_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id BIGINT NOT NULL,
  update_id TEXT,
  raw_text TEXT,
  intent JSONB,
  result JSONB,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## 5. CommandIntent Taxonomia

### 5.1 Admin

Ações:

- `pause_all`
- `resume_all`
- `pause_agent`
- `resume_agent`
- `pause_business`
- `resume_business`

### 5.2 Status

Ações:

- `system_status`
- `agent_status`
- `cost_status`
- `pending_approvals`
- `recent_errors`
- `recent_runs`
- `scheduler_status`

### 5.3 Workflow

Ações:

- `run_agent`
- `run_subagent_capability`
- `create_marketing_post`
- `run_prospecting_batch`
- `run_web_prospecting`
- `run_cfo_briefing`
- `run_cmo_review`
- `run_ceo_briefing`
- `prepare_operations_task`
- `process_sdr_lead`

### 5.4 Approval

Ações:

- `list_pending`
- `approve`
- `reject`
- `edit`
- `details`

---

## 6. Fluxos Técnicos

### 6.1 `/status`

```text
Telegram /status
  -> CommandParser deterministic
  -> StatusController.system_status
  -> read settings, store, cost guard snapshot, pending approvals, recent errors
  -> render compact card
```

Resposta:

```text
MAESTRO status
Env: production | Dry-run: true
Agents: 8 active, 0 paused
Cost today: $0.04 / $15
Pending: 3 approvals
Errors 24h: 0
```

Botões:

- `Aprovações`
- `Custos`
- `Erros`
- `Agents`

### 6.2 Executar workflow

```text
Thiago: "faz post Roberts sobre spring cleanup"
  -> parser: workflow/create_marketing_post
  -> required fields ok
  -> cost guard
  -> WorkflowController
  -> trace_agent_run
  -> MarketingAgent.create_post
  -> persist run
  -> create approval
  -> render approval card
```

### 6.3 Missing fields

```text
Thiago: "faz post"
  -> parser identifies missing business/topic
  -> session pending intent
  -> ask clarification
```

Resposta:

```text
Qual negócio e tema?
```

Botões:

- `Roberts`
- `DockPlus`
- `Cancelar`

### 6.4 Agent paused

```text
Thiago: "roda CFO Roberts"
  -> router checks agent_pause:cfo
  -> if paused, no execution
```

Resposta:

```text
CFO está pausado.
```

Botões:

- `Retomar CFO`
- `Ver status`

---

## 7. Controle de Agents

### 7.1 Checks obrigatórios antes de execução

Todo workflow deve chamar:

1. global pause;
2. business pause;
3. agent pause;
4. cost guard;
5. idempotency;
6. registry validation;
7. required fields validation.

Ordem:

```python
await guard_global_not_paused()
await guard_business_not_paused(business)
await guard_agent_not_paused(agent)
await evaluate_cost_guard(...)
validate_workflow(intent)
```

### 7.2 Estados

```text
active
paused
blocked_by_cost
degraded
error
not_configured
```

---

## 8. Approval Center

### 8.1 Callback format

Atual:

```text
approval:approve:{approval_id}
approval:reject:{approval_id}
```

Novo formato recomendado:

```text
appr:v1:{action}:{approval_id}
```

Ações:

- `approve`
- `reject`
- `edit`
- `details`

Manter compatibilidade com formato antigo.

### 8.2 Edit approval

Fase inicial:

- `edit` abre modo texto;
- Thiago responde instrução;
- agent refaz preview;
- approval novo substitui ou versiona o anterior.

Schema recomendado:

```json
{
  "approval_id": "...",
  "edit_instruction": "mais curto e premium",
  "previous_preview": {},
  "new_preview": {}
}
```

---

## 9. Responsividade Telegram

### 9.1 SLA

- Auth/idempotency: <250ms.
- Slash/status commands: <3s.
- Agent accepted message: <5s.
- Final result: depende do agent, mas com progress message.

### 9.2 Progress messages

Para fluxos longos:

1. enviar ack;
2. executar agent;
3. editar mensagem ou enviar resultado.

Exemplo:

```text
Recebi. Rodando CMO Roberts agora.
```

### 9.3 Mensagens compactas

Limites:

- body principal: até 700 caracteres;
- approval card: até 6 linhas antes dos botões;
- detalhes longos: `Ver detalhes`;
- erro: até 4 linhas.

---

## 10. Observabilidade

Toda execução via Telegram deve registrar:

- `telegram_command_log`;
- `processed_events`;
- `agent_runs`;
- `audit_log`;
- LangSmith trace;
- `cost_usd`;
- `tokens_in`;
- `tokens_out`;
- `prompt_version`.

Tags LangSmith:

- `source=telegram`
- `business=...`
- `agent=...`
- `workflow=...`
- `prompt_version=...`

---

## 11. Testes

### Unit

- parser slash commands;
- parser natural language;
- registry validation;
- missing fields;
- pause guards;
- renderers;
- approval callback parser.

### E2E

Cada agent:

- Telegram message;
- correct route;
- agent run persisted;
- approval if needed;
- audit log;
- no external action without approval.

### Dataset de comandos

Criar `tests/fixtures/telegram_commands.jsonl` com 50-100 frases reais.

Campos:

```json
{
  "text": "faz post Roberts sobre spring cleanup",
  "expected": {
    "intent_type": "workflow",
    "business": "roberts",
    "agent": "marketing",
    "workflow": "create_marketing_post"
  }
}
```

Meta: 95%+ acerto.

---

## 12. Plano de Implementação Técnico

### Passo 1 — Estrutura

Criar:

```text
maestro/telegram/
  __init__.py
  schemas.py
  registry.py
  parser.py
  router.py
  renderers.py
  guards.py
  controllers/
    __init__.py
    admin.py
    status.py
    approval.py
    workflow.py
```

### Passo 2 — Migrar webhook

`maestro/webhooks/telegram.py` deve ficar fino:

```python
verify secret
verify chat
payload -> TelegramUpdate
return await TelegramCommandService.handle(payload)
```

### Passo 3 — Admin/status

Implementar primeiro:

- `/help`
- `/status`
- `/agents`
- `/costs`
- `/pending`
- `/errors`
- pause/resume global/agent/business.

### Passo 4 — Workflows

Implementar roteamento:

- marketing post;
- prospecting batch/web;
- CFO;
- CMO;
- CEO;
- Operations;
- SDR lead text.

### Passo 5 — Approval center

Implementar:

- list;
- details;
- approve;
- reject;
- edit.

### Passo 6 — Evals

Adicionar dataset e teste de acurácia.

---

## 13. Riscos e Mitigações

| Risco | Mitigação |
|---|---|
| Parser LLM entende errado | registry validation + confidence + clarification |
| Telegram vira parede de texto | renderers com limites rígidos |
| Agent pausado ainda executa por scheduler | pause guard central usado por todos entrypoints |
| Callback duplicado | processed_events por callback id |
| Custo sobe por comandos repetidos | cost guard antes de agent + idempotency |
| Subagent exposto demais confunde | expor capacidades, não nomes internos |
| Thiago pede algo fora do escopo | resposta clara + menu de opções suportadas |

---

## 14. Definition of Done

O Telegram Cockpit está pronto quando:

- Thiago opera todos os agents principais por Telegram.
- Todos os agents têm pelo menos um workflow E2E.
- `/status`, `/agents`, `/costs`, `/pending`, `/errors` funcionam.
- Pause/resume global, por agent e por negócio funcionam.
- Approval center lista, detalha, aprova, rejeita e edita.
- 50 comandos reais passam com 95%+ routing accuracy.
- Nenhuma ação externa ocorre sem aprovação.
- Todos os runs têm trace, custo, tokens e audit log.
- Soak de 7 dias passa sem precisar abrir código para operação normal.
