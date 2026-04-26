# PRD — MAESTRO v2.0

**Product Requirements Document**
**Versão:** 2.0 (definitiva)
**Owner:** Thiago do Carmo — DockPlus AI
**Data:** 25 de abril de 2026
**Documento irmão:** [SDD.md](./SDD.md)

> Documento construído sem fake news, sem promessas falsas, sem enrolação.
> Tudo que está aqui é mensurável, implementável, e foi auditado.

---

## Sumário

1. [Resumo executivo](#1-resumo-executivo)
2. [Contexto e problema](#2-contexto-e-problema)
3. [Objetivos e métricas](#3-objetivos-e-métricas-de-sucesso)
4. [Personas e usuários](#4-personas-e-usuários)
5. [Requisitos funcionais](#5-requisitos-funcionais)
6. [Requisitos não-funcionais](#6-requisitos-não-funcionais)
7. [User stories e critérios de aceite](#7-user-stories-e-critérios-de-aceite)
8. [Roadmap em 3 fases](#8-roadmap-em-3-fases)
9. [Pré-requisitos absolutos](#9-pré-requisitos-absolutos)
10. [Plano de testes](#10-plano-de-testes)
11. [Lançamento gradual](#11-lançamento-gradual)
12. [Pós-lançamento](#12-pós-lançamento)
13. [Decisões e trade-offs](#13-decisões-e-trade-offs-explícitos)
14. [Aprovação](#14-aprovação)

---

## 1. Resumo executivo

MAESTRO automatiza **85-90% das tarefas operacionais repetitivas** de Roberts Landscape e DockPlus AI usando 7 agents principais (Triage, SDR, Marketing, CFO, CMO, CEO, Operations) na Fase 1, expandindo para 10 agents e 7 negócios nas Fases 2-3.

### Mandato principal do MAESTRO

O papel mais importante do MAESTRO não é "responder mensagens". É **crescer as empresas**.

MAESTRO deve operar como uma camada executiva de crescimento, com prioridade explícita em:

1. **Prospecting** — encontrar oportunidades novas, qualificar leads, abrir conversas e gerar reuniões.
2. **Marketing** — criar conteúdo consistente, testar ângulos, aumentar alcance e melhorar percepção de marca.
3. **Criação** — produzir assets, campanhas, drafts, relatórios e ideias úteis em velocidade maior que o time humano sozinho.
4. **Produtividade** — reduzir trabalho operacional repetitivo, encurtar ciclos e remover gargalos de decisão.
5. **Inteligência operacional** — transformar dados soltos em decisões claras, rápidas e auditáveis.
6. **Lucratividade** — priorizar ações que aumentam receita, margem, conversão, retenção ou reduzem custo/desperdício.

Toda feature deve responder a pelo menos uma pergunta:

- Isso ajuda a empresa ficar **maior**?
- Isso ajuda a empresa ficar **mais inteligente**?
- Isso ajuda a empresa ficar **mais rápida**?
- Isso ajuda a empresa ficar **mais produtiva**?
- Isso ajuda a empresa ficar **mais lucrativa**?

Se a resposta for "não" para todas, a feature não entra no roadmap.

### Resultados esperados (mensuráveis)

- **Tempo de resposta a leads:** de 2-6h (atual) para <10min, 24/7
- **Posts Instagram/semana por negócio:** de 1-2 para 5-7
- **Visibilidade financeira:** de planilha mensal manual para CFO Agent semanal automático
- **ROAS de ads:** +20-30% em 90 dias (via CMO Agent re-allocation)
- **Tempo Thiago em ops:** redução de 15-20h/semana
- **Receita prospecting B2B (DockPlus AI):** 4-15 reuniões qualificadas/mês via outbound (Fase 2)
- **Margem operacional:** identificar semanalmente oportunidades de aumento de margem ou redução de desperdício

### Investimento total

- **Tempo dev:** Gustavo 20h/semana × 24 semanas (480h) + Thiago 6h/semana × 24 semanas (144h) = **624h dev**
- **Custo APIs Fase 1 (8 semanas):** ~$60-80/mês
- **Custo APIs Fase 2 (semanas 9-16):** ~$350-410/mês
- **Custo APIs Fase 3 (semanas 17-24):** ~$450-520/mês
- **VPS, Supabase, GHL, Postforme:** já contratados

### ROI realista

Se Roberts converter **1 job a mais de $20k/mês** (atribuível a resposta rápida): pago todo o investimento de APIs do ano em 1 mês.

Se DockPlus AI conseguir **2 reuniões a mais/mês** via prospecting (Fase 2): valor bruto ~$10-30k novo MRR potencial/mês.

**Soli Deo Gloria.**

---

## 2. Contexto e problema

### 2.1 Estado atual (abril 2026)

Thiago opera 7 negócios em paralelo. Foco deste PRD: **Roberts Landscape** (B2C local, ticket alto) e **DockPlus AI** (B2B, escalável globalmente).

#### Roberts Landscape — números reais

- 30-50 leads/mês via Meta Ads + Google LSA + indicações
- Ticket médio: $15-25k
- Conversão atual: ~15-20%
- Resposta média a lead: 2-6h (perda comprovada de leads em horários fora comerciais)
- Posts Instagram: 1-2/semana inconsistentes
- Stack: GHL CRM, Meta Ads, Google LSA, Postforme, Calendar

#### DockPlus AI — números reais

- Capacidade demos atual: 10-20/mês (Joana + Thiago)
- Ticket médio: $5-15k retainer ou $20-50k projeto
- Conversão demo→cliente: ~25-35%
- Outbound atual: zero estruturado (depende de indicação)
- Joana faz parte do trabalho via Paperclip AI
- Stack: GHL CRM, Paperclip, Google Workspace

### 2.2 Dores concretas

#### Dores Roberts

1. **Lead noturno/fim-de-semana perdido** — ~20-30% dos leads chegam fora comercial. Resposta em <10min é diferenciador.
2. **Tempo Thiago em ops** — 15-20h/semana em tarefas que LLM faz bem.
3. **Conteúdo IG inconsistente** — semanas sem post, depois rajada. Algoritmo IG pune.
4. **Visibilidade financeira pobre** — Thiago não sabe margem real por job em tempo hábil.
5. **Ads sem otimização proativa** — CPC sobe, criativo fadiga, ninguém percebe até relatório mensal.

#### Dores DockPlus AI

1. **Joana sobrecarregada** — Paperclip ajuda, mas SDR humano não escala.
2. **Outbound zero** — só inbound. Crescimento limitado a marketing orgânico.
3. **Mesmo conteúdo IG inconsistente** — pior porque B2B exige consistência maior.
4. **Sem data financeira clara** — clientes pagam mensalidade, mas Thiago não sabe LTV/churn em tempo real.

### 2.3 Por que agora (abril 2026)

- **Modelos LLM 2026** (Claude Sonnet 4.6, Opus 4.7) tem confiabilidade pra produção real
- **LangGraph 0.2.50+** estabilizou — checkpointing nativo, interrupt() pra HITL
- **Custo de tokens** caiu ~80% nos últimos 18 meses
- **Stack já existe** — VPS, Supabase, GHL, Postforme. Falta orquestrador.
- **Clay.com / Apollo MCP / Vibe Prospecting** — ferramentas B2B maduras pra Fase 2
- **Concorrência ganhou tempo** — early adopters de agents já têm 6-12 meses de vantagem

### 2.4 O que não vai funcionar (verdades amargas)

Pra evitar frustração, lista do que **não vai dar certo** mesmo com MAESTRO:

- ❌ Substituir reunião de descoberta DockPlus AI (Thiago vende)
- ❌ Estimar orçamento técnico Roberts sem visita (granito, drainage variam)
- ❌ Resolver cliente Roberts insatisfeito por telefone (humano)
- ❌ Decidir abrir 8º negócio (estratégia humana)
- ❌ Substituir Bruna em visitas técnicas (físico)
- ❌ Garantir conversão de lead (mercado decide)
- ❌ Atingir 100% automação — fantasia

---

## 3. Objetivos e métricas de sucesso

### 3.1 Objetivos primários (Fase 1)

| # | Objetivo | Métrica | Meta 90 dias | Como medir |
|---|---|---|---|---|
| O1 | Reduzir tempo lead → primeira resposta | Mediana minutos | <10 min | log GHL + agent_runs |
| O2 | Aumentar posts IG/semana | Posts publicados | 5-7/semana por negócio ativo | Postforme analytics |
| O3 | Visibilidade financeira semanal | Briefing CFO entregue | 100% das segundas | business_metrics table |
| O4 | Liberar tempo Thiago | Horas/semana ops manual | -15 a -20h | self-report semanal |
| O5 | Não tomar decisão cara errada | Ações >$500 sem aprovação | 0 | audit_log |
| O6 | Auditável | % ações com trace | 100% | LangSmith |
| O7 | Custo controlado | $/mês | <$200 Fase 1 | daily_costs |

### 3.2 Objetivos primários (Fase 2)

| # | Objetivo | Métrica | Meta | Como medir |
|---|---|---|---|---|
| O8 | DockPlus AI: gerar pipeline outbound | Reuniões agendadas/mês | 4-15 | GHL pipeline + cadence_state |
| O9 | DockPlus AI: deliverability sustentada | Bounce rate | <2% | deliverability_metrics |
| O10 | DockPlus AI: zero spam complaint | Complaints | 0 críticos | Postmaster API |
| O11 | Customer Success funcionando | Reviews Google novos | +30% Roberts | GBP API |
| O12 | All Granite + Cape Codder ativos | Profiles em produção | 2 | profiles directory |

### 3.3 Objetivos primários (Fase 3)

| # | Objetivo | Métrica | Meta |
|---|---|---|---|
| O13 | Todos os 7 negócios ativos | Profiles em prod | 7 |
| O14 | Eval automatizado funcionando | Score weekly | >85% |
| O15 | Dual-run validado | Agent vs Bruna | 90%+ acordo |
| O16 | Release 100% | Leads autônomos | 100% (sem dual) |

### 3.4 Anti-objetivos (NÃO buscamos)

- ❌ Substituir time humano (complementar, não trocar)
- ❌ Multi-usuário (Thiago opera; equipe lê outputs)
- ❌ Automação 100% (fantasia)
- ❌ Mais barato possível (qualidade > custo)
- ❌ Velocidade acima de tudo (qualidade > velocidade)

### 3.5 Indicadores de saúde (medidos sempre)

```
CARDÁPIO DE MÉTRICAS — verificar semanalmente
─────────────────────────────────────────────────
SAÚDE TÉCNICA
  ▸ Latência P90 por agent           target: <SLA
  ▸ Taxa de erro por tool            target: <2%
  ▸ Uptime                           target: >99.5%
  ▸ Custo dia                        target: <$15

QUALIDADE
  ▸ Score eval semanal               target: >85%
  ▸ % aprovação Thiago               target: >90%
  ▸ Correções/semana                 target: <5
  ▸ Reclamação de cliente            target: 0

NEGÓCIO
  ▸ Tempo médio resposta lead        target: <10min
  ▸ Taxa conversão (delta vs base)   target: ≥0%
  ▸ Posts publicados                 target: 5-7/sem
  ▸ Reuniões DockPlus (Fase 2)       target: 4-15/mês
```

---

## 4. Personas e usuários

### 4.1 Usuário primário: Thiago

**Perfil:**
- 38-45, fundador, multi-business
- Técnico (programa, sabe terminal, deploy, Docker)
- Brasileiro vivendo em Cape Cod há 20+ anos
- Bilíngue (português com Claude, inglês com clientes)
- Casado (Bruna Cruz), 3 filhos, ministro de adoração
- Vive no Telegram (>50 abertas/dia)

**Contexto de uso:**
- Mobile-first (Telegram phone)
- Decisões rápidas quando contexto está claro
- Detesta UI com 50 cliques
- Valoriza ownership, qualidade, fé
- Trabalha em mobilidade (Cape Cod ↔ Brasil)

**Como interage:**
- Manda mensagens curtas pelo Telegram
- Quer respostas resumidas, não dados crus
- Aprova decisões com 1 toque (inline keyboard)
- Pede relatórios profundos quando precisa decidir grande

### 4.2 Usuários indiretos (consomem outputs, Fase 2+)

| Pessoa | Negócio | Como usa MAESTRO |
|---|---|---|
| **Bruna** | Roberts (prospecting) | Recebe leads qualificados pra visitar |
| **Joana** | DockPlus AI (sales) | Recebe demos agendadas + briefing pré-call |
| **Gustavo** | Tech (Brasil) | Implementa, mantém, debugga |
| **Ana** | Office/finance | Recebe relatório CFO + reconciliações |
| **Luanny** | Marketing/conteúdo | Coordena com Marketing Agent, aprova drafts |

Na Fase 1, **só Thiago** opera. Outros recebem outputs via email/relatório, sem disparar agents.

---

## 5. Requisitos funcionais

### 5.1 Capacidades core — Fase 1

#### F1 — Triage
- Recebe toda mensagem do Thiago via Telegram
- Classifica em <500ms
- Despacha pro agent correto
- Pede esclarecimento se confidence <70%

#### F2 — SDR (inbound)
- Webhook GHL recebe lead novo
- Em <30s: lead criado em Supabase, qualificado, email draftado, slots calendar buscados
- Notifica Thiago via Telegram com inline keyboard
- Após aprovação: envia email, cria evento, move pipeline GHL
- Toda ação reversível por 5min

#### F3 — Marketing
- Aceita request livre ("post sobre patio granito Falmouth")
- Em <90s: gera 1-4 imagens + caption + hashtags
- Apresenta preview no Telegram
- Após aprovação: agenda no horário ótimo via Postforme
- Calendário editorial automático: 1 post/dia draft pra cada negócio ativo

#### F4 — CFO weekly
- Cron segunda 7h UTC
- Reconcilia Stripe + GHL
- Calcula margem por job/mês
- Projeta cashflow 30/60/90 dias
- Salva em business_metrics

#### F5 — CMO weekly
- Cron segunda 8h UTC
- Analisa Meta Ads + Google Ads + GBP
- Detecta fadiga creative (CTR -20% em 14 dias)
- Recomenda redistribuição budget
- Salva em business_metrics

#### F6 — CEO briefing
- Cron segunda 9h UTC
- Lê outputs CFO + CMO + ops da semana
- Sintetiza 1 página markdown
- Lista 3-5 decisões pendentes
- Envia via Telegram com inline keyboards

#### F7 — Operations
- Tarefas ad-hoc via Telegram
- Agendar, follow-up, mover pipeline
- Sempre pede confirmação antes de ação externa

### 5.2 Capacidades core — Fase 2

#### F8 — Prospecting (DockPlus AI)
- Cron daily 6h UTC: list_builder gera 50 leads novos
- Sender rate-limited: 30-50 emails/dia/mailbox, 3-5 mailboxes em rotação
- Reply classifier: webhook Gmail processa replies em <60s
- Deliverability monitor a cada 4h: pausa se thresholds violados
- Cadência: 3 toques email + LinkedIn flag em 21 dias
- Handoff automático pro SDR Agent quando reply é "interested"

#### F9 — Customer Success
- Trigger pós-job-won: 30 dias depois pede review
- Trigger churn risk DockPlus: alerta se cliente com baixa atividade
- Trigger upsell: identifica oportunidades cross/up-sell
- Trigger nova review Google: drafta resposta apropriada

#### F10 — Brand Guardian (transversal)
- Toda mensagem pra cliente externo passa por Brand Guardian antes
- Valida tom, palavras proibidas, alinhamento com profile
- Se rejeitado: agent retry. 2 falhas → escala Thiago.

### 5.3 Capacidades core — Fase 3

#### F11 — Competitive Intelligence
- Weekly: monitora competidores (preço, ofertas, novos serviços)
- Tavily + Perplexity + Maps reviews + Apify scraping
- Output: 3-5 trends + 3-5 changes detectados

#### F12 — Evals automáticos
- Sexta 22h UTC: roda eval suite contra dataset de produção
- Compara: accuracy, tone, action correctness
- Alerta se score regrediu >5%

### 5.4 Capacidades transversais (todas as fases)

#### F13 — Aprovação humana obrigatória
- Toda ação >$500 → pause + inline keyboard
- Todo email pra cliente novo → preview
- Todo post Instagram → preview
- Toda mudança de budget ads → aprovação

#### F14 — Memória persistente
- Conversas anteriores em Supabase
- Embeddings vetorizados pgvector
- Scoring híbrido: similaridade + recência + importância
- Comando `/lembrar isso` marca importance manual

#### F15 — Idempotência
- Toda webhook checa `processed_events`
- Re-execução é safe (zero efeito colateral duplicado)

#### F16 — Audit log imutável
- Toda decisão de agent + ação externa logada
- Append-only via trigger Postgres
- Hash chain (Merkle-style) detecta tampering

#### F17 — Feedback loop
- Toda mensagem do agent tem 👍/👎 inline
- 👎 abre modal pra correção textual
- Correções vão pra `corrections` table
- Quinzenal: Thiago revisa top 5 correções, atualiza prompts

#### F18 — Versionamento de prompts
- Prompts em `maestro/prompts/v{N}/`
- Toda mudança = nova versão, git tracked
- agent_runs registra `prompt_version` usado
- Rollback rápido se v_new regredir

#### F19 — Kill switch
- Custo dia >$15: alerta Thiago
- Custo dia >$30: pausa cron jobs (webhook ainda recebe)
- Custo mês >$500: pausa total, requer SSH manual

#### F20 — Emergency `/stop`
- Comando Telegram pausa todos agents instantâneo
- `/start` retoma operação
- Útil em reuniões, viagens, momentos sensíveis

### 5.5 Integrações externas obrigatórias

**Fase 1:**
- Telegram Bot API
- GoHighLevel (Roberts + DockPlus AI)
- Gmail (OAuth2)
- Google Calendar
- Postforme
- Meta Marketing API
- Google Ads API
- Stripe (read-only)
- Google Business Profile API
- Tavily, Perplexity, Replicate
- Anthropic API, OpenAI API (fallback)
- LangSmith

**Fase 2 (adicionais):**
- Clay.com OU Apollo + Hunter.io
- Google Maps Places API
- Apify (Zillow scraper)
- Vibe Prospecting (já tem MCP)
- Google Workspace (mailboxes prospecção)

---

## 6. Requisitos não-funcionais

### 6.1 Performance

| Métrica | Target P90 |
|---|---|
| Latência Triage | <500ms |
| Latência SDR full pipeline | <10s |
| Latência Marketing post complete | <90s |
| Throughput webhooks | ≥10 req/s sustained |
| Throughput cron prospecting | 50 leads em <300s |

### 6.2 Disponibilidade

- Uptime: ≥99.5% (3.6h downtime/mês aceitável)
- RTO: 2h (recovery após disaster)
- RPO: 24h (backup diário)
- Health check: `/health` público
- Auto-restart Docker em crash

### 6.3 Segurança

- TLS 1.3 obrigatório
- Webhook validation: secret_token + HMAC
- Whitelist chat_id (só Thiago)
- Stripe read-only Fase 1
- PII redacted em logs
- Audit log imutável
- Secrets nunca commitados

### 6.4 Custo

- Fase 1: <$200/mês
- Fase 2: <$500/mês
- Fase 3: <$700/mês
- Kill switch obrigatório dia 1

### 6.5 Manutenibilidade

- Cobertura testes ≥70%
- Code review antes merge main
- ADRs documentados
- Runbook incidentes
- Documentação contínua (Gustavo)

### 6.6 Escalabilidade

- Adicionar profile = 1 arquivo JSON + ~3 dias dev
- Adicionar agent = ~1 semana dev
- Adicionar tool = 1-2 dias dev

### 6.7 Observabilidade

- Toda invocação em LangSmith
- Logs JSON estruturado
- Métricas custo + latência + erro expostas
- Alertas Telegram pra eventos críticos

### 6.8 Compliance

- CAN-SPAM (US): unsubscribe + endereço físico em todo email
- LGPD (BR): consentimento explícito antes cold email BR
- GDPR-ready: RLS Supabase + delete-my-data process
- Brand: Brand Guardian valida tudo público

---

## 7. User stories e critérios de aceite

### US-1: Lead noturno via Meta Ads (Fase 1)

> **Como** Thiago, **quando** um lead novo entra no GHL Roberts às 23h via Meta Ads,
> **quero** que o MAESTRO qualifique, drafte email e sugira horários,
> **para que** eu só precise aprovar de manhã sem perder o lead pra concorrente.

**Critérios de aceite:**
- ✅ Em <30s do webhook GHL, Thiago recebe Telegram com:
  - Resumo do lead (nome, fonte, área, ticket estimado)
  - Score de qualificação 0-100 + justificativa em 2 linhas
  - Email draftado completo (subject + body)
  - 3 horários sugeridos
  - Botões: "Aprovar tudo", "Editar email", "Editar horários", "Rejeitar"
- ✅ Se Thiago não responder em 8h, agent envia email "auto-reply neutro" (template):
  > "Olá [nome], recebemos sua mensagem e Thiago vai entrar em contato em breve. Em caso de urgência, ligue (508) 464-4878. — Roberts Landscape"
- ✅ Esse auto-reply é **diferente** do email customizado e é flagged como "automatic" no GHL
- ✅ Thiago aprova de manhã → email customizado vai, calendar criado, GHL movido

### US-2: Post Instagram on-demand (Fase 1)

> **Como** Thiago, **em qualquer momento do dia**,
> **quero** pedir um post sobre tema específico ("patio de granito Falmouth"),
> **para receber** preview pronto em <90s e publicar com 1 toque.

**Critérios de aceite:**
- ✅ Marketing Agent recebe request
- ✅ Em <90s gera:
  - 1-4 imagens (Replicate FLUX)
  - Caption (200-2200 chars)
  - 8-12 hashtags
  - Sugestão de horário
- ✅ Preview no Telegram com botões "Publicar agora", "Agendar pra horário X", "Refazer caption", "Refazer imagens", "Cancelar"
- ✅ Após aprovação, publicação confirmada em <30s
- ✅ Brand Guardian validou tom antes de apresentar (Fase 2)

### US-3: Briefing semanal segunda 9h (Fase 1)

> **Como** Thiago, **toda segunda às 9h**,
> **quero receber** 1 mensagem clara com estado do Roberts,
> **para entrar** na semana sabendo o que importa.

**Critérios de aceite:**
- ✅ Mensagem Telegram às 9h ± 5min UTC
- ✅ Estrutura (5-8 parágrafos):
  - **Resumo** (3 bullets)
  - **Receita semana** vs anterior
  - **Pipeline** (leads, qualified, won, value)
  - **Marketing** (posts, ROAS, top creative, fadiga detectada)
  - **3 wins** da semana
  - **3 alertas/preocupações**
- ✅ 3-5 decisões pendentes com inline keyboards
- ✅ Botões "Discutir", "Postpone 1 semana", "Aprovar", "Rejeitar"

### US-4: Pergunta financeira ad-hoc (Fase 1)

> **Como** Thiago, **em qualquer momento**,
> **quero perguntar** "qual minha margem do mês passado?"
> **e receber** resposta precisa em <10s.

**Critérios de aceite:**
- ✅ CFO Agent ativado via Triage
- ✅ Consulta Supabase + Stripe se necessário
- ✅ Resposta em <10s com:
  - Valor calculado
  - Comparação mês anterior
  - 1 frase de contexto
- ✅ Pergunta de follow-up sugerida ("quer ver detalhamento por categoria?")

### US-5: Lead aprovado vira ação real (Fase 1)

> **Como** Thiago, **depois que aprovo um lead via botão**,
> **quero** que o sistema execute todas as ações automaticamente,
> **sem** eu precisar fazer mais nada.

**Critérios de aceite:**
- ✅ Email enviado via Gmail
- ✅ Evento criado no Calendar (com link Google Meet se for DockPlus AI)
- ✅ Lead movido no pipeline GHL: "new" → "contacted" → "qualified"
- ✅ Confirmação Telegram em <15s: "✅ Email enviado pra Sarah, reunião agendada quinta 14h, GHL atualizado"
- ✅ Zero erro silencioso (qualquer falha notifica Thiago)
- ✅ Audit log registra cada ação

### US-6: Prospecting B2B sustentável (Fase 2)

> **Como** Thiago, **toda semana**,
> **quero** receber 4-15 reuniões qualificadas via outbound DockPlus AI,
> **sem** queimar minha reputação de domínio nem violar leis CAN-SPAM/LGPD.

**Critérios de aceite:**
- ✅ Daily: 50 leads novos no funil
- ✅ Personalização real (não `{firstname}`)
- ✅ Bounce rate <2%, spam complaints = 0
- ✅ Reply rate ≥3% sustentado
- ✅ 4-15 meetings/mês booked no calendário
- ✅ Toda reply passa por reply_classifier
- ✅ Replies "interested" viram leads no SDR Agent (handoff)
- ✅ Domain `try-dockplusai.com` warmed e sem flag

### US-7: Customer Success automático (Fase 2)

> **Como** Thiago, **30 dias após Roberts terminar um job**,
> **quero** que cliente receba automaticamente pedido de review,
> **para** crescer reputação Google sem trabalho manual.

**Critérios de aceite:**
- ✅ GHL opportunity → "won" + 30 dias = trigger
- ✅ Email customizado por cliente (nome do projeto, foto se houver)
- ✅ Aprovação Thiago antes envio
- ✅ Pós envio, monitora se review apareceu no GBP
- ✅ Se review negativa: alerta crítico Thiago + drafta resposta
- ✅ Métrica: +30% reviews/mês após 90 dias

### US-8: Modo silêncio (Fase 1)

> **Como** Thiago, **antes de uma reunião importante com cliente DockPlus AI**,
> **quero** mandar `/stop` e ter certeza que nenhum agent vai mandar email/post no momento errado,
> **para evitar** constrangimento ou má impressão.

**Critérios de aceite:**
- ✅ `/stop` no Telegram pausa todos agents em <2s
- ✅ Webhooks ainda recebem (não perdem dados)
- ✅ Crons pulam execução
- ✅ Confirmação visual no Telegram
- ✅ `/start` retoma todas operações
- ✅ Log audit registra pause/resume

---

## 8. Roadmap em 3 fases

### FASE 1 — MVP Roberts + DockPlus AI (semanas 1-8)

**Objetivo:** sistema rodando 7 agents principais, 2 negócios, validado com leads reais.

**Regra de qualidade 10/10:** antes de construir "todos os agents", provar um fluxo vertical completo. Um lead falso precisa entrar por webhook, passar por idempotência, gerar card Telegram, receber aprovação, registrar audit log e executar apenas ação dry-run. Só depois disso o projeto expande para agents completos.

```
SEMANA 0 — Pré-requisitos absolutos
─────────────────────────────────────────────────
Smoke test todas APIs (1 dia)
Profiles roberts.json + dockplusai.json preenchidos com dados reais
Contratos das APIs externas congelados (auth, scopes, endpoints, rate limits, fallback)
Definition of Done da Fase 1 aprovada
Domain maestro.dockplus.app DNS configurado
VPS preparado (Docker, Traefik, certificados)
Telegram bot criado, secret configurado
LangSmith projeto criado
Supabase tabelas criadas via seed_supabase.sql
Backup automatizado funcionando
.env preenchido completo

SEMANA 0.5 — True MVP / vertical slice
─────────────────────────────────────────────────
FastAPI /health funcionando local
Telegram bot recebe comando de Thiago e rejeita chat_id não autorizado
Supabase schema core criado: processed_events, audit_log, leads, agent_runs
Webhook fake GHL recebe lead e valida idempotência
Triage stub classifica lead como SDR
Telegram approval card enviado com botões inline
Clique de aprovação grava audit_log e processed_events
Dry-run action executada (sem email real, sem calendar real, sem GHL real)
LangSmith trace criado para o fluxo completo

CRITÉRIO SAÍDA: fake lead → approval card → approve → audit log → dry-run
em menos de 30s, repetição do webhook não duplica nada.

SEMANA 1 — Setup base
─────────────────────────────────────────────────
config.py, logging, security utilities
FastAPI scaffold, /health funcionando
LangGraph scaffold com Triage stub
Memory layer (Redis + Supabase wrappers)
CI/CD GitHub Actions deploy automático
Comando /stop emergency funcionando

SEMANA 2-3 — SDR Agent (a base do MVP)
─────────────────────────────────────────────────
Tools: ghl.py, gmail.py, calendar.py, telegram.py
Subagents: lead_qualifier, email_drafter, meeting_scheduler
SDR Agent integrado no graph
Webhook GHL handler com idempotency + HMAC
HITL via interrupt() + inline keyboards
Audit log + processed_events implementados
Tests unitários ≥70% cobertura

CRITÉRIO SAÍDA: lead falso entra GHL → em <30s Thiago recebe Telegram
com email draftado, aprova com 1 toque, email vai e calendar criado.

SEMANA 4 — Marketing Agent
─────────────────────────────────────────────────
Tools: postforme.py, replicate.py, tavily.py
Subagents: content_creator, caption_writer, hashtag_strategist, posting_scheduler
Marketing Agent integrado
Skill carousel-autoposter integrada (reuso)

CRITÉRIO SAÍDA: Thiago manda "post sobre patio granito" → 90s depois
preview Telegram → aprova → publica IG Roberts.

SEMANA 5 — CFO + CMO
─────────────────────────────────────────────────
Tools: stripe.py, meta_ads.py, google_ads.py, gbp.py
Subagents CFO + CMO + agents
Schedulers: weekly cron segunda 7h e 8h
Outputs em business_metrics

CRITÉRIO SAÍDA: segunda-feira teste, 2 relatórios JSON gerados
com dados reais.

SEMANA 6 — CEO + Operations
─────────────────────────────────────────────────
Subagents CEO (weekly_briefing, decision_preparer)
CEO Agent com Claude Opus 4.7
Operations Agent + 3 subagents
Cron segunda 9h dispara CEO
Inline keyboards de decisões

CRITÉRIO SAÍDA: segunda 9h Thiago recebe briefing executivo,
decisão por toque funciona.

SEMANA 7-8 — Hardening
─────────────────────────────────────────────────
Tests E2E completos
Performance tuning baseado em LangSmith traces
Recovery scenarios documentados e testados
Backup verificado (restore test)
Alertas custo + erro funcionando
Runbook completo
Soak test: 7 dias rodando com leads reais
Cost monitor verificado por 7 dias

CRITÉRIO SAÍDA FASE 1: 7 dias consecutivos sem intervenção,
métricas O1-O7 batendo, custos <$200/mês.
```

### Definition of Done — Fase 1

Fase 1 só pode ser considerada concluída quando todos os itens abaixo estiverem verdes:

- Deploy em VPS funcionando atrás de TLS.
- `/health` público responde OK.
- Telegram `/stop` pausa agents e `/start` retoma.
- Webhooks Telegram e GHL validam segredo/HMAC.
- Duplicate webhook não gera lead, email, evento ou log duplicado.
- Todo output externo relevante passa por aprovação humana.
- Toda decisão gera `agent_runs` + `audit_log`.
- LangSmith mostra traces com tags `business`, `agent`, `prompt_version`.
- Cost monitor alertou corretamente em teste simulado.
- Backup Supabase restaurado em staging pelo menos 1 vez.
- Testes unitários ≥70% nas áreas críticas.
- Testes E2E cobrem lead inbound, approval loop, `/stop`, idempotência e auth failure.
- Runbook de incidente e rollback existe.
- 7 dias de soak test sem incidente crítico.

### Testes críticos obrigatórios

Esses casos entram no plano antes de produção:

- GHL webhook duplicado não cria duplicidade.
- Telegram chat_id não autorizado é rejeitado.
- Lead sem telefone ou sem email ainda recebe tratamento controlado.
- Botão de aprovação clicado duas vezes executa uma vez só.
- `/stop` impede LLM/tool execution.
- Custo diário acima do limite pausa cron jobs.
- Falha de autenticação em webhook gera alerta.
- API externa fora do ar aciona retry/circuit breaker/fallback conforme contrato.

### FASE 2 — Prospecting + extras + 2 negócios (semanas 9-16)

```
SEMANA 9-10 — Setup deliverability prospecting
─────────────────────────────────────────────────
Domain try-dockplusai.com comprado
SPF/DKIM/DMARC configurados
3-5 mailboxes Google Workspace criados
Domain warming inicia (4-6 semanas processo)
Tools: clay.py OU apollo.py + hunter.py, maps.py, zillow_apify.py, vibe_prospecting.py
Tests de cada tool isolado

SEMANA 11-12 — Prospecting Agent build
─────────────────────────────────────────────────
Subagents: icp_definer, list_builder, enricher, personalizer
Cadence orchestrator (state machine LangGraph)
Reply classifier
Deliverability monitor
Webhook Gmail pra replies
ICP DockPlus AI validado por Thiago manual

SEMANA 13 — Customer Success + Brand Guardian
─────────────────────────────────────────────────
Customer Success Agent + 4 subagents
Brand Guardian transversal implementado
Profiles all_granite.json + cape_codder.json
Tests integration

SEMANA 14 — Validação ICP + dry run prospecting
─────────────────────────────────────────────────
20 leads gerados manualmente, Thiago revisa
Domain warming continua
Dry run: 10 emails personalizados, Thiago aprova cada um manual
Nenhum email "automático" ainda

SEMANA 15 — Soft launch prospecting (volume baixo)
─────────────────────────────────────────────────
30-50 emails/dia, 1 mailbox apenas
Aprovação Thiago batch (manhã + tarde)
Deliverability monitor agressivo
Zero spam complaint = critério crítico

SEMANA 16 — Scale prospecting + extras
─────────────────────────────────────────────────
3-5 mailboxes em rotação
Volume 100-150 emails/dia total
Reactivation Subagent (sob SDR)
Métricas semana batendo (reply rate ≥3%, bounce <2%)

CRITÉRIO SAÍDA FASE 2:
- Domain saudável, métricas dentro do alvo
- 2-5 reuniões DockPlus AI booked via outbound em 30 dias
- All Granite e Cape Codder ativos com Marketing Agent
- Brand Guardian validando tudo público
- Custo <$500/mês
```

### FASE 3 — Completude + qualidade extrema (semanas 17-24)

```
SEMANA 17-18 — Mais negócios + Competitive Intel
─────────────────────────────────────────────────
Profiles Cheesebread, Bread & Roses, Flamma Verbi
Competitive Intelligence Agent + 3 subagents
Cron weekly competitive monitoring
Profiles testados isoladamente

SEMANA 19-20 — Evals automatizados + dual-run prep
─────────────────────────────────────────────────
Datasets de eval criados (30-50 casos por agent)
Eval runner automático sexta 22h
Comparação modelos (4.6 vs 4.5 vs novo modelo)
Sistema feedback 👍/👎 ativo
Versionamento prompts implementado

SEMANA 21-22 — Dual-run com Bruna/Joana
─────────────────────────────────────────────────
Para cada lead Roberts: agent processa + Bruna processa
Comparação outputs daily
Identificar divergências (target: <10% após 14 dias)
Idem DockPlus AI com Joana
Refinement de prompts baseado em divergências

SEMANA 23 — Release gradual
─────────────────────────────────────────────────
Day 1: 25% leads autônomo
Day 4: 50% se métricas OK
Day 7: 75% se métricas OK
Day 10: 100% autônomo

SEMANA 24 — Operação plena + retrospectiva
─────────────────────────────────────────────────
Sistema 100% autônomo (com kill switches armados)
Métricas O1-O16 medidas e comparadas com baseline
Retrospectiva 24 semanas
Backlog Fase 4 (se aplicável)

CRITÉRIO SAÍDA FASE 3:
- 7 negócios ativos
- Eval score ≥85%
- Dual-run validou >90% acordo
- Release 100% sem incidentes em 14 dias
- Custo <$700/mês
- Thiago confirmou economia ≥15h/semana
```

---

## 9. Pré-requisitos absolutos

**Antes de começar Sprint 1, todos esses itens precisam estar verdes.** Sem isso, projeto NÃO inicia.

```
INFRAESTRUTURA
[ ] VPS Hostinger ≥4GB RAM, ≥40GB disk, Ubuntu 22+
[ ] Docker + docker-compose instalados e testados
[ ] Domain maestro.dockplus.app DNS apontando pro VPS
[ ] Certificate Let's Encrypt funcionando
[ ] SSH access Thiago + Gustavo
[ ] Backup automatizado VPS configurado

APIs EXTERNAS — smoke test (1 dia full)
[ ] Anthropic API: chave funciona, Tier 4 confirmado
[ ] OpenAI API: chave funciona (fallback)
[ ] LangSmith: projeto criado, primeiro trace de teste
[ ] GHL Roberts: token + webhook secret + 1 evento de teste recebido
[ ] GHL DockPlus AI: idem
[ ] Gmail OAuth: refresh token funciona, send + read testados
[ ] Google Calendar: find slots + create event testados
[ ] Postforme: API key + 1 publicação teste
[ ] Meta Marketing API: developer token + insights testados
[ ] Google Ads API: developer token APROVADO (pode levar semanas — check ASAP)
[ ] Stripe: chave test funciona
[ ] Tavily: query teste
[ ] Perplexity: query teste
[ ] Replicate: 1 imagem gerada teste
[ ] Telegram bot: webhook configurado, secret_token validado
[ ] Supabase: connection + RLS configurado

DADOS REAIS — preenchimento profiles
[ ] roberts.json com tickets reais (analisar últimos 20 jobs)
[ ] dockplusai.json com ICP validado
[ ] Tom de voz documentado (5+ sample emails que converteram)
[ ] Lista palavras proibidas/aprovadas
[ ] Critérios qualificação validados com Bruna
[ ] Decision_thresholds calibrados

EQUIPE
[ ] Gustavo confirmou disponibilidade 20h/semana × 8 semanas Fase 1
[ ] Thiago bloqueou 6h/semana × 8 semanas
[ ] Bruna disponível pra dual-run Fase 3 (notificada)
[ ] Joana disponível pra dual-run DockPlus Fase 3
[ ] Plano backup de dev caso Gustavo indisponível

GOVERNANÇA
[ ] Kill switch desenhado e implementado dia 1
[ ] Plano de incidente documentado
[ ] Runbook rollback escrito (target <5min)
[ ] Lista de quem é alertado em emergência

QUALIDADE
[ ] Dataset eval inicial (10-20 leads reais Roberts) preparado
[ ] Métricas baseline coletadas:
    - Tempo médio Bruna qualifica lead
    - Taxa conversão atual Roberts
    - Tempo médio Thiago responde lead noite
    - Posts IG/semana média atual
    - Receita 90 dias
[ ] Sistema feedback 👍/👎 desenhado
[ ] Plano versionamento prompts documentado

LEGAL/COMPLIANCE
[ ] Roberts: endereço físico documentado pra unsubscribe
[ ] DockPlus AI: endereço + termos pra prospecting
[ ] LGPD checklist Brasil
[ ] CAN-SPAM checklist US
```

**Se mais de 20% dos itens estão vermelhos, adia projeto até resolver.**

---

## 10. Plano de testes

### 10.1 Testes unitários (todo PR)

- Cobertura mínima 70%
- Mocks pra todas APIs externas
- Pytest + pytest-asyncio + pytest-mock
- Roda em CI antes de merge

### 10.2 Testes integração (toda merge main)

- Sandbox Telegram bot separado (`@maestro_dev_bot`)
- Sandbox GHL location separado
- Stripe modo test
- Supabase staging instance
- Não atinge APIs caras (Replicate mockado, Apollo limitado)

### 10.3 Testes E2E (semanal)

| Cenário | Trigger | Validação |
|---|---|---|
| Lead inbound full pipeline | webhook GHL fake | Email enviado, Calendar criado, GHL movido |
| Marketing post on-demand | Telegram message fake | Post gerado, preview ok, IG publicação |
| Cron CFO + CMO + CEO segunda | trigger manual cron | 3 outputs em business_metrics |
| Prospecting daily (Fase 2) | trigger manual | 50 leads enriched + 50 emails ready |
| Reply classifier (Fase 2) | webhook Gmail fake | Classificação correta + ação tomada |

### 10.4 Testes de carga (Fase 1, semana 8)

- 50 mensagens/min sustained 30min
- 100 webhooks GHL em 5min
- Verificar P90 latência + taxa erro

### 10.5 Testes recuperação (Fase 1, semana 8)

| Falha simulada | Comportamento esperado |
|---|---|
| Redis down | Sessões resetam, Supabase mantém histórico, no data loss |
| Supabase down | Mensagens em queue local, flush quando voltar |
| Anthropic 429 sustained | Fallback OpenAI ativa, alerta Thiago |
| Container crash | Restart automático <30s |
| Webhook signature inválida | 403, log, alerta se >5 em 5min |

### 10.6 Testes deliverability (Fase 2)

- Bounce rate <2% durante warmup 6 semanas
- Spam complaint = 0 durante todo período
- Reply rate ≥3% após semana 4 de envio
- Mailbox reputation Postmaster API "high"

### 10.7 Testes evals (Fase 3)

- Dataset 30-50 casos por agent
- Score baseline coletado semana 19
- Score weekly tracked
- Regressão >5% = trigger investigação imediata

---

## 11. Lançamento gradual (Fase 3)

### 11.1 Antes de qualquer release

- ✅ Todos critérios Fase 1-2 atendidos
- ✅ Soak test 7 dias passou (Fase 1)
- ✅ Dual-run 14 dias com >90% acordo (Fase 3)
- ✅ Backup verificado funcional
- ✅ Kill switch testado em produção
- ✅ Runbook revisado por Thiago + Gustavo

### 11.2 Plano release (Fase 3, semanas 23-24)

| Dia | % Leads autônomo | % Bruna/Joana review | Métricas a validar |
|---|---|---|---|
| 1-3 | 25% | 75% | Latência, custo, taxa erro |
| 4-7 | 50% | 50% | + qualidade output, aprovação Thiago |
| 8-10 | 75% | 25% | + reply rate prospecting (se Fase 2) |
| 11-14 | 100% | spot check | Tudo + reviews humanos pontuais |

### 11.3 Critérios go/no-go diário

A cada noite, Thiago + Gustavo decidem se prossegue ou rola back:

- ✅ Custo dia <$15: GO
- ✅ Taxa erro tools <2%: GO
- ✅ Aprovação Thiago >90%: GO
- ✅ Zero incidente crítico: GO
- ❌ Qualquer red → rollback automático pra % anterior

### 11.4 Rollback plan

```bash
# Em <5min
# Voltar pro nível anterior:
ssh thiago@vps "cd /opt/maestro && \
  echo 'AUTONOMOUS_PERCENT=50' >> .env && \
  docker compose restart maestro"

# Ou shutdown total:
ssh thiago@vps "cd /opt/maestro && docker compose down"
# Thiago volta a operar manualmente
```

---

## 12. Pós-lançamento

### 12.1 Métricas comparadas (90 dias pós-Fase 3)

| Métrica | Baseline (pré-MAESTRO) | Target | Real |
|---|---|---|---|
| Tempo médio resposta lead | 2-6h | <10min | _____ |
| Posts IG/semana Roberts | 1-2 | 5-7 | _____ |
| Briefing CFO entregue | 0% | 100% | _____ |
| Horas Thiago/semana ops | 25-30h | 5-10h | _____ |
| ROAS Meta+Google | _____ | +20-30% | _____ |
| Reuniões DockPlus AI/mês | 0 outbound | 4-15 | _____ |
| Custo operacional | $0 | <$700 | _____ |

### 12.2 Iteração contínua

- **Sprint review quinzenal:** Thiago + Gustavo
- **Backlog em GitHub Projects:** prioridade quinzenal
- **LangSmith evals mensais:** qualidade ao longo do tempo
- **Retrospectiva trimestral:** decisões de expansão

### 12.3 Quando expandir Fase 4

Adicionar novos canais (WhatsApp via OpenClaw), voice mode, ou agents adicionais (HR, Legal) **só se**:

- ✅ Sistema 90+ dias estável
- ✅ ROI confirmado (Thiago economizando ≥15h/semana real)
- ✅ Demanda de negócio justifica
- ✅ Custos sob controle

### 12.4 Documentação contínua

- README atualizado a cada feature nova
- ADRs novos pra decisões importantes
- Runbook atualizado pós-incidente
- Prompts versionados em git

---

## 13. Decisões e trade-offs explícitos

Esta seção documenta decisões controversas pra Thiago não esquecer **por que** foi assim.

### Decisão 1: Sem n8n / Make / Zapier

**Trade-off:** mais código Python upfront, mas debugável, performático, sem subscription.

### Decisão 2: Sem OpenClaw na Fase 1

**Trade-off:** Telegram só. Quando Cheesebread/Cape Codder precisarem WhatsApp, reavaliar Fase 4+.

### Decisão 3: Sem Hermes self-hosted

**Trade-off:** dependência Anthropic/OpenAI. Mas $200/mês é aceitável vs custo de GPU dedicada.

### Decisão 4: Function-first agents

**Trade-off:** profile JSON precisa ser bem desenhado. Compensa em escalabilidade.

### Decisão 5: Threshold humano $500

**Trade-off:** Thiago é gargalo em horário não-comercial. Mitigado por auto-reply neutro <8h.

### Decisão 6: Clay.com OU Apollo+Hunter

**Decisão atual:** começar Apollo+Hunter (já tem MCP), migrar Clay se waterfall manual virar dor.

### Decisão 7: 24 semanas pra qualidade extrema

**Trade-off:** vs 8 semanas MVP. Thiago pediu 100% funcional → 24 semanas é honesto. 8 seria fake.

### Decisão 8: Brand Guardian como subagent transversal

**Trade-off:** adiciona latência (~1-2s por output público), mas evita publicação fora da marca.

### Decisão 9: Domain prospecção separado

**Trade-off:** custo $15/ano + 4-6 semanas warmup. Mas spam complaint no domínio principal seria irreversível.

### Decisão 10: Trio Stack (Claude Code + Cursor + Codex CLI)

**Decisão:** alinhar com workflow Thiago já valida. Não tentar mudar processo de dev no meio do projeto.

---

## 14. Aprovação

| Stakeholder | Papel | Aprovação | Data |
|---|---|---|---|
| Thiago do Carmo | Owner / Decisor final | __________ | _____ |
| Gustavo | Implementador principal | __________ | _____ |

---

## 15. Compromissos finais (sem fake news)

Este PRD se compromete com:

✅ **Honestidade brutal** — sem promessas falsas. Sistema é probabilístico, não 100%.

✅ **Mensurabilidade** — toda meta tem número e como medir.

✅ **Reversibilidade** — toda fase pode ser rolled back se métricas falharem.

✅ **Humildade** — agents complementam time humano, não substituem.

✅ **Sustentabilidade** — custos controlados, kill switches, monitoring.

✅ **Auditabilidade** — toda decisão registrada, todo prompt versionado.

✅ **Soli Deo Gloria** — projeto serve família, time, e clientes. Tudo pra glória de Deus.

---

> *"Whatever you do, work at it with all your heart, as working for the Lord, not for human masters." — Colossians 3:23*

**Fim do PRD v2.0.**
