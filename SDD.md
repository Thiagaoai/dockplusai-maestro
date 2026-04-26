# SDD — MAESTRO v2.0

**System Design Document**
**Versão:** 2.0 (definitiva)
**Owner:** Thiago do Carmo — DockPlus AI
**Data:** 25 de abril de 2026
**Status:** Ready to implement

> Não promete 100%. Promete 85-90% nas tarefas operacionais que dão pra automatizar bem,
> com 0% de ações irreversíveis automatizadas, e visibilidade total via LangSmith.

---

## Sumário

1. [Visão geral e princípios](#1-visão-geral-e-princípios)
2. [Escopo e fora de escopo](#2-escopo-e-fora-de-escopo)
3. [Stack tecnológico (decisões finais)](#3-stack-tecnológico-decisões-finais)
4. [Arquitetura de alto nível](#4-arquitetura-de-alto-nível)
5. [Agents e subagents](#5-agents-e-subagents)
6. [Profiles dos negócios](#6-profiles-dos-negócios)
7. [Tools e integrações externas](#7-tools-e-integrações-externas)
8. [Fluxos de dados](#8-fluxos-de-dados)
9. [Estrutura de pastas](#9-estrutura-de-pastas)
10. [Modelo de dados (Supabase)](#10-modelo-de-dados-supabase)
11. [Configuração e secrets](#11-configuração-e-secrets)
12. [Segurança e compliance](#12-segurança-e-compliance)
13. [Observabilidade e evals](#13-observabilidade-e-evals)
14. [Performance e custos](#14-performance-e-custos)
15. [Resiliência e recuperação](#15-resiliência-e-recuperação)
16. [Riscos e mitigações](#16-riscos-e-mitigações)
17. [ADRs — decisões arquiteturais](#17-adrs--decisões-arquiteturais)
18. [Glossário](#18-glossário)

---

## 1. Visão geral e princípios

MAESTRO é o sistema multi-agent que automatiza operações dos negócios do ecossistema DockPlus, começando por **Roberts Landscape** e **DockPlus AI**, com expansão planejada para **All Granite, Cape Codder, Cheesebread, Bread & Roses, Flamma Verbi**.

### 1.0 Mandato operacional

MAESTRO é uma máquina de crescimento operacional. A arquitetura deve servir primeiro ao crescimento das empresas, não à elegância técnica.

Prioridade de produto e engenharia:

1. **Prospector** — achar oportunidades, enriquecer leads, abrir conversas e gerar reuniões qualificadas.
2. **Marketer** — produzir conteúdo, campanhas, testes e insights que aumentem demanda.
3. **Creator** — gerar assets, copies, relatórios e drafts em velocidade alta com controle humano.
4. **Growth operator** — deixar a empresa maior, mais inteligente, mais rápida, mais produtiva e mais lucrativa.
5. **Profit-first analyst** — toda automação deve buscar impacto em receita, margem, conversão, retenção, CAC, ROAS ou economia de horas.

Regra de arquitetura: uma integração, agent ou workflow só entra se aumentar velocidade, qualidade de decisão, capacidade comercial, produtividade ou lucro. Automação sem impacto operacional claro é backlog, não core.

### 1.1 Princípios de design (não-negociáveis)

1. **Function-first, profile-aware** — agents organizados por função (vendas, marketing, finanças), não por negócio. Cada negócio é um profile JSON.

2. **Humano no loop pra decisões importantes** — toda ação >$500, todo email pra cliente novo, toda publicação pública requer aprovação Thiago via Telegram.

3. **Determinístico onde possível, probabilístico onde necessário** — fluxo de controle (cadência, retry, scheduling) é state machine. Decisão linguística (qualificação, copy, classificação) é LLM.

4. **Idempotente por padrão** — toda webhook, toda ação externa pode ser executada N vezes sem efeito colateral.

5. **Observável end-to-end** — toda decisão registrada em LangSmith + Supabase. Zero black box.

6. **Reversível antes de tudo** — primeiro draft + preview, depois ação. Tools que enviam email, postam IG, cobram cartão são always-pause-first.

7. **Stack maduro acima de stack novo** — LangChain/LangGraph/LangSmith em vez de framework experimental.

8. **Vertical slice antes de escala** — primeiro provar um fluxo completo fake lead → Telegram approval → audit log → dry-run action. Só depois expandir para agents completos.

9. **Profit signal em todo agent** — cada agent registra qual métrica de negócio pretende impactar: receita, margem, conversão, retenção, custo, tempo economizado ou risco reduzido.

### 1.2 O que MAESTRO NÃO promete

- ❌ 100% das tarefas automatizadas
- ❌ Substituir decisão humana estratégica
- ❌ Substituir relacionamento humano com cliente
- ❌ Eliminar Bruna, Joana, Ana, Gustavo, Luanny — complementa, não substitui
- ❌ ROAS garantido em ads (tools agem, mercado decide)
- ❌ Conversão garantida de leads (qualifica, não vende)

### 1.3 O que MAESTRO promete (mensurável)

- ✅ Resposta a lead em <10 minutos, 24/7
- ✅ 5-7 posts Instagram/semana por negócio ativo
- ✅ Briefing executivo toda segunda 9h sem falhar
- ✅ Visibilidade financeira semanal (CFO) e de ads (CMO)
- ✅ Prospecting B2B sustentável gerando reuniões qualificadas
- ✅ Recomendações semanais para aumentar lucro, margem ou reduzir desperdício
- ✅ Custo operacional <$200/mês durante MVP, <$500/mês com 4 negócios
- ✅ Latência P90 <10s pra fluxos síncronos
- ✅ Uptime ≥99.5% (3.6h downtime/mês aceitável)

---

## 2. Escopo e fora de escopo

### 2.1 Em escopo — Fase 1 (MVP, 8 semanas)

**Negócios ativos:** Roberts Landscape + DockPlus AI

**Agents implementados:**
- Triage
- SDR (inbound leads)
- Marketing
- CFO
- CMO
- CEO
- Operations

**Canais:** Telegram bot único `@maestro_dockplus_bot`

**Fora de escopo Fase 1:**
- Prospecting Agent (Fase 2)
- Customer Success Agent (Fase 2)
- Brand Guardian, Reactivation, Competitive (Fase 2-3)
- Outros 5 negócios (Fase 3)
- WhatsApp/iMessage/Slack via OpenClaw (Fase 4 se justificar)
- Voice mode (Fase 4+)
- Multi-usuário (sempre fora de escopo)
- Pagamentos automatizados >$500 (sempre fora de escopo)

### 2.2 Em escopo — Fase 2 (Prospecting + extras, semanas 9-16)

- Prospecting Agent + 7 subagents
- Customer Success Agent
- Brand Guardian (subagent transversal)
- Domain de prospecção separado (`try-dockplusai.com`)
- Integração Clay.com OU Apollo+Hunter waterfall
- Adição de Cape Codder e All Granite como profiles

### 2.3 Em escopo — Fase 3 (Hardening + completude, semanas 17-24)

- Reactivation Subagent
- Competitive Intelligence Agent
- Cheesebread, Bread & Roses, Flamma Verbi profiles
- Sistema de evals semanais automatizado
- Dual-run com Bruna/Joana de 30 dias
- Release gradual (25% → 50% → 75% → 100%)

---

## 3. Stack tecnológico (decisões finais)

| Camada | Tecnologia | Versão | Justificativa |
|---|---|---|---|
| **Linguagem** | Python | 3.11 | Padrão ecosystem agents 2026, type hints maduros |
| **Orquestração** | LangGraph | 0.2.50+ | State machine + checkpointing nativo |
| **Agents/Tools** | LangChain | 0.3+ | 1000+ integrações prontas |
| **Observabilidade** | LangSmith | latest | Tracing nativo, evals automáticos |
| **API HTTP** | FastAPI | 0.115+ | Async, performance, padrão webhook |
| **Modelo principal** | Claude Sonnet 4.6 | - | Custo/qualidade ótimo conversação |
| **Modelo CEO** | Claude Opus 4.7 | - | Raciocínio profundo briefing semanal |
| **Modelo barato** | Claude Haiku 4.5 | - | Subagents simples, classificação |
| **Embeddings** | OpenAI text-embedding-3-small | - | Custo baixo, qualidade boa |
| **DB principal** | Supabase Postgres + pgvector | latest | Já contratado, vetorial nativo |
| **Sessions** | Redis | 7+ | LangGraph checkpointer oficial |
| **Canal** | Telegram Bot API | latest | Thiago já vive lá |
| **Reverse proxy** | Traefik | 3+ | Let's Encrypt automático |
| **Container** | Docker + Compose | latest | Padrão deploy VPS |
| **CI/CD** | GitHub Actions | - | Push → deploy via SSH |
| **Logs** | structlog → stdout | - | JSON estruturado, fácil grep |
| **Scheduler** | APScheduler | 3.10+ | Cron jobs in-process |
| **HTTP client** | httpx | 0.27+ | Async-first, retry built-in |
| **Validation** | Pydantic | 2.10+ | Settings + schemas |
| **Retry** | tenacity | 9+ | Exponential backoff |
| **Circuit breaker** | purgatory | latest | Async-native breaker |

### 3.1 Stack de enrichment/prospecção (Fase 2)

| Caso de uso | Ferramenta | Justificativa |
|---|---|---|
| **B2B contact discovery + waterfall enrichment** | **Clay.com** | Estado da arte 2026, 90%+ accuracy, substitui Apollo+Hunter+Clearbit |
| Backup B2B (caso Clay caro demais) | Apollo + Hunter.io | Já tem MCP Apollo, Hunter $49/mês, ~85% accuracy |
| Negócios locais (Roberts/All Granite/Cape Codder) | Google Maps Places API | Oficial, $200 grátis/mês |
| Imobiliário (high-intent home services) | Apify + Zillow scraper | Casa recém-comprada = lead premium pra Roberts/All Granite/Cape Codder |
| Research contextual | **Tavily** + **Perplexity** | Ambos já contratados, complementares |
| Buying signals B2B | Vibe Prospecting | MCP já contratado, eventos relevantes |
| LinkedIn enriquecimento | LinkedIn Sales Nav (manual) ou Apify (cuidado) | Premium B2B, integração via export periódico |

### 3.2 O que NÃO está no stack (decisões explícitas)

- ❌ **n8n** — workflow visual desnecessário, código é mais debugável
- ❌ **Make.com** — mesma razão acima
- ❌ **Zapier** — mesma razão, custo escala mal
- ❌ **OpenClaw (Fase 1)** — Telegram basta, complexidade prematura
- ❌ **Hermes self-hosted (Fase 1)** — VPS sem GPU, Claude API é viável
- ❌ **PhantomBuster** — LinkedIn pune contas, risco alto
- ❌ **ATTOM Data** — $400/mês caro pra começar, Zillow via Apify cobre
- ❌ **AutoGen / CrewAI** — frameworks com filosofia diferente, não casam com nosso modelo function-first

---

## 4. Arquitetura de alto nível

```
┌────────────────────────────────────────────────────────────────────┐
│  ENTRY POINTS                                                       │
│  ─ Telegram Bot (@maestro_dockplus_bot) — Thiago                   │
│  ─ Webhook GHL — leads inbound de cada negócio                     │
│  ─ Cron Scheduler — CFO/CMO/CEO weekly, Prospecting daily           │
│  ─ Webhook Gmail — replies a cold emails (Fase 2)                   │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ HTTPS
                               ↓
┌────────────────────────────────────────────────────────────────────┐
│  TRAEFIK (reverse proxy, Let's Encrypt SSL)                        │
└──────────────────────────────┬─────────────────────────────────────┘
                               ↓
┌────────────────────────────────────────────────────────────────────┐
│  FASTAPI APP (maestro/main.py)                                     │
│  Validação de webhooks, idempotency check, dispatch async          │
└──────────────────────────────┬─────────────────────────────────────┘
                               ↓
┌────────────────────────────────────────────────────────────────────┐
│  LANGGRAPH ORCHESTRATOR (maestro/graph.py)                         │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  TRIAGE NODE                                                 │  │
│  │  classifica: business + function + intent                   │  │
│  │  load profile JSON + carrega memória relevante              │  │
│  └────────┬────────────────────────────────────────────────────┘  │
│           │                                                        │
│  ┌────────┼──────┬──────┬──────┬──────┬──────┬──────┬───────┐   │
│  ↓        ↓      ↓      ↓      ↓      ↓      ↓      ↓       │   │
│ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌─────┐ ┌─────┐  │   │
│ │SDR │ │MKT │ │ CFO│ │ CMO│ │ CEO│ │ OPS│ │PROSP│ │ CS  │  │   │
│ └─┬──┘ └─┬──┘ └─┬──┘ └─┬──┘ └─┬──┘ └─┬──┘ └──┬──┘ └──┬──┘  │   │
│   │      │      │      │      │      │       │       │      │   │
│   │  subagents (LangChain) por agent                         │   │
│                                                                │   │
│  ┌──────────────────────────────────────────────────────────┐ │   │
│  │  HUMAN-IN-THE-LOOP NODE (interrupt())                    │ │   │
│  │  pausa grafo, espera Thiago aprovar via Telegram         │ │   │
│  │  state persiste em Redis até resposta                    │ │   │
│  └──────────────────────────────────────────────────────────┘ │   │
└────┼──────┼──────┼──────┼──────┼──────┼───────┼──────┬───────┘   │
     ↓      ↓      ↓      ↓      ↓      ↓       ↓       ↓           │
┌────────────────────────────────────────────────────────────────────┐
│  TOOL LAYER (maestro/tools/)                                       │
│                                                                     │
│  ── COMUNICAÇÃO ──        ── ENRICHMENT ──     ── ADS/MARKETING ── │
│  telegram.py              clay.py              meta_ads.py         │
│  gmail.py                 apollo.py            google_ads.py       │
│  calendar.py              maps.py              gbp.py              │
│  postforme.py             zillow_apify.py      tavily.py           │
│                           perplexity.py        replicate.py        │
│  ── CRM / FINANCE ──      hunter.py            ── DATA ──          │
│  ghl.py                   vibe_prospecting.py  supabase_db.py     │
│  stripe.py                                     redis_session.py    │
└──────────────────────────────┬─────────────────────────────────────┘
                               ↓
┌────────────────────────────────────────────────────────────────────┐
│  EXTERNAL APIS                                                      │
└────────────────────────────────────────────────────────────────────┘

PARALLEL STATE STORES:
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Redis        │  │ Supabase     │  │ LangSmith    │  │ Loki (Fase 3)│
│ sessions     │  │ memory long  │  │ traces+evals │  │ logs         │
│ checkpoints  │  │ idempotency  │  │              │  │              │
│ rate limits  │  │ audit log    │  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

---

## 5. Agents e subagents

### 5.1 Princípio de design

Cada **agent principal** é uma "função executiva" (vendas, marketing, etc.). Cada agent tem 2-7 **subagents** que são especialistas em sub-tarefas. Subagents são LangChain agents puros; agents principais são LangGraph subgrafos.

### 5.2 Tabela mestra de agents

| # | Agent | Modelo | Trigger | Subagents | Fase |
|---|---|---|---|---|---|
| 1 | **Triage** | Claude Haiku 4.5 | toda mensagem entrante | — | 1 |
| 2 | **SDR** | Claude Sonnet 4.6 | webhook GHL, mensagem inbound | 3 | 1 |
| 3 | **Marketing** | Claude Sonnet 4.6 + GPT-5 vision | request explícito, cron diário | 4 | 1 |
| 4 | **CFO** | Claude Sonnet 4.6 | cron segunda 7h, ask explícito | 3 | 1 |
| 5 | **CMO** | Claude Sonnet 4.6 | cron segunda 8h, ask explícito | 3 | 1 |
| 6 | **CEO** | Claude Opus 4.7 | cron segunda 9h, ask explícito | 2 | 1 |
| 7 | **Operations** | Claude Haiku 4.5 | tasks ad-hoc | 3 | 1 |
| 8 | **Prospecting** | Claude Sonnet 4.6 | cron daily, request explícito | 7 | 2 |
| 9 | **Customer Success** | Claude Sonnet 4.6 | cron weekly + post-job triggers | 4 | 2 |
| 10 | **Competitive Intel** | Claude Sonnet 4.6 | cron weekly | 3 | 3 |

### 5.3 Definições detalhadas

#### Agent 1: Triage
**Responsabilidade:** classifica toda mensagem em <500ms, despacha pro agent correto.

**Inputs:** mensagem texto, sender (Telegram chat_id ou webhook source), histórico recente da sessão.

**Output:** `{business: str, function: str, intent: str, confidence: float, target_agent: str}`

**Lógica:**
- Se confidence <0.7 → pede esclarecimento ao Thiago
- Se mensagem ambígua (multi-business) → assume business=last_active
- Cache de 5 minutos pra mesma sessão (não reclassifica toda mensagem)

---

#### Agent 2: SDR (inbound leads)
**Subagents:**

**2a. lead_qualifier**
- Input: dados do lead (nome, contato, source, mensagem)
- Lógica: cross-check com profile.qualification_criteria + Maps API (validar service area)
- Output: score 0-100 + justificativa estruturada
- Modelo: Claude Sonnet 4.6

**2b. email_drafter**
- Input: lead + score + profile.tone
- Lógica: gera subject + body em tom Roberts/DockPlus (depende do profile)
- Output: `{subject, body, send_after: datetime}`
- Modelo: Claude Sonnet 4.6
- Sempre passa por aprovação humana antes do envio na Fase 1

**2c. meeting_scheduler**
- Input: lead + duration_min
- Lógica: chama `calendar.find_free_slots`, ranqueia por preferência (manhã > tarde, terça-quinta > segunda/sexta)
- Output: lista de 3 slots + link calendly opcional

---

#### Agent 3: Marketing
**Subagents:**

**3a. content_creator**
- Reusa skill existente `carousel-autoposter` quando aplicável
- Para visuals: chama `replicate.generate_image` com prompt FLUX/Hermes
- Para Reels: chama skill `remotion-video-maker`
- Output: arquivos de imagem/vídeo + estrutura do post

**3b. caption_writer**
- Input: tema, profile.tone, target audience
- Output: caption otimizada (200-2200 chars dependendo de plataforma)
- Inclui CTA, emoji moderado conforme profile

**3c. hashtag_strategist**
- Output: 8-12 hashtags = 4 locais + 4 nicho + 2-4 trending
- Source: histórico de posts performados + Tavily trends

**3d. posting_scheduler**
- Lógica: consulta `business_metrics` pra horários históricos de melhor engagement
- Default Roberts: Ter/Qui 18h-19h
- Default DockPlus: Seg/Qua 9h-10h
- Output: scheduled_at em ISO 8601

---

#### Agent 4: CFO
**Subagents:**

**4a. invoice_reconciler**
- Bate Stripe charges vs GHL opportunities won
- Detecta gaps (cobrado sem job, job sem cobrança)
- Output: lista de discrepâncias

**4b. margin_analyst**
- Input: período (semana/mês)
- Lógica: receita total - custos diretos (materiais, mão-de-obra de subs) - alocação fixa
- Output: margem bruta % + comparação período anterior

**4c. cashflow_forecaster**
- Lógica: receitas confirmadas próximos 30/60/90 dias - despesas fixas conhecidas
- Output: projeção 3-cenários (pessimista/realista/otimista)

---

#### Agent 5: CMO
**Subagents:**

**5a. ad_performance_analyst**
- Input: Meta Ads + Google Ads + GBP insights última semana
- Output: ROAS, CPC, CPL trends + alertas de performance

**5b. budget_allocator**
- Input: performance + budget mensal
- Lógica: recomenda redistribuição (mais $$ pro que performa)
- Output: tabela "campanha → action (manter/aumentar X%/reduzir Y%/pausar)"
- Sempre requer aprovação Thiago se mudança >$500

**5c. creative_tester**
- Detecta fadiga de creative (CTR caindo >20% em 14 dias)
- Sugere novos ângulos baseado em top performers
- Output: lista de 3-5 hipóteses pra testar

---

#### Agent 6: CEO
**Subagents:**

**6a. weekly_briefing**
- Input: outputs de CFO + CMO + métricas operacionais (leads novos, jobs fechados, posts publicados)
- Modelo: Claude Opus 4.7 (precisa raciocínio profundo)
- Output: 1 página markdown estruturada
  - Resumo executivo (3 bullets)
  - Receita semana vs anterior
  - Pipeline (leads, qualified, won, value)
  - Marketing performance
  - 3 wins da semana
  - 3 alertas/preocupações

**6b. decision_preparer**
- Lógica: identifica decisões pendentes (ex: aprovar budget shift, contratar fornecedor, pausar ad)
- Output: 3-5 decisões com:
  - Contexto
  - Opções (2-3)
  - Recomendação
  - Botões inline keyboard pra Thiago decidir

---

#### Agent 7: Operations
**Subagents:**

**7a. calendar_manager**
- Tools: `calendar.find_free_slots`, `calendar.create_event`, `calendar.update_event`

**7b. follow_up_sender**
- Lógica: detecta opportunities GHL sem touch >7 dias, drafta follow-up
- Sempre requer aprovação Thiago

**7c. ghl_pipeline_mover**
- Move opportunities entre stages baseado em ações (email enviado → "contacted", reunião agendada → "qualified", etc.)
- Determinístico, não usa LLM

---

#### Agent 8: Prospecting (Fase 2)
**Subagents:**

**8a. icp_definer**
- Lê `profile.icp` e refina com base em wins históricos
- Output: filtros estruturados pra Clay/Apollo

**8b. list_builder**
- Tools: `clay.find_people`, `apollo.search_people`, `vibe.fetch_entities`, `maps.search_places`
- Output: 50-200 leads/semana enriched

**8c. enricher**
- Tools: `clay.enrich`, `tavily.crawl`, `apify.linkedin_posts`, `hunter.verify_email`
- Output: lead com 15+ campos validados

**8d. personalizer**
- Input: lead enriched + profile.tone + sample emails que converteram
- Output: email único por lead (subject + body + reasoning)
- Modelo: Claude Sonnet 4.6

**8e. cadence_orchestrator**
- State machine LangGraph com estados: queued → sent_1 → sent_2 → sent_3 → linkedin_flag → done
- Inputs: response from `reply_classifier` move estado pra "engaged" ou "stop"
- Persistência: Supabase `cadence_state` table

**8f. reply_classifier**
- Triggered por webhook Gmail
- Modelo: Claude Haiku 4.5 (alto volume, classificação simples)
- Output: `{intent: interested|not_interested|ooo|complaint|question, confidence, suggested_action}`
- Se complaint → STOP imediato + alerta crítico Thiago

**8g. deliverability_monitor**
- Cron a cada 4h
- Lê: bounce rate, spam complaints (Postmaster API), reply rate, open rate
- Thresholds:
  - Bounce >3% → pausa imediata
  - Spam complaint >0.1% → pausa imediata
  - Reply rate <2% por 3 semanas → pausa, refazer ICP/copy
- Notifica Thiago em qualquer pausa

---

#### Agent 9: Customer Success (Fase 2)
**Subagents:**

**9a. post_job_follow_up**
- Trigger: GHL opportunity → "won" + 30 dias
- Drafta email pedindo review Google + photo authorization
- Aprovação Thiago

**9b. churn_risk_detector** (DockPlus AI específico)
- Trigger: cliente DockPlus AI com baixa atividade (login/usage tracking)
- Output: alerta + sugestão de outreach

**9c. upsell_opportunity_finder**
- Lê histórico cliente, detecta padrões (ex: cliente Roberts fez patio mas não tem outdoor lighting)
- Output: lista priorizada de upsell opportunities

**9d. review_responder**
- Trigger: nova review Google Business
- Drafta resposta apropriada (positiva ou negativa)
- Aprovação Thiago obrigatória

---

#### Agent 10: Competitive Intelligence (Fase 3)
**Subagents:**

**10a. competitor_monitor**
- Tools: `maps.get_reviews`, `apify.scrape_competitor_site`, `tavily.research`
- Output: changes detectados na semana (preços, ofertas, novos serviços)

**10b. market_trend_analyst**
- Input: pesquisa Tavily + Perplexity sobre indústria
- Output: 3-5 trends relevantes pra cada negócio

**10c. positioning_advisor**
- Lê output dos 2 anteriores
- Recomenda ajustes de posicionamento/copy/preço

---

### 5.4 Subagent transversal: Brand Guardian (Fase 2)

**Não é agent principal.** É um subagent invocado por **qualquer agent** antes de produzir output público.

**Responsabilidade:** valida output contra `profile.brand_rules` antes de:
- Email externo
- Post Instagram
- Caption
- Resposta de review
- Resposta a cold email reply

**Validações:**
- Tom alinhado com profile
- Sem palavras proibidas
- Sem hard-sell agressivo
- Sem promessas que não pode cumprir
- Sem informações sensíveis

**Output:** `{approved: bool, issues: list[str], suggested_revision: str}`

Se `approved=false`, agent retry com revisão. Após 2 falhas, escala pro Thiago.

---

## 6. Profiles dos negócios

Cada profile é arquivo JSON em `maestro/profiles/{business_id}.json`.

### 6.1 Schema base (todos os profiles seguem)

```typescript
{
  business_id: string,           // "roberts", "dockplusai", etc.
  business_name: string,
  business_type: "B2C" | "B2B" | "B2B2C",
  active: boolean,               // se false, agents não processam
  
  contact: {
    phone: string,
    email: string,
    address?: string,
    website?: string
  },
  
  service_area: string[] | "global",
  
  tone: {
    voice: string,                // descrição em prosa
    formality: 1-5,               // 1=casual, 5=formal
    do: string[],
    do_not: string[],
    signature: string,
    sample_emails: string[],      // 3-5 exemplos reais que converteram
    sample_posts: string[]
  },
  
  offerings: [
    {
      name: string,
      description: string,
      ticket_avg_usd: number,
      ticket_min_usd: number,
      ticket_max_usd: number,
      season: string,
      conversion_rate: number     // dado histórico
    }
  ],
  
  qualification_criteria: {       // SDR usa
    min_ticket_usd: number,
    in_service_area_required: boolean,
    ready_within_months_max: number,
    custom_rules: string[]
  },
  
  decision_thresholds: {
    thiago_approval_above_usd: number,    // default 500
    auto_book_meeting: boolean,
    auto_send_email_to_lead: boolean,
    auto_publish_social: boolean
  },
  
  marketing: {
    instagram_handle: string,
    posting_frequency_per_week: number,
    best_posting_times: string[],
    visual_style: string,
    hashtag_strategy: { local: string[], niche: string[] }
  },
  
  ads: {
    meta_ad_account_id: string | null,
    google_ads_customer_id: string | null,
    google_lsa_active: boolean,
    monthly_budget_usd: number
  },
  
  brand_rules: {                  // Brand Guardian usa
    forbidden_words: string[],
    required_disclaimers: string[],
    competitor_mentions_allowed: boolean
  },
  
  icp?: {                         // Prospecting usa, só pra B2B
    industries: string[],
    company_size: { min_employees: number, max_employees: number },
    revenue_range: { min_usd: number, max_usd: number },
    geography: string[],
    tech_stack_signals: string[],
    buying_signals: string[],
    pain_points: string[]
  },
  
  team: {
    primary_humans: [
      { name: string, role: string, telegram_chat_id?: string }
    ]
  }
}
```

### 6.2 Profile: Roberts Landscape (resumido — completo no repo)

```json
{
  "business_id": "roberts",
  "business_name": "Roberts Landscape Design & Construction",
  "business_type": "B2C",
  "active": true,
  "contact": {
    "phone": "(508) 464-4878",
    "email": "info@robertslandscape.com"
  },
  "service_area": ["Cape Cod", "Falmouth", "Sandwich", "Mashpee", "Bourne", "Barnstable"],
  "tone": {
    "voice": "Professional, warm, locally-rooted Cape Cod craftsman. Confident but never pushy.",
    "formality": 3,
    "do": ["mention Cape Cod", "showcase craftsmanship", "use specific project examples"],
    "do_not": ["hard-sell", "discount-driven", "generic stock language", "emojis em excesso"],
    "signature": "Roberts Landscape — Cape Cod outdoor craftsmanship",
    "sample_emails": ["..."]
  },
  "offerings": [
    {"name": "Hardscape", "ticket_avg_usd": 18000, "ticket_min_usd": 8000, "ticket_max_usd": 50000, "season": "Apr-Oct"},
    {"name": "Masonry", "ticket_avg_usd": 25000, "ticket_min_usd": 12000, "ticket_max_usd": 80000, "season": "Apr-Oct"},
    {"name": "Landscape Design", "ticket_avg_usd": 8000, "ticket_min_usd": 3000, "ticket_max_usd": 20000, "season": "year-round"},
    {"name": "Outdoor Lighting", "ticket_avg_usd": 5000, "ticket_min_usd": 2500, "ticket_max_usd": 15000, "season": "year-round"}
  ],
  "qualification_criteria": {
    "min_ticket_usd": 5000,
    "in_service_area_required": true,
    "ready_within_months_max": 6
  },
  "decision_thresholds": {
    "thiago_approval_above_usd": 500,
    "auto_book_meeting": false,
    "auto_send_email_to_lead": false,
    "auto_publish_social": false
  }
}
```

### 6.3 Profile: DockPlus AI (resumido)

```json
{
  "business_id": "dockplusai",
  "business_name": "DockPlus AI Solutions",
  "business_type": "B2B",
  "active": true,
  "service_area": "global",
  "tone": {
    "voice": "Technical authority with founder warmth. Direct, no fluff. Speaks builder-to-builder.",
    "formality": 3,
    "do": ["use concrete examples (Roberts case study)", "show ROI numbers", "speak founder-to-founder"],
    "do_not": ["enterprise-speak", "vague AI hype", "promise 100% automation"]
  },
  "offerings": [
    {"name": "AI Automation Consulting", "ticket_avg_usd": 8000, "ticket_min_usd": 3000, "ticket_max_usd": 25000},
    {"name": "Custom Agent Build", "ticket_avg_usd": 25000, "ticket_min_usd": 15000, "ticket_max_usd": 80000},
    {"name": "Monthly Retainer", "ticket_avg_usd": 5000, "ticket_min_usd": 2500, "ticket_max_usd": 15000}
  ],
  "icp": {
    "industries": ["home services", "professional services", "healthcare", "real estate"],
    "company_size": {"min_employees": 5, "max_employees": 100},
    "revenue_range": {"min_usd": 500000, "max_usd": 10000000},
    "geography": ["US", "BR"],
    "buying_signals": ["hired marketing manager <90d", "raised funding <180d", "expanded location"],
    "pain_points": ["lead response time", "manual SDR", "ad inefficiency", "content inconsistency"]
  }
}
```

Profiles para All Granite, Cape Codder, Cheesebread, Bread & Roses, Flamma Verbi serão criados nas Fases 2-3 com mesmo schema.

---

## 7. Tools e integrações externas

Tools são funções Python `async` decoradas como `@tool` (LangChain). Cada uma testada isoladamente. Cada tool tem retry exponencial (max 3 tentativas) e timeout default 30s.

### 7.1 Mapa completo de tools

| Tool file | Funções principais | API externa | Custo |
|---|---|---|---|
| `telegram.py` | `send_message`, `send_inline_keyboard`, `edit_message`, `download_file` | Telegram Bot API | grátis |
| `gmail.py` | `send_email`, `read_inbox`, `get_thread`, `check_bounces` | Gmail API (OAuth2) | grátis |
| `calendar.py` | `find_free_slots`, `create_event`, `update_event`, `get_event` | Google Calendar API | grátis |
| `ghl.py` | `create_contact`, `update_contact`, `add_to_pipeline`, `move_stage`, `create_opportunity` | GoHighLevel API | já contratado |
| `stripe.py` | `list_charges`, `get_customer`, `summarize_revenue` | Stripe API (read-only) | grátis (free tier) |
| `postforme.py` | `publish_carousel`, `schedule_post`, `get_analytics` | Postforme API | já contratado |
| `meta_ads.py` | `get_campaign_insights`, `get_ad_performance` | Meta Marketing API | grátis (token) |
| `google_ads.py` | `get_campaign_metrics`, `get_keyword_performance` | Google Ads API | grátis (após approval token) |
| `gbp.py` | `get_reviews`, `get_metrics`, `respond_to_review` | Google Business Profile API | grátis |
| `tavily.py` | `search`, `crawl`, `extract` | Tavily API | já contratado |
| `perplexity.py` | `query`, `research` | Perplexity API | já contratado |
| `replicate.py` | `generate_image`, `generate_video` | Replicate API | pay-per-use ~$20-50/mês |
| `clay.py` (Fase 2) | `find_people`, `enrich_lead`, `waterfall_email` | Clay.com API | $149-349/mês |
| `apollo.py` (Fase 2) | `search_people`, `bulk_match`, `get_company` | Apollo API (MCP) | $59-119/mês |
| `hunter.py` (Fase 2) | `verify_email`, `find_email`, `domain_search` | Hunter.io API | $49/mês |
| `maps.py` (Fase 2) | `search_places`, `get_place_details`, `get_reviews`, `geocode` | Google Maps Places API | $200 free, então pay-per-use |
| `zillow_apify.py` (Fase 2) | `recently_sold`, `property_details`, `area_stats` | Apify (Zillow scraper) | $49-499/mês |
| `vibe_prospecting.py` (Fase 2) | `fetch_entities`, `enrich_business`, `match_business` | Vibe Prospecting API (MCP) | já contratado |
| `supabase_db.py` | CRUD em todas as tabelas | Supabase | já contratado |
| `redis_session.py` | get/set/delete sessions, checkpointer | Redis | grátis (self-hosted) |

### 7.2 Padrão obrigatório de tool

```python
from typing import Any
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential
import httpx
import structlog

log = structlog.get_logger()

@tool
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
async def ghl_create_contact(
    name: str,
    phone: str,
    email: str | None = None,
    business: str = "roberts",
    *,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """
    Cria contato no GoHighLevel para o negócio especificado.
    
    Args:
        name: Nome completo do contato
        phone: Telefone E.164 ou nacional
        email: Email opcional
        business: business_id do profile
        idempotency_key: chave única para evitar duplicação
    
    Returns:
        dict com id, status, e ghl_url
    
    Raises:
        ValueError: se phone inválido
        httpx.HTTPError: se API falhar após retries
    """
    log.info("ghl_create_contact_start", business=business, name_redacted=mask(name))
    
    # idempotency check
    if idempotency_key and await _is_processed(idempotency_key):
        log.info("ghl_create_contact_skipped_duplicate", idempotency_key=idempotency_key)
        return await _get_processed_result(idempotency_key)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://services.leadconnectorhq.com/contacts/",
            headers={"Authorization": f"Bearer {settings.ghl_token(business)}"},
            json={"firstName": name.split()[0], "lastName": " ".join(name.split()[1:]),
                  "phone": phone, "email": email, "tags": [business]}
        )
        response.raise_for_status()
        result = response.json()
    
    if idempotency_key:
        await _mark_processed(idempotency_key, result)
    
    log.info("ghl_create_contact_success", business=business, ghl_id=result["id"])
    return result
```

Toda tool segue esse template: type hints, docstring, retry, idempotency, structured logging, redaction de PII.

---

## 8. Fluxos de dados

### 8.1 Fluxo síncrono — Thiago manda mensagem Telegram

```
1. Thiago digita: "como tá o pipeline do Roberts?"
2. Telegram → POST /telegram/webhook (HMAC validated)
3. FastAPI:
   a. Verifica chat_id whitelist
   b. Verifica idempotency (message_id)
   c. Cria/recupera thread_id Redis
4. LangGraph dispatch async com state inicial
5. TRIAGE node:
   - Modelo: Claude Haiku 4.5
   - Classifica: business=roberts, function=cfo, intent=pipeline_status
   - Confidence 0.95
6. Routing condicional → CFO Agent
7. CFO Agent invoca subagents:
   - margin_analyst lê Supabase business_metrics
   - cashflow_forecaster calcula projeção
8. Output formatado pelo agent (markdown Telegram-friendly)
9. Tool `telegram.send_message` envia resposta
10. Toda execução logada em LangSmith + Supabase agent_runs
```

**SLA:** P90 <8s end-to-end.

### 8.2 Fluxo assíncrono — Lead inbound via webhook GHL

```
1. Lead preenche form Roberts → GHL trigger webhook
2. POST /ghl/webhook com HMAC SHA-256 signature
3. FastAPI:
   a. Valida HMAC
   b. Extrai event_id, verifica processed_events table
   c. Se duplicate → 200 OK silent
   d. Se novo → marca como processing
4. Dispatch direto pro SDR Agent (skip Triage, business inferido do GHL location)
5. SDR Agent:
   - lead_qualifier: chama maps.geocode pra validar service area, calcula score
   - email_drafter: gera email customizado
   - meeting_scheduler: busca 3 slots
6. HUMAN-IN-THE-LOOP node:
   - LangGraph interrupt()
   - Estado salva em Redis
   - Tool telegram.send_inline_keyboard envia ao Thiago:
     "Lead novo: [nome] - score [X]/100. [Aprovar] [Editar] [Rejeitar]"
7. Thiago clica "Aprovar"
8. LangGraph retoma execution:
   - gmail.send_email
   - calendar.create_event
   - ghl.move_stage → "contacted"
9. telegram.send_message: "✅ enviado, agendado pra quinta 14h"
```

**SLA:** end-to-end <60s do webhook até notificação Thiago.

### 8.3 Fluxo cron — segunda 7h

```
07:00 UTC | CFO Agent dispara
  → invoice_reconciler.run()
  → margin_analyst.run()
  → cashflow_forecaster.run()
  → escreve em business_metrics (metric_type='cfo_weekly')
  
08:00 UTC | CMO Agent dispara
  → ad_performance_analyst.run()
  → budget_allocator.run()
  → creative_tester.run()
  → escreve em business_metrics (metric_type='cmo_weekly')

09:00 UTC | CEO Agent dispara
  → lê business_metrics dos últimos 7 dias
  → weekly_briefing gera markdown
  → decision_preparer identifica 3-5 decisões
  → telegram.send_message com briefing + inline keyboards
```

### 8.4 Fluxo Prospecting (Fase 2) — daily

```
06:00 UTC | Prospecting Agent dispara (apenas DockPlus AI Fase 2)
  → list_builder consulta Clay/Apollo com filtros ICP
  → enricher processa 50 leads novos
  → personalizer gera 50 emails únicos
  → 50 emails entram em queue (Supabase prospecting_queue)

07:00-19:00 UTC | Sender (rate-limited)
  → A cada 10min, pega 3-4 emails da queue
  → gmail.send_email via mailbox prospect@try-dockplusai.com
  → marca como sent_1 em cadence_state

A cada 4h | deliverability_monitor
  → checa bounce rate, spam complaints, reply rate
  → pausa se thresholds violados

Trigger Gmail webhook | reply_classifier
  → classifica resposta
  → se interested → handoff pro SDR Agent
  → se complaint → STOP + alerta crítico Thiago
```

---

## 9. Estrutura de pastas

```
maestro/
├── docs/
│   ├── SDD.md                       ← este arquivo
│   ├── PRD.md                       ← documento irmão
│   ├── TASK.md                      ← lista pra Cursor
│   ├── CODEX_TASKS.md               ← lista pra Codex CLI
│   ├── RUNBOOK.md                   ← incidentes e troubleshooting
│   ├── PROMPTS.md                   ← versionamento de system prompts
│   └── ADR/                         ← architectural decision records
│       ├── ADR-001-langgraph.md
│       ├── ADR-002-no-n8n.md
│       └── ...
│
├── maestro/                         ← código Python (Cursor zone)
│   ├── __init__.py
│   ├── main.py                      ← FastAPI app
│   ├── config.py                    ← Pydantic Settings
│   ├── graph.py                     ← LangGraph orchestrator principal
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── triage.py
│   │   ├── sdr.py
│   │   ├── marketing.py
│   │   ├── cfo.py
│   │   ├── cmo.py
│   │   ├── ceo.py
│   │   ├── operations.py
│   │   ├── prospecting.py           ← Fase 2
│   │   ├── customer_success.py      ← Fase 2
│   │   └── competitive_intel.py     ← Fase 3
│   │
│   ├── subagents/
│   │   ├── sdr/
│   │   │   ├── lead_qualifier.py
│   │   │   ├── email_drafter.py
│   │   │   └── meeting_scheduler.py
│   │   ├── marketing/...
│   │   ├── cfo/...
│   │   ├── cmo/...
│   │   ├── ceo/...
│   │   ├── operations/...
│   │   ├── prospecting/...          ← Fase 2
│   │   ├── customer_success/...     ← Fase 2
│   │   ├── competitive_intel/...    ← Fase 3
│   │   └── _shared/
│   │       └── brand_guardian.py    ← transversal Fase 2
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── telegram.py
│   │   ├── gmail.py
│   │   ├── calendar.py
│   │   ├── ghl.py
│   │   ├── stripe.py
│   │   ├── postforme.py
│   │   ├── meta_ads.py
│   │   ├── google_ads.py
│   │   ├── gbp.py
│   │   ├── tavily.py
│   │   ├── perplexity.py
│   │   ├── replicate.py
│   │   ├── supabase_db.py
│   │   └── _enrichment/             ← Fase 2
│   │       ├── clay.py
│   │       ├── apollo.py
│   │       ├── hunter.py
│   │       ├── maps.py
│   │       ├── zillow_apify.py
│   │       └── vibe_prospecting.py
│   │
│   ├── memory/
│   │   ├── redis_session.py
│   │   ├── supabase_long.py
│   │   └── decay.py                 ← scoring híbrido
│   │
│   ├── profiles/
│   │   ├── _schema.py               ← Pydantic model
│   │   ├── roberts.json
│   │   ├── dockplusai.json
│   │   ├── all_granite.json         ← Fase 2
│   │   ├── cape_codder.json         ← Fase 2
│   │   ├── cheesebread.json         ← Fase 3
│   │   ├── bread_and_roses.json     ← Fase 3
│   │   └── flamma_verbi.json        ← Fase 3
│   │
│   ├── webhooks/
│   │   ├── telegram.py
│   │   ├── ghl.py
│   │   └── gmail.py                 ← Fase 2 (replies)
│   │
│   ├── schedulers/
│   │   ├── weekly.py                ← CFO/CMO/CEO segunda
│   │   ├── daily.py                 ← Prospecting Fase 2
│   │   └── monitoring.py            ← deliverability, custos
│   │
│   ├── prompts/                     ← versionado!
│   │   ├── v1/
│   │   │   ├── triage.txt
│   │   │   ├── sdr_qualifier.txt
│   │   │   └── ...
│   │   └── v2/
│   │       └── ...
│   │
│   ├── evals/                       ← Fase 2
│   │   ├── datasets/
│   │   │   ├── sdr_leads.jsonl
│   │   │   ├── marketing_posts.jsonl
│   │   │   └── ...
│   │   └── runners/
│   │       └── weekly_eval.py
│   │
│   └── utils/
│       ├── logging.py
│       ├── security.py
│       ├── idempotency.py
│       ├── circuit_breaker.py
│       └── pii.py                   ← redaction
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── scripts/                         ← Codex CLI zone
│   ├── deploy.sh
│   ├── healthcheck.sh
│   ├── seed_supabase.sql
│   ├── backup_supabase.sh
│   ├── cost_monitor.py
│   ├── telegram_setup.sh
│   └── domain_warmup.sh             ← Fase 2
│
├── docker-compose.yml
├── docker-compose.dev.yml
├── Dockerfile
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── deploy.yml
└── README.md
```

---

## 10. Modelo de dados (Supabase)

### 10.1 Tabelas core (Fase 1)

```sql
-- Conversações Telegram
CREATE TABLE conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  telegram_chat_id BIGINT NOT NULL,
  thread_id TEXT NOT NULL UNIQUE,
  business TEXT NOT NULL DEFAULT 'roberts',
  started_at TIMESTAMPTZ DEFAULT NOW(),
  last_active_at TIMESTAMPTZ DEFAULT NOW(),
  message_count INT DEFAULT 0,
  total_cost_usd NUMERIC(10,6) DEFAULT 0
);

CREATE INDEX idx_conv_chat ON conversations(telegram_chat_id);
CREATE INDEX idx_conv_active ON conversations(last_active_at DESC);

-- Execuções de agents (audit + analytics)
CREATE TABLE agent_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID REFERENCES conversations(id),
  business TEXT NOT NULL,
  agent_name TEXT NOT NULL,
  subagents_called TEXT[],
  tools_called JSONB,
  input TEXT,
  output TEXT,
  tokens_in INT,
  tokens_out INT,
  cost_usd NUMERIC(10,6),
  latency_ms INT,
  error TEXT,
  langsmith_trace_url TEXT,
  prompt_version TEXT,
  human_approved BOOLEAN,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_runs_business ON agent_runs(business, created_at DESC);
CREATE INDEX idx_runs_agent ON agent_runs(agent_name, created_at DESC);
CREATE INDEX idx_runs_cost ON agent_runs(cost_usd DESC, created_at DESC);

-- Idempotência (CRÍTICO)
CREATE TABLE processed_events (
  event_id TEXT PRIMARY KEY,
  source TEXT NOT NULL,           -- 'telegram', 'ghl', 'gmail', 'cron'
  business TEXT,
  result JSONB,
  processed_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '7 days'
);

CREATE INDEX idx_events_expires ON processed_events(expires_at);

-- Audit log imutável
CREATE TABLE audit_log (
  id BIGSERIAL PRIMARY KEY,
  event_type TEXT NOT NULL,        -- 'agent_decision', 'human_approval', 'tool_call', 'config_change'
  business TEXT,
  agent TEXT,
  action TEXT NOT NULL,
  payload JSONB NOT NULL,
  prev_hash TEXT,
  hash TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_business_time ON audit_log(business, created_at DESC);
-- Append-only: rejeita UPDATE/DELETE via trigger
CREATE OR REPLACE FUNCTION reject_audit_modifications()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER no_update_audit BEFORE UPDATE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION reject_audit_modifications();
CREATE TRIGGER no_delete_audit BEFORE DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION reject_audit_modifications();

-- Métricas de negócio (CFO/CMO/CEO output)
CREATE TABLE business_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business TEXT NOT NULL,
  metric_type TEXT NOT NULL,
  metric_data JSONB NOT NULL,
  generated_by TEXT,
  period_start DATE,
  period_end DATE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_metrics_business_type_period ON business_metrics(business, metric_type, period_start DESC);

-- Leads (cache local + tracking)
CREATE TABLE leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ghl_contact_id TEXT UNIQUE,
  business TEXT NOT NULL,
  name TEXT,
  phone TEXT,
  email TEXT,
  source TEXT,
  estimated_ticket_usd NUMERIC,
  qualification_score INT,
  qualification_reasoning TEXT,
  status TEXT DEFAULT 'new',
  thiago_approved BOOLEAN DEFAULT FALSE,
  thiago_approved_at TIMESTAMPTZ,
  enrichment_data JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_leads_business_status ON leads(business, status);
CREATE INDEX idx_leads_score ON leads(qualification_score DESC);

-- Memória semântica (pgvector)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE memory_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business TEXT NOT NULL,
  content TEXT NOT NULL,
  embedding VECTOR(1536),
  metadata JSONB,
  importance_score NUMERIC DEFAULT 0.5,  -- 0-1, manual via /lembrar
  created_at TIMESTAMPTZ DEFAULT NOW(),
  last_accessed_at TIMESTAMPTZ DEFAULT NOW(),
  access_count INT DEFAULT 0
);

CREATE INDEX idx_memory_business ON memory_chunks(business);
CREATE INDEX ON memory_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Feedback/correções do Thiago
CREATE TABLE corrections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_run_id UUID REFERENCES agent_runs(id),
  feedback TEXT NOT NULL,         -- '👍', '👎', ou texto
  thiago_correction TEXT,
  applied_in_prompt_version TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Custo diário agregado (pra kill switch)
CREATE TABLE daily_costs (
  date DATE PRIMARY KEY,
  total_cost_usd NUMERIC(10,4) NOT NULL,
  by_agent JSONB,
  by_business JSONB,
  alerted BOOLEAN DEFAULT FALSE,
  killed_at TIMESTAMPTZ
);
```

### 10.2 Tabelas Fase 2 (prospecting)

```sql
-- Estado de cadência de prospecting
CREATE TABLE cadence_state (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business TEXT NOT NULL,
  prospect_email TEXT NOT NULL,
  prospect_data JSONB,
  current_stage TEXT NOT NULL,    -- 'queued', 'sent_1', 'sent_2', 'sent_3', 'engaged', 'stopped'
  current_stage_at TIMESTAMPTZ,
  next_action_at TIMESTAMPTZ,
  reply_classification TEXT,
  stop_reason TEXT,
  thread_id TEXT,
  mailbox_used TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(business, prospect_email)
);

CREATE INDEX idx_cadence_next_action ON cadence_state(next_action_at) WHERE current_stage NOT IN ('engaged','stopped');
CREATE INDEX idx_cadence_business_stage ON cadence_state(business, current_stage);

-- Métricas de deliverability
CREATE TABLE deliverability_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  date DATE NOT NULL,
  business TEXT NOT NULL,
  mailbox TEXT NOT NULL,
  emails_sent INT,
  bounces INT,
  spam_complaints INT,
  opens INT,
  replies INT,
  positive_replies INT,
  domain_reputation TEXT,         -- from Postmaster API
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(date, business, mailbox)
);
```

---

## 11. Configuração e secrets

### 11.1 `.env` completo

```bash
# === MODELOS ===
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# === OBSERVABILIDADE ===
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=maestro-prod

# === TELEGRAM ===
TELEGRAM_BOT_TOKEN=...
TELEGRAM_WEBHOOK_SECRET=<random_64_chars>
TELEGRAM_THIAGO_CHAT_ID=...

# === GOHIGHLEVEL (uma chave por business) ===
GHL_TOKEN_ROBERTS=...
GHL_LOCATION_ID_ROBERTS=...
GHL_WEBHOOK_SECRET_ROBERTS=...
GHL_TOKEN_DOCKPLUSAI=...
GHL_LOCATION_ID_DOCKPLUSAI=...
GHL_WEBHOOK_SECRET_DOCKPLUSAI=...

# === GOOGLE WORKSPACE (Gmail + Calendar via OAuth) ===
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...

# === SUPABASE ===
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=...
SUPABASE_ANON_KEY=...

# === REDIS ===
REDIS_URL=redis://redis:6379/0

# === ADS ===
META_ACCESS_TOKEN=...
META_AD_ACCOUNT_ROBERTS=act_...
META_AD_ACCOUNT_DOCKPLUSAI=act_...
GOOGLE_ADS_DEVELOPER_TOKEN=...
GOOGLE_ADS_CUSTOMER_ID_ROBERTS=...
GOOGLE_ADS_CUSTOMER_ID_DOCKPLUSAI=...

# === FINANCE ===
STRIPE_SECRET_KEY_ROBERTS=sk_live_...
STRIPE_SECRET_KEY_DOCKPLUSAI=sk_live_...

# === MARKETING/SOCIAL ===
POSTFORME_API_KEY=...
POSTFORME_ACCOUNT_ROBERTS=...
POSTFORME_ACCOUNT_DOCKPLUSAI=...
GBP_API_KEY=...                 # Google Business Profile

# === RESEARCH/ENRICHMENT ===
TAVILY_API_KEY=...
PERPLEXITY_API_KEY=...
REPLICATE_API_TOKEN=...

# === FASE 2 (PROSPECTING) ===
CLAY_API_KEY=...                # OU Apollo+Hunter
APOLLO_API_KEY=...
HUNTER_API_KEY=...
GOOGLE_MAPS_API_KEY=...
APIFY_TOKEN=...
VIBE_PROSPECTING_API_KEY=...

# === PROSPECTING MAILBOXES (DockPlus AI Fase 2) ===
PROSPECT_DOMAIN_DOCKPLUSAI=try-dockplusai.com
PROSPECT_MAILBOX_1=outreach@try-dockplusai.com
PROSPECT_MAILBOX_1_REFRESH_TOKEN=...
# ... até 5 mailboxes pra rotação

# === APP ===
APP_ENV=production              # 'dev' | 'staging' | 'production'
LOG_LEVEL=INFO
WEBHOOK_BASE_URL=https://maestro.dockplus.app
THIAGO_APPROVAL_THRESHOLD_USD=500
DAILY_COST_KILL_USD=30
DAILY_COST_ALERT_USD=15
```

### 11.2 Secrets management

- `.env` **nunca** commitado
- Produção: usa Docker secrets (não env vars)
- CI/CD: GitHub Actions secrets
- Rotação: trimestral pra todas as keys

---

## 12. Segurança e compliance

### 12.1 Princípios

1. **Whitelist over blacklist** — só Thiago pode disparar agents
2. **Validação em todo entry point** — HMAC, secret_token, rate limits
3. **Princípio do menor privilégio** — Stripe read-only, GHL só endpoints necessários
4. **Reversibilidade** — toda ação destrutiva exige aprovação humana
5. **PII redaction** — emails/phones nunca em logs
6. **Encryption at rest** — Supabase nativo, Redis com password

### 12.2 Validações específicas

| Entry point | Validação |
|---|---|
| Telegram webhook | `X-Telegram-Bot-Api-Secret-Token` header + chat_id whitelist |
| GHL webhook | HMAC SHA-256 com secret per business |
| Gmail webhook (Fase 2) | Pub/Sub signed JWT |
| FastAPI public endpoints | Rate limit (slowapi): 10 req/min global |
| Internal cron | Lock distribuído via Redis (evita double-trigger) |

### 12.3 Compliance

- **CAN-SPAM (US)**: todo email tem unsubscribe + endereço físico (Roberts e DockPlus AI têm)
- **LGPD (BR)**: consentimento explícito antes de cold email pra brasileiros (Fase 2 cuidado especial)
- **GDPR-ready**: Supabase RLS configurada, pode atender requests "delete my data"
- **PCI**: zero — não armazenamos dados de cartão. Stripe lida tudo.

### 12.4 Modelo de ameaças

| Ameaça | Mitigação |
|---|---|
| Atacante descobre webhook URL | secret_token + HMAC + chat_id whitelist |
| Vazamento de API keys | Docker secrets, rotação trimestral, monitoring de logs |
| Agent executa ação cara errada | Hard threshold $500, sempre humano |
| LLM hallucina ação destrutiva | Tools destrutivas têm `dry_run=True` default + interrupt() |
| Supabase mal configurado vaza dados | RLS policies, service_key só backend, audit log |
| Spam complaint derruba domínio | Domain prospecção separado, deliverability monitor 4h |
| Prompt injection via lead message | Input sanitization + system prompt locks role |

---

## 13. Observabilidade e evals

### 13.1 LangSmith

- **Tracing total**: toda invocação registra trace completo
- **Project per environment**: `maestro-dev`, `maestro-staging`, `maestro-prod`
- **Tags**: `business=roberts`, `agent=sdr`, `prompt_version=v3`
- **Custos por trace**: visualização nativa
- **Datasets**: 30-50 casos reais por agent pra evals

### 13.2 Evals automáticos (Fase 2)

```python
# evals/runners/weekly_eval.py
from langsmith.evaluation import evaluate

# Roda toda sexta às 22h UTC
# Compara modelo atual vs anterior em dataset de produção

results = evaluate(
    target=sdr_qualifier_chain,
    data="sdr_leads_dataset_v1",
    evaluators=[
        accuracy_evaluator,      # score qualificação correto?
        tone_evaluator,          # tom Roberts?
        action_evaluator         # propôs ação correta?
    ]
)

# Se score regrediu >5%, alerta crítico Thiago
```

### 13.3 Métricas operacionais (Grafana futuro, MVP CLI)

```
DASHBOARD (MVP CLI: python scripts/dashboard.py)
─────────────────────────────────────────────────
LATÊNCIA P50/P90/P99 por agent (last 24h)
TAXA DE ERRO por tool (last 24h)
CUSTO HORA/DIA/SEMANA total + por business
LEADS PROCESSADOS por business (last 7d)
APROVAÇÕES THIAGO: aprovado/rejeitado (last 7d)
DELIVERABILITY (Fase 2): bounce, spam, reply rate
```

### 13.4 Logs estruturados

```python
log.info(
    "agent_run_completed",
    correlation_id="...",
    business="roberts",
    agent="sdr",
    subagents=["lead_qualifier", "email_drafter", "meeting_scheduler"],
    tools_called=["maps.geocode", "ghl.create_contact", "calendar.find_free_slots"],
    tokens_in=2341,
    tokens_out=687,
    cost_usd=0.0234,
    latency_ms=4321,
    success=True,
    human_approved=True,
    prompt_version="v2"
)
```

### 13.5 Alertas (Telegram)

| Evento | Severidade | Notifica |
|---|---|---|
| Custo dia >$15 | INFO | Thiago |
| Custo dia >$30 | CRÍTICO | Thiago + kill switch |
| Erro tool >10% em 1h | WARNING | Thiago |
| Anthropic 429 sustained | CRÍTICO | Thiago |
| Spam complaint >0.05% | CRÍTICO | Thiago + pausa prospecting |
| Eval score regrediu >5% | WARNING | Thiago + Gustavo |
| Webhook falha autenticação 5x em 5min | CRÍTICO | Thiago (possível ataque) |

---

## 14. Performance e custos

### 14.1 Estimativa realista mensal

**Fase 1 (Roberts + DockPlus AI, MVP)**

| Item | Volume | Custo |
|---|---|---|
| Claude Sonnet 4.6 (5 agents principais) | ~3M in / 1M out | $30 |
| Claude Opus 4.7 (CEO weekly) | ~80k tokens | $8 |
| Claude Haiku 4.5 (triage, subagents simples) | ~2M tokens | $4 |
| OpenAI embeddings | 1M tokens | $0.02 |
| Tavily | já contratado | — |
| Perplexity | já contratado | — |
| Replicate (imagens Marketing) | ~150 imagens | $20 |
| LangSmith (tier free <5k traces) | <5k traces | $0 |
| **Subtotal Fase 1** | | **$62** |

**Fase 2 (+ Prospecting + 2 negócios)**

| Item | Volume | Custo |
|---|---|---|
| Tudo da Fase 1 (volume aumenta) | | $90 |
| **Clay.com** OU Apollo+Hunter | | $149-199 |
| Google Maps API | <50k requests | $0 (free tier) |
| Apify (Zillow) | tier starter | $49 |
| Vibe Prospecting | já contratado | — |
| LangSmith Plus (>5k traces) | | $39 |
| 3 mailboxes Google Workspace | DockPlus | $30 |
| Domain prospecção | $15/ano | $1 |
| **Subtotal Fase 2** | | **$358-408** |

**Fase 3 (todos os 7 negócios)**

| Item | Adicional |
|---|---|
| Mais agents rodando, mais profiles | +$50-80 |
| Mais Replicate/imagens | +$30 |
| **Total Fase 3** | **~$450-520/mês** |

### 14.2 SLA por agent

| Agent | Target P90 |
|---|---|
| Triage | <500ms |
| SDR full pipeline | <10s |
| Marketing (gera post completo) | <90s |
| CFO weekly run | <60s (async) |
| CMO weekly run | <60s (async) |
| CEO briefing | <120s (async) |
| Operations | <5s |
| Prospecting list build (200 leads) | <300s (async) |

### 14.3 Kill switch e cost control

- **Diário >$15**: alerta INFO Thiago
- **Diário >$30**: kill switch automático (cron jobs pausam, webhook ainda recebe mas não dispara LLM)
- **Mensal >$500**: kill switch hard (apenas Thiago via SSH reativa)

---

## 15. Resiliência e recuperação

### 15.1 Cenários de falha e respostas

| Falha | Comportamento | Recuperação |
|---|---|---|
| Anthropic API 429 | Circuit breaker abre 60s, fallback OpenAI | Auto, ao terminar 60s |
| Anthropic API 5xx | Retry exponencial 3x, depois OpenAI | Auto |
| Redis down | LangGraph perde checkpoint, sessões resetam | Auto restart Docker, dados em Supabase |
| Supabase down | Mensagens entram em queue local (SQLite fallback) | Manual flush quando voltar |
| GHL webhook silencia | Polling fallback a cada 5min | Auto |
| Postforme API quebra | Marketing Agent pausa publishing, alerta Thiago | Manual (Postforme alternativa) |
| Container crash | Docker restart unless-stopped | Auto <30s |
| VPS down (Hostinger) | DNS ainda resolve, tudo offline | Manual restart Hostinger |

### 15.2 Backup

- **Supabase**: pg_dump diário 3h UTC → Hostinger Object Storage
- **Retenção**: 30 dias rolling
- **Verificação**: weekly restore test em DB staging
- **Profiles JSON**: versionado em git (zero risco)

### 15.3 Rollback

```bash
# Em <5min
ssh thiago@vps "cd /opt/maestro && \
  git checkout <previous_tag> && \
  docker compose up -d --build"
```

### 15.4 Disaster recovery

- VPS perde tudo → restore Supabase backup + git clone + redeploy
- RTO (Recovery Time Objective): 2h
- RPO (Recovery Point Objective): 24h

---

## 16. Riscos e mitigações

| # | Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|---|
| R1 | LangGraph breaking change | Média | Alto | Pin versão, upgrade trimestral controlado |
| R2 | Anthropic muda pricing 2x | Baixa | Alto | Multi-model ready (OpenAI fallback) |
| R3 | Postforme tira API | Média | Médio | Plan B: Meta Graph API direto |
| R4 | Custo explode primeiro mês | Alta | Médio | Kill switch obrigatório, alertas |
| R5 | Agent toma decisão errada cara | Média | Alto | Threshold $500 + always-human |
| R6 | Spam complaint derruba domínio | Média | Crítico | Domain separado, monitoring 4h |
| R7 | Gustavo indisponível | Média | Alto | Documentação contínua, Thiago capaz de debug |
| R8 | LLM regrida silenciosamente | Alta | Médio | Evals semanais automáticos |
| R9 | Dados de cliente vazam | Baixa | Crítico | RLS, audit log, no-PII-in-logs |
| R10 | Lead premium perdido em horário de sono | Alta | Médio | Auto-resposta neutra <10min, aprovação manhã seguinte |
| R11 | DockPlus AI prospecting flagged spam | Alta | Alto | Domain warmup 6 semanas + volume baixo inicial |
| R12 | Hallucination em info financeira CFO | Média | Alto | CFO sempre cita fonte (transação Stripe ID), Thiago cross-check primeira semana |

---

## 17. ADRs — decisões arquiteturais

### ADR-001: LangGraph em vez de OpenAI Agents SDK
**Decisão:** usar LangGraph como orquestrador.
**Razão:** state machine + checkpointing nativo, ecossistema com LangChain/LangSmith, comunidade enterprise.
**Trade-off:** mais verbose que OpenAI Agents SDK, mas mais explícito e debugável.

### ADR-002: Sem n8n / Make / Zapier
**Decisão:** todas integrações via Python direto.
**Razão:** debug, versionamento, performance, controle.
**Trade-off:** mais código inicial, mas economia de licenças e menos pontos de falha.

### ADR-003: Sem OpenClaw na Fase 1
**Decisão:** Telegram bot único, sem OpenClaw multi-canal.
**Razão:** Thiago já vive em Telegram, OpenClaw adiciona complexidade prematura, projeto jovem com risco segurança.
**Reavaliar:** Fase 4+, se Cheesebread/Cape Codder demandar WhatsApp.

### ADR-004: Sem Hermes self-hosted na Fase 1
**Decisão:** Claude/OpenAI via API, sem GPU.
**Razão:** VPS sem GPU, custo Claude API <$200/mês é aceitável.
**Reavaliar:** Fase 5+, se volume justificar GPU dedicada.

### ADR-005: Function-first agents
**Decisão:** agents por função (SDR, Marketing, CFO), não por business.
**Razão:** evita 7×N agents duplicados, escala via profiles.
**Trade-off:** profile JSON precisa ser bem desenhado.

### ADR-006: Clay.com OU Apollo+Hunter (decisão pendente)
**Decisão:** começar Fase 2 com Apollo+Hunter (já temos MCP Apollo). Migrar pra Clay se waterfall manual virar problema.
**Razão:** Clay é estado da arte mas $149/mês mínimo. Apollo+Hunter custa $108/mês e cobre 80% dos casos.

### ADR-007: Supabase para memória longa
**Decisão:** Postgres + pgvector em vez de Pinecone/Qdrant.
**Razão:** já contratado, pgvector resolve, simplicidade operacional.

### ADR-008: Threshold humano $500
**Decisão:** ações >$500 sempre requerem aprovação Thiago.
**Razão:** balanceia autonomia e risco. Ajustável por agent/profile.

### ADR-009: Domain de prospecção separado
**Decisão:** `try-dockplusai.com` separado de `dockplus.com`.
**Razão:** spam complaints destruiriam domínio principal, irreversível.

### ADR-010: Trio Stack pra desenvolvimento
**Decisão:** Claude Code (docs) + Cursor (src) + Codex CLI (scripts).
**Razão:** alinhado com workflow já validado de Thiago.

---

## 18. Glossário

- **MAESTRO**: nome do sistema orquestrador.
- **Agent**: nó LangGraph com role + tools + decisão.
- **Subagent**: agent menor invocado por um principal.
- **Profile**: JSON com tom, ofertas e regras de um negócio.
- **Tool**: função Python decorada como LangChain tool.
- **Triage**: nó inicial que classifica intent.
- **Handoff**: transferência entre agents.
- **Trace**: registro completo execução em LangSmith.
- **HITL**: Human-In-The-Loop, pausa pra aprovação Thiago.
- **Cadence**: sequência de toques outbound (prospecting).
- **ICP**: Ideal Customer Profile.
- **Brand Guardian**: subagent transversal que valida output público.

---

**Fim do SDD v2.0**

> *Sistema desenhado pra ser implementável, não pra impressionar. Soli Deo Gloria.*
