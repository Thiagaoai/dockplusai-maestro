# TASK.md — MAESTRO v2.0 Plano de Ação Detalhado

**Owner:** Thiago do Carmo — DockPlus AI  
**Dev principal:** Gustavo (20h/semana)  
**Revisão:** Thiago (6h/semana)  
**Referência:** [SDD.md](./SDD.md) | [PRD.md](./PRD.md) | [CLAUDE.md](./CLAUDE.md)

> Legenda: **[G]** = Gustavo implementa | **[T]** = Thiago entrega dado/aprova | **[GT]** = ambos juntos

---

## STATUS ATUAL — implementado no scaffold local

> Estado: backend/agents funcionando em modo **dry-run**, sem site/UI. Ações externas reais já têm Resend para email, GHL direto e camada Composio para Calendar/HighLevel quando conectado.

- [x] FastAPI app com `/health`
- [x] Webhook Telegram com validação de secret + whitelist `chat_id`
- [x] Webhook GHL com HMAC por business
- [x] `/stop` e `/start`
- [x] Idempotência local para webhooks/callbacks
- [x] `audit_log`, `agent_runs`, approvals, leads e business metrics em store local
- [x] Profiles `roberts.json` e `dockplusai.json`
- [x] SDR Agent + subagents: `lead_qualifier`, `email_drafter`, `meeting_scheduler`
- [x] Marketing Agent + subagents: `content_creator`, `caption_writer`, `hashtag_strategist`, `posting_scheduler`
- [x] CFO Agent + subagents: `invoice_reconciler`, `margin_analyst`, `cashflow_forecaster`
- [x] CMO Agent + subagents: `ad_performance_analyst`, `budget_allocator`, `creative_tester`
- [x] CEO Agent + subagents: `weekly_briefing`, `decision_preparer`
- [x] Operations Agent + subagents: `calendar_manager`, `follow_up_sender`, `ghl_pipeline_mover`
- [x] Brand Guardian subagent base
- [x] Telegram normal message → Triage → agent correto
- [x] Approval callback genérico para SDR, Marketing, CMO e Operations
- [x] Weekly scheduler chama CFO/CMO/CEO em dry-run
- [x] Testes E2E cobrindo vertical slice + agents Fase 1
- [x] Test suite atual: `16 passed`

### Próximo bloco real

- [x] Implementar `Store` real com Supabase mantendo `InMemoryStore` para testes
- [x] Persistir `processed_events`, `audit_log`, `agent_runs`, `approval_requests`, `leads`, `business_metrics`
- [x] Escolher backend via `.env`: `STORAGE_BACKEND=memory|supabase`
- [x] Testes mockados para `SupabaseStore`
- [x] Script para aplicar schema no Supabase por `SUPABASE_DB_URL`
- [x] Rodar `scripts/seed_supabase.sql` no projeto Supabase real
- [x] Projeto Supabase `maestro` criado/conectado via Composio: `nithporoqakujydqfpsa`
- [x] Tabelas verificadas no Supabase: 10 tabelas core criadas
- [x] Triggers append-only do `audit_log` verificados: `no_update_audit`, `no_delete_audit`
- [x] Preencher `.env` com `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `STORAGE_BACKEND=supabase`
- [x] Smoke test local usando Supabase real: Telegram → CFO → `agent_runs` + `business_metrics` + `processed_events`
- [x] Composio CLI autenticado no workspace `dockplusai_workspace`
- [x] Cliente Composio adicionado ao backend para executar tools via CLI
- [x] Executor SDR preparado para `DRY_RUN=false`: Resend email + Calendar event + HighLevel pipeline lookup após aprovação humana
- [x] Resend definido como canal primário de email SDR; Gmail não é obrigatório para envio
- [x] Gmail conectado no Composio e validado com leitura mínima (`GMAIL_FETCH_EMAILS`)
- [x] Google Calendar conectado no Composio e validado com listagem read-only (`GOOGLECALENDAR_LIST_CALENDARS`)
- [x] GHL direto via API adicionado como fallback/primary para pipeline quando Composio não enxerga HighLevel
- [x] GHL DockPlus AI validado direto na API: pipeline lookup OK
- [x] Composio HighLevel verificado: sem active connection no CLI/workspace atual
- [x] Roberts `do_not_contact` hard block criado: Kim Williams nunca entra em prospecting/follow-up/SDR
- [x] Importador CSV de clientes/prospects Roberts criado com dedupe e bloqueio `do_not_contact`
- [x] Supabase `prospect_queue` criado para intercalar fontes `customer_file` e `scrape`
- [x] Lista `Clients (1).csv` importada para Roberts: 1.130 válidos no arquivo, 1 Kim Williams excluída
- [x] Lista `Customers.xls` importada para Roberts: 1.484 válidos no arquivo
- [x] Base Roberts consolidada no Supabase: 2.574 leads/prospects importados e 2.574 itens queued
- [x] Prospecting batch Roberts criado: 10 pessoas por lote, approval Telegram, HTML email via Resend
- [x] Scheduler Roberts prospecting configurado: 08:00, 11:00, 15:00, 17:00 America/New_York
- [x] Intercalação configurada: 2 `customer_file` para 1 `scrape` quando houver scrape queued
- [x] Comando Telegram manual criado: `prospect roberts 10`
- [x] Fluxos nomeados: `roberts 10` usa lista própria; `roberts web` usa fila de scrape/web
- [x] Promo Roberts configurada: 10% off para novos clientes, CTA para `https://robertslandscapecod.com`
- [ ] GHL Roberts token válido direto na API
- [ ] Prospectar clientes existentes nos pipelines Roberts ou CSV, excluindo `do_not_contact`
- [x] Autorizar Google Calendar no Composio
- [ ] Autorizar HighLevel/GHL no Composio
- [ ] Conectar Telegram dev bot real (`@maestro_dev_bot`)
- [ ] Conectar GHL sandbox real
- [ ] Validar fluxo real SDR aprovado: email enviado + calendar criado + GHL consultado, ainda com HITL
- [ ] Adicionar LangSmith traces reais por agent
- [ ] Adicionar LLM real nos subagents onde fizer diferença, preservando fallback determinístico

---

## SEMANA 0 — Pré-requisitos absolutos (antes de escrever 1 linha de código)

> Critério de saída: todos os itens abaixo com ✅. Projeto NÃO inicia sem isso.

### Infraestrutura
- [ ] **[T]** VPS Hostinger ≥4GB RAM / ≥40GB disk / Ubuntu 22+ provisionado
- [ ] **[G]** Docker + docker-compose instalados e testados no VPS
- [ ] **[T]** DNS `maestro.dockplus.app` apontando pro IP do VPS
- [ ] **[G]** Traefik configurado com Let's Encrypt — HTTPS funcionando em `https://maestro.dockplus.app/health`
- [ ] **[GT]** SSH access configurado para Thiago + Gustavo
- [ ] **[G]** Backup automático VPS agendado (cron diário, output pra Hostinger Object Storage)

### APIs — smoke test (1 dia dedicado, ambos)
- [ ] **[T]** Anthropic API: chave funciona, Tier 4 confirmado (`curl` com Sonnet 4.6)
- [ ] **[T]** OpenAI API: chave funciona (fallback)
- [ ] **[G]** LangSmith: projeto `maestro-prod` criado, primeiro trace de teste enviado
- [ ] **[T]** GHL Roberts: location token + webhook secret. Testar: criar contato fake, receber 1 evento webhook
- [ ] **[T]** GHL DockPlus AI: idem
- [ ] **[G]** Resend: domínio/from validado, testar envio real para conta controlada
- [x] **[G]** Gmail OAuth2: conectado no Composio para leitura/histórico/reply-in-thread; não bloqueia SDR send
- [x] **[G]** Google Calendar: conexão/listagem validada no Composio
- [ ] **[G]** Google Calendar: testar `find free slots` + `create event`
- [ ] **[T]** Postforme: API key válida + 1 post teste publicado (pode deletar depois)
- [ ] **[T]** Meta Marketing API: developer token + testar `GET /insights` em 1 campanha Roberts
- [ ] **[T]** Google Ads API: developer token solicitado — **fazer isso AGORA, pode levar semanas**
- [ ] **[T]** Stripe: chave test funciona, testar `list charges`
- [ ] **[G]** Tavily: 1 query de teste
- [ ] **[G]** Perplexity: 1 query de teste
- [ ] **[G]** Replicate: gerar 1 imagem teste com FLUX
- [ ] **[G]** Telegram bot: criar `@maestro_dockplus_bot`, webhook configurado, `secret_token` validado
- [ ] **[G]** Telegram bot sandbox: criar `@maestro_dev_bot` separado para testes
- [ ] **[G]** Supabase: projeto criado, rodar `scripts/seed_supabase.sql`, confirmar RLS ativa

### Dados reais (Thiago entrega)
- [ ] **[T]** `maestro/profiles/roberts.json` preenchido com dados reais:
  - Últimos 20 jobs: ticket, serviço, fonte do lead, converteu ou não
  - 5+ emails reais que converteram (copiar do Gmail)
  - Tom de voz em prosa (ex: "Professional, warm, locally-rooted Cape Cod craftsman")
  - Lista de palavras proibidas e aprovadas
  - Service area completa (cidades)
- [ ] **[T]** `maestro/profiles/dockplusai.json` preenchido:
  - ICP validado (indústrias, tamanho empresa, revenue range)
  - 5+ emails B2B que converteram
  - Critérios de qualificação validados com Joana
- [ ] **[T]** `decision_thresholds` calibrado por Thiago (default: `thiago_approval_above_usd: 500`)
- [ ] **[T]** Métricas baseline coletadas (preencher antes de começar):
  - Tempo médio atual de resposta a lead (pedir pra Bruna)
  - Taxa de conversão atual Roberts (últimos 90 dias)
  - Média posts IG/semana (últimas 8 semanas)
  - Receita últimos 90 dias

### Repositório e CI/CD
- [ ] **[G]** Repo GitHub criado (`dockplusai/maestro`, privado)
- [ ] **[G]** `.env.example` criado com todas as vars do SDD §11.1
- [ ] **[G]** `.gitignore` incluindo `.env`, `*.pyc`, `__pycache__`
- [ ] **[G]** Branch strategy: `main` (prod), `dev` (staging), feature branches
- [ ] **[G]** GitHub Actions: CI (lint + tests) em todo PR
- [ ] **[G]** GitHub Actions: deploy automático em push para `main` via SSH
- [ ] **[G]** GitHub Secrets configurados com todas as vars de prod

---

## SEMANA 1 — Base do sistema

> Critério de saída: `https://maestro.dockplus.app/health` retorna 200. `/stop` funciona via Telegram.

### Setup base Python
- [ ] **[G]** `pyproject.toml` com todas as dependências (uv)
- [ ] **[G]** `maestro/config.py` — Pydantic Settings lendo todas as vars do `.env`
- [ ] **[G]** `maestro/utils/logging.py` — structlog configurado com JSON output (ver CLAUDE.md para processor chain exata)
- [ ] **[G]** `maestro/utils/security.py` — HMAC validation, chat_id whitelist
- [ ] **[G]** `maestro/utils/pii.py` — funções `mask(phone)`, `mask(email)`, `mask(name)` para logs
- [ ] **[G]** `maestro/utils/idempotency.py` — `is_processed()` e `mark_processed()` via Supabase `processed_events`

### FastAPI scaffold
- [ ] **[G]** `maestro/main.py` — app FastAPI com Traefik headers
- [ ] **[G]** `GET /health` — retorna `{status: ok, env: prod, version: ...}`
- [ ] **[G]** Middleware: rate limit (slowapi, 10 req/min global), request logging
- [ ] **[G]** `maestro/webhooks/telegram.py` — router com validação `X-Telegram-Bot-Api-Secret-Token` + chat_id whitelist
- [ ] **[G]** `maestro/webhooks/ghl.py` — router com HMAC SHA-256 por business

### LangGraph scaffold
- [ ] **[G]** `maestro/graph.py` — StateGraph base com nó `triage` stub (retorna "OK")
- [ ] **[G]** Redis checkpointer wired: `RedisSaver.from_conn_string()` compilado com `interrupt_before=["hitl"]`
- [ ] **[G]** `maestro/memory/redis_session.py` — get/set/delete session, helper `is_stopped()`
- [ ] **[G]** `maestro/memory/supabase_long.py` — wrapper CRUD para tabelas principais

### Kill switch `/stop`
- [ ] **[G]** Handler Telegram para `/stop`: seta `maestro:stopped=1` no Redis, confirma ao Thiago em português
- [ ] **[G]** Handler Telegram para `/start`: deleta key Redis, confirma retomada
- [ ] **[G]** Decorator `@check_stopped` ou guard no início de cada agent execution
- [ ] **[G]** Audit log: todo `/stop` e `/start` registrado em `audit_log`
- [ ] **[T]** Testar: mandar `/stop`, confirmar que próxima mensagem não dispara LLM. Mandar `/start`, confirmar retomada.

### Docker
- [ ] **[G]** `Dockerfile` (Python 3.11 slim, uv, non-root user)
- [ ] **[G]** `docker-compose.yml` — serviços: `maestro`, `redis`, `traefik`
- [ ] **[G]** `docker-compose.dev.yml` — idem com hot reload e portas expostas
- [ ] **[G]** Auto-restart: `restart: unless-stopped` em todos os serviços

---

## SEMANA 2 — SDR Agent (parte 1: tools + subagents)

> Critério de saída parcial: lead qualificado retorna score + email draftado + 3 slots de reunião (em teste unitário, sem webhook).

### Tools (todas com retry + idempotência + structlog)
- [ ] **[G]** `maestro/tools/telegram.py`:
  - `send_message(chat_id, text)` — formata markdown pra Telegram
  - `send_inline_keyboard(chat_id, text, buttons)` — botões em grade 2x2 max
  - `edit_message(chat_id, message_id, new_text)`
- [ ] **[G]** `maestro/tools/ghl.py`:
  - `create_contact(name, phone, email, business, idempotency_key)`
  - `update_contact(ghl_id, fields)`
  - `move_stage(opportunity_id, stage_name, business)`
  - `create_opportunity(contact_id, business, pipeline_id)`
  - `get_contact(ghl_id)` — para enriquecer lead já existente
- [ ] **[G]** `maestro/tools/gmail.py`:
  - `send_email(to, subject, body, from_alias, idempotency_key)`
  - `get_thread(thread_id)` — para follow-up em thread existente
- [ ] **[G]** `maestro/tools/calendar.py`:
  - `find_free_slots(duration_min, days_ahead, preferred_times)` — retorna lista de 3 slots ranqueados
  - `create_event(title, start, end, attendee_email, description)`
- [ ] **[G]** `maestro/tools/supabase_db.py`:
  - CRUD helpers para `leads`, `agent_runs`, `audit_log`, `processed_events`, `business_metrics`

### Subagents SDR
- [ ] **[G]** `maestro/subagents/sdr/lead_qualifier.py`:
  - Input: lead data + profile.qualification_criteria
  - Valida service area (geocode simples por cidade por ora, Maps API na Fase 2)
  - Output: `{score: 0-100, justification: str, recommended_action: str}`
  - Modelo: Claude Sonnet 4.6
  - Teste unitário com 5 leads Roberts reais (dados de Thiago)
- [ ] **[G]** `maestro/subagents/sdr/email_drafter.py`:
  - Input: lead + score + `profile.tone` + `profile.tone.sample_emails`
  - Output: `{subject: str, body: str, send_after: datetime}`
  - Idioma: sempre inglês (lead é cliente externo)
  - Modelo: Claude Sonnet 4.6
  - Teste: gera email pra lead fictício Roberts, Thiago aprova tom
- [ ] **[G]** `maestro/subagents/sdr/meeting_scheduler.py`:
  - Chama `calendar.find_free_slots`
  - Ranqueia: manhã > tarde, Terça/Quinta > Segunda/Sexta
  - Output: 3 slots formatados para o Telegram

### Testes unitários SDR
- [ ] **[G]** `tests/unit/test_lead_qualifier.py` — 5 casos: qualificado, fora de área, ticket baixo, info insuficiente, urgente
- [ ] **[G]** `tests/unit/test_email_drafter.py` — tom correto, sem hard-sell, assinatura correta
- [ ] **[G]** `tests/unit/test_meeting_scheduler.py` — 3 slots retornados, formato correto
- [ ] **[G]** Cobertura ≥70% nos 3 arquivos
- [ ] **[T]** Review dos emails gerados — confirmar tom Roberts

---

## SEMANA 3 — SDR Agent (parte 2: orchestration + HITL + webhook)

> Critério de saída: lead fake entra no GHL → em <30s Thiago recebe Telegram com email draftado → aprova com 1 toque → email vai + calendar criado + GHL movido.

### SDR Agent principal
- [ ] **[G]** `maestro/agents/sdr.py` — LangGraph subgraph:
  - Nó `qualify_lead` → invoca `lead_qualifier`
  - Nó `draft_email` → invoca `email_drafter`
  - Nó `find_slots` → invoca `meeting_scheduler` (roda em paralelo com `draft_email`)
  - Nó `hitl_review` — `interrupt()`, formata mensagem Telegram mobile-first, envia inline keyboard
  - Nó `execute_approved` — gmail.send_email + calendar.create_event + ghl.move_stage
  - Nó `handle_rejection` — registra motivo, move GHL para stage "disqualified"
- [ ] **[G]** Inline keyboard buttons: "✅ Aprovar tudo" | "✏️ Editar email" | "📅 Editar horários" | "❌ Rejeitar"
- [ ] **[G]** Auto-reply neutro: se Thiago não responder em 8h, enviar template neutro e marcar como "auto_replied" no GHL
- [ ] **[G]** Toda ação registrada: `agent_runs` + `audit_log` + LangSmith trace com `prompt_version`

### Webhook GHL
- [ ] **[G]** `maestro/webhooks/ghl.py` — handler completo:
  - Valida HMAC SHA-256
  - Extrai `event_id`, checa `processed_events` (idempotência)
  - Infere `business` do `locationId` GHL
  - Checa Redis `maestro:stopped` — se parado, enfileira evento, retorna 200
  - Dispatcha pro SDR Agent assíncrono
- [ ] **[G]** Triage para webhook GHL: skip Triage, vai direto pro SDR
- [ ] **[G]** Logging: todo webhook logado com `event_id`, `business`, `lead_name_redacted`

### Triage Agent
- [ ] **[G]** `maestro/agents/triage.py`:
  - Modelo: Claude Haiku 4.5 (custo baixo, alta velocidade)
  - Input: mensagem Thiago + histórico recente da sessão
  - Output: `{business, function, intent, confidence, target_agent}`
  - Se `confidence < 0.7`: pede esclarecimento em português
  - Cache de 5min para mesma sessão no Redis
  - Latência target P90 <500ms
- [ ] **[G]** Roteamento condicional no `graph.py` — Triage → SDR | Marketing | CFO | CMO | CEO | Operations

### Testes integração SDR
- [ ] **[G]** `tests/integration/test_sdr_pipeline.py` — end-to-end com sandbox:
  - Webhook fake GHL → Telegram sandbox recebe mensagem
  - Simula aprovação via bot API → email enviado (Resend sandbox) + calendar criado + GHL movido
- [ ] **[T]** Teste manual com lead real Roberts: Thiago aprova fluxo completo, confirma email e calendar corretos

---

## SEMANA 4 — Marketing Agent

> Critério de saída: Thiago manda "post sobre patio granito Falmouth" → 90s depois preview Telegram → aprova → publica IG Roberts.

### Tools Marketing
- [ ] **[G]** `maestro/tools/replicate.py`:
  - `generate_image(prompt, style, aspect_ratio)` → retorna URL da imagem
  - Prompt enrichment automático baseado em `profile.marketing.visual_style`
  - Timeout 60s (Replicate pode ser lento)
- [ ] **[G]** `maestro/tools/postforme.py`:
  - `schedule_post(account_id, caption, image_urls, scheduled_at)` → retorna `post_id`
  - `publish_now(account_id, caption, image_urls)` — para aprovação imediata
  - `get_analytics(account_id, days)` — para histórico de horários de melhor engagement

### Subagents Marketing
- [ ] **[G]** `maestro/subagents/marketing/content_creator.py`:
  - Input: tema, profile, estilo visual
  - Gera 1-4 prompts de imagem otimizados para FLUX
  - Chama `replicate.generate_image` para cada prompt
  - Output: lista de URLs de imagens
- [ ] **[G]** `maestro/subagents/marketing/caption_writer.py`:
  - Input: tema + imagens geradas + profile.tone
  - Output: caption 200-2200 chars, com CTA, tom correto
  - Idioma: inglês (post público)
  - Modelo: Claude Sonnet 4.6
- [ ] **[G]** `maestro/subagents/marketing/hashtag_strategist.py`:
  - Output: 8-12 hashtags = 4 locais + 4 nicho + 2-4 gerais
  - Fonte: histórico de posts + Tavily trends (query simples)
- [ ] **[G]** `maestro/subagents/marketing/posting_scheduler.py`:
  - Lê `business_metrics` ou usa defaults do profile
  - Default Roberts: Ter/Qui 18h-19h ET
  - Default DockPlus: Seg/Qua 9h-10h ET
  - Output: `scheduled_at` em ISO 8601

### Marketing Agent principal
- [ ] **[G]** `maestro/agents/marketing.py` — LangGraph subgraph:
  - Nó `generate_content` — roda `content_creator` + `caption_writer` + `hashtag_strategist` em paralelo
  - Nó `hitl_preview` — envia preview Telegram: imagem(ns) + caption + hashtags + horário sugerido
  - Inline keyboard: "📤 Publicar agora" | "📅 Agendar" | "✏️ Refazer caption" | "🖼️ Refazer imagens" | "❌ Cancelar"
  - Nó `publish` — chama `postforme.schedule_post` ou `postforme.publish_now`
  - Confirmação Telegram: "✅ Post agendado para Roberts IG — Ter 18h"

### Calendário editorial automático
- [ ] **[G]** `maestro/schedulers/daily.py` — cron diário 6h UTC:
  - Para cada profile ativo com `marketing.posting_frequency_per_week > 0`
  - Gera 1 post draft e enfileira para revisão Thiago
  - Não publica automaticamente — sempre HITL
- [ ] **[T]** Confirmar: calendário editorial rodando, Thiago recebe sugestão diária, aprova ou descarta

### Testes
- [ ] **[G]** `tests/unit/test_caption_writer.py` — tom correto por profile, sem hard-sell
- [ ] **[G]** `tests/unit/test_hashtag_strategist.py` — estrutura correta, sem repetição
- [ ] **[T]** Review manual: 3 posts completos gerados, Thiago aprova estilo visual e tom

---

## SEMANA 5 — CFO + CMO Agents

> Critério de saída: segunda-feira teste manual, 2 relatórios JSON gerados em `business_metrics` com dados reais.

### Tools Finance/Ads
- [ ] **[G]** `maestro/tools/stripe.py`:
  - `list_charges(business, days)` — read-only
  - `summarize_revenue(business, period)` — agrupa por período
- [ ] **[G]** `maestro/tools/meta_ads.py`:
  - `get_campaign_insights(ad_account_id, days)` — ROAS, CPC, CPM, CTR
  - `get_creative_performance(ad_account_id, days)` — performance por criativo
- [ ] **[G]** `maestro/tools/google_ads.py` *(se token aprovado; mockar se ainda não)*:
  - `get_campaign_metrics(customer_id, days)`
- [ ] **[G]** `maestro/tools/gbp.py`:
  - `get_reviews(location_id, days)` — últimas reviews Google
  - `get_metrics(location_id)` — views, calls, direction requests

### Subagents CFO
- [ ] **[G]** `maestro/subagents/cfo/invoice_reconciler.py`:
  - Bate Stripe charges vs GHL opportunities `won`
  - Output: lista de discrepâncias + total reconciliado
- [ ] **[G]** `maestro/subagents/cfo/margin_analyst.py`:
  - Input: período (semana/mês)
  - Cálculo: receita total - custos diretos estimados por `profile.offerings`
  - Output: margem bruta % + comparação período anterior
- [ ] **[G]** `maestro/subagents/cfo/cashflow_forecaster.py`:
  - Input: oportunidades GHL confirmadas + despesas fixas do profile
  - Output: projeção 3 cenários (pessimista/realista/otimista) pra 30/60/90 dias

### CFO Agent
- [ ] **[G]** `maestro/agents/cfo.py`:
  - Trigger: cron segunda 7h UTC + ask explícito via Triage
  - Roda 3 subagents em paralelo
  - Salva output em `business_metrics` com `metric_type='cfo_weekly'`
  - Responde perguntas ad-hoc em <10s (US-4 do PRD)
- [ ] **[T]** Teste: perguntar "qual minha margem do mês passado?" → receber resposta em <10s com número real

### Subagents CMO
- [ ] **[G]** `maestro/subagents/cmo/ad_performance_analyst.py`:
  - Consolida Meta + Google Ads + GBP
  - Detecta fadiga de criativo: CTR caiu >20% em 14 dias = alerta
  - Output: tabela performance por campanha
- [ ] **[G]** `maestro/subagents/cmo/budget_allocator.py`:
  - Recomenda redistribuição de budget
  - **Toda mudança >$500 → obrigatoriamente para em HITL com inline keyboard**
  - Output: tabela "campanha → action"
- [ ] **[G]** `maestro/subagents/cmo/creative_tester.py`:
  - Output: 3-5 hipóteses de novos criativos baseadas em top performers

### CMO Agent
- [ ] **[G]** `maestro/agents/cmo.py`:
  - Trigger: cron segunda 8h UTC + ask explícito
  - Salva em `business_metrics` com `metric_type='cmo_weekly'`
  - Alertas de fadiga enviados imediatamente via Telegram, não esperam segunda

### Scheduler weekly
- [ ] **[G]** `maestro/schedulers/weekly.py`:
  - APScheduler com Redis lock distribuído (ver CLAUDE.md — sem lock, pode disparar 2x)
  - Segunda 7h UTC: CFO
  - Segunda 8h UTC: CMO
  - Segunda 9h UTC: CEO (implementado na semana seguinte)

---

## SEMANA 6 — CEO + Operations Agents

> Critério de saída: segunda 9h Thiago recebe briefing executivo completo com inline keyboards de decisão funcionando.

### Subagents CEO
- [ ] **[G]** `maestro/subagents/ceo/weekly_briefing.py`:
  - Input: outputs CFO + CMO da semana + leads processados + posts publicados
  - Modelo: **Claude Opus 4.7** (raciocínio profundo — só aqui justifica o custo)
  - Output markdown estruturado (ver PRD US-3 para estrutura exata):
    - Resumo executivo (3 bullets)
    - Receita semana vs anterior
    - Pipeline (leads, qualified, won, value)
    - Marketing performance
    - 3 wins da semana
    - 3 alertas/preocupações
  - Idioma: português (para Thiago)
- [ ] **[G]** `maestro/subagents/ceo/decision_preparer.py`:
  - Identifica 3-5 decisões pendentes a partir dos dados
  - Cada decisão: contexto + 2-3 opções + recomendação
  - Output: lista de decisões com inline keyboards

### CEO Agent
- [ ] **[G]** `maestro/agents/ceo.py`:
  - Trigger: cron segunda 9h UTC
  - Envia briefing via Telegram (split em máx 2 mensagens para respeitar limite 4096 chars)
  - Inline keyboards por decisão: "✅ Aprovar" | "❌ Rejeitar" | "📅 Adiar 1 semana" | "💬 Discutir"
  - Respostas aos botões disparam ações concretas ou abrem thread de discussão

### Operations Agent + subagents
- [ ] **[G]** `maestro/subagents/operations/calendar_manager.py`:
  - Gerencia agenda via Telegram: "agendar reunião com João quinta 14h"
  - Tools: `calendar.find_free_slots`, `calendar.create_event`, `calendar.update_event`
- [ ] **[G]** `maestro/subagents/operations/follow_up_sender.py`:
  - Detecta oportunidades GHL sem touch >7 dias
  - Drafta follow-up email, apresenta para Thiago aprovar
- [ ] **[G]** `maestro/subagents/operations/ghl_pipeline_mover.py`:
  - Move stages baseado em ações confirmadas
  - Determinístico — sem LLM neste subagent
- [ ] **[G]** `maestro/agents/operations.py` — LangGraph subgraph roteando entre os 3 subagents

### Integração Triage → todos os agents
- [ ] **[G]** `maestro/graph.py` — grafo principal completo com roteamento para todos os 7 agents
- [ ] **[G]** Profiles schema validado: `maestro/profiles/_schema.py` Pydantic model carregado no Triage
- [ ] **[T]** Teste de roteamento: 10 frases diferentes em português → Triage roteia corretamente

---

## SEMANA 7-8 — Hardening, testes E2E e soak test

> Critério de saída FASE 1: 7 dias consecutivos sem intervenção manual, métricas O1-O7 do PRD batendo, custo <$200/mês.

### Testes E2E
- [ ] **[G]** `tests/e2e/test_sdr_full.py` — webhook GHL fake → email enviado + calendar + GHL movido (sandbox completo)
- [ ] **[G]** `tests/e2e/test_marketing_full.py` — Telegram message → post gerado → aprovado → publicado
- [ ] **[G]** `tests/e2e/test_weekly_cron.py` — trigger manual cron → 3 outputs em `business_metrics`
- [ ] **[GT]** Teste de carga: 50 mensagens/min por 30min — verificar P90 latência + taxa de erro

### Testes de recuperação (simular falhas)
- [ ] **[G]** Redis down: sessões resetam, Supabase mantém histórico, zero data loss
- [ ] **[G]** Supabase down: mensagens entram em SQLite fallback local, flush quando voltar
- [ ] **[G]** Anthropic 429 sustained: fallback OpenAI ativa, Thiago recebe alerta
- [ ] **[G]** Container crash: restart automático <30s (Docker `restart: unless-stopped`)
- [ ] **[G]** Webhook signature inválida: retorna 403, loga, alerta se >5 em 5min

### Cost monitor
- [ ] **[G]** `scripts/cost_monitor.py`:
  - Lê `agent_runs.cost_usd` do dia
  - Se >$15: Telegram INFO pra Thiago
  - Se >$30: pausa crons (APScheduler pause), mantém webhooks ativos, Telegram CRÍTICO
  - Roda a cada hora via APScheduler
- [ ] **[G]** `daily_costs` table atualizada a cada agent run
- [ ] **[T]** Verificar: simular custo alto artificialmente, confirmar kill switch funciona

### Observabilidade
- [ ] **[G]** LangSmith: tags em todos os traces (`business=`, `agent=`, `prompt_version=`)
- [ ] **[G]** `scripts/dashboard.py` — CLI simples: latência P50/P90, taxa erro, custo dia, leads processados
- [ ] **[G]** Alertas Telegram: todos os eventos críticos do SDD §13.5 implementados

### Soak test (7 dias)
- [ ] **[GT]** Dias 1-3: leads reais Roberts entram, Thiago aprova via Telegram, observar comportamento
- [ ] **[GT]** Dias 4-7: crons rodando, briefing segunda, posts diários propostos
- [ ] **[T]** Self-report: "economizei X horas esta semana?" — baseline vs MAESTRO
- [ ] **[GT]** Retrospectiva Fase 1: o que funcionou, o que foi ajustado, backlog para Fase 2

### Documentação final Fase 1
- [ ] **[G]** `docs/RUNBOOK.md` — procedimentos de incidente (restart, rollback, debug)
- [ ] **[G]** `README.md` — setup instructions atualizadas
- [ ] **[G]** `CLAUDE.md` — atualizar seção de comandos com comandos verificados e funcionando
- [ ] **[G]** Seção "Pitfalls log" no CLAUDE.md — preencher com o que deu errado durante Fase 1

---

## FASE 2 — Tarefas (semanas 9-16)

> Detalhamento completo será feito ao final da Fase 1. Abaixo o roadmap de alto nível.

- [ ] **[T]** Comprar domínio `try-dockplusai.com`
- [ ] **[T]** SPF/DKIM/DMARC configurados — **iniciar warmup nas semanas 9-10, leva 4-6 semanas**
- [ ] **[G]** 3-5 mailboxes Google Workspace criadas para rotação
- [ ] **[G]** `maestro/tools/_enrichment/apollo.py` — integração Apollo MCP (já temos acesso)
- [ ] **[G]** `maestro/tools/_enrichment/hunter.py` — verificação de emails
- [ ] **[G]** `maestro/tools/_enrichment/maps.py` — Google Maps Places API
- [x] **[G]** CSV customer/prospect import como fonte imediata para Roberts, sem depender de token GHL
- [x] **[G]** `prospect_queue` com `source_type=customer_file|scrape` para alternar fontes
- [x] **[G]** Batch scheduler 4x/dia para campanha Roberts com aprovação humana antes de envio
- [ ] **[G]** Prospecting Agent híbrido: CSV/customers + GHL pipeline + online scraping/enrichment, sempre com HITL
- [ ] **[G]** Prospecting Agent + 7 subagents (icp_definer, list_builder, enricher, personalizer, cadence_orchestrator, reply_classifier, deliverability_monitor)
- [ ] **[G]** Customer Success Agent + 4 subagents
- [ ] **[G]** Brand Guardian subagent transversal
- [ ] **[T]** Profiles `all_granite.json` e `cape_codder.json` preenchidos

---

## FASE 3 — Tarefas (semanas 17-24)

> Detalhamento feito ao final da Fase 2.

- [ ] **[T]** Profiles `cheesebread.json`, `bread_and_roses.json`, `flamma_verbi.json`
- [ ] **[G]** Competitive Intelligence Agent
- [ ] **[G]** Sistema de evals semanais automatizados (LangSmith)
- [ ] **[G]** Feedback 👍/👎 inline em todo output do agente
- [ ] **[G]** Versionamento automático de prompts (leitura de `prompts/v{N}/`)
- [ ] **[GT]** Dual-run 30 dias com Bruna (Roberts) e Joana (DockPlus AI)
- [ ] **[GT]** Release gradual: 25% → 50% → 75% → 100% autônomo

---

## Tracking de métricas (medir semanalmente a partir da Semana 7)

| Métrica | Baseline (pré-MAESTRO) | Target Fase 1 | Atual |
|---|---|---|---|
| Tempo médio resposta lead | ____h | <10min | ___ |
| Posts IG/semana Roberts | ____ | 5-7 | ___ |
| Briefing CFO entregue | 0% | 100% | ___ |
| Horas Thiago/semana em ops | ____h | -15 a -20h | ___ |
| Custo mensal APIs | $0 | <$200 | ___ |
| Aprovação Thiago | — | >90% | ___ |
| Taxa erro tools | — | <2% | ___ |

---

> *"Whatever you do, work at it with all your heart, as working for the Lord, not for human masters." — Colossians 3:23*
>
> **Soli Deo Gloria.**
