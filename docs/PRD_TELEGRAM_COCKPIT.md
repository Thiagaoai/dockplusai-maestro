# PRD — MAESTRO Telegram Cockpit

**Produto:** MAESTRO v2.1 — Cockpit operacional via Telegram  
**Owner:** Thiago do Carmo  
**Status:** Ready for implementation  
**Objetivo:** permitir que Thiago administre todos os agents, subagents, fluxos, aprovações, custos e prioridades do MAESTRO diretamente pelo Telegram, com respostas rápidas, controle humano e histórico auditável.

---

## 1. Resumo Executivo

O Telegram deve virar o cockpit principal do MAESTRO. Thiago precisa conseguir mandar qualquer direção operacional em linguagem natural, pedir qualquer fluxo suportado, aprovar ou rejeitar ações, pausar agentes, consultar status e comandar subagents sem entrar em dashboard técnico.

O sistema deve ser mobile-first, responsivo e curto. MAESTRO deve entender a intenção, confirmar quando houver ambiguidade, executar o agent correto, mostrar preview quando houver risco externo e registrar tudo em Supabase + LangSmith.

### Meta do produto

Thiago deve conseguir escrever mensagens como:

- `roda CFO Roberts agora`
- `faz 3 posts para DockPlus sobre automação`
- `prospecta marinas no Cape usando perplexity`
- `pausa marketing`
- `quais aprovações estão pendentes?`
- `mostra custos de hoje`
- `manda follow-up para leads sem resposta`
- `cria campanha Roberts para spring cleanup`
- `qual agent falhou hoje?`

E receber uma resposta clara, em português, com botões acionáveis.

---

## 2. Problema

Hoje o MAESTRO já tem agents e subagents, mas o controle ainda está dividido entre webhooks, comandos específicos, scheduler, scripts, logs e Supabase. Isso impede uso diário fluido.

O problema real não é falta de agents. É falta de uma camada operacional unificada onde Thiago possa:

- descobrir o que cada agent pode fazer;
- disparar fluxos sob demanda;
- administrar estado dos agents;
- aprovar ações externas;
- consultar histórico;
- saber custo, erros e pendências;
- corrigir direção sem mexer em código.

---

## 3. Objetivos

### O1 — Comando universal por Telegram

Toda mensagem de Thiago deve ser classificada em uma destas categorias:

- comando administrativo;
- pedido de status;
- execução de fluxo;
- aprovação/rejeição/edição;
- pergunta operacional;
- fallback/clarificação.

Meta: **95%+ das mensagens comuns roteadas corretamente** em testes com dataset real.

### O2 — Administração completa dos agents

Thiago deve conseguir via Telegram:

- pausar/retomar todos os agents;
- pausar/retomar agent específico;
- ver status de agents;
- ver últimas execuções;
- ver erros recentes;
- ver custos;
- ver aprovações pendentes;
- rodar agent específico para negócio específico.

### O3 — Subagents acessíveis quando útil

Subagents não precisam ser expostos como botões técnicos sempre, mas Thiago deve conseguir acionar capacidades específicas:

- `qualifica esse lead`
- `refaz só a caption`
- `recalcula margem`
- `analisa ads`
- `prepara reunião`
- `move pipeline`

O sistema deve mapear isso para o subagent correto dentro do agent principal.

### O4 — Mobile-first real

Toda resposta Telegram deve caber no uso diário:

- primeira resposta em até 3 segundos para comandos simples;
- resposta de agent em andamento deve mandar “recebi, estou rodando” se passar de 5 segundos;
- cards com no máximo 6 linhas antes dos botões;
- detalhes longos atrás de botão `Ver detalhes`;
- nada de JSON cru para Thiago.

### O5 — Controle humano e segurança

Nenhuma ação externa relevante deve acontecer sem aprovação:

- email externo;
- post público;
- calendar event;
- pipeline move;
- campanha de ads;
- ação financeira;
- envio em lote.

Exceção só com política explícita futura.

---

## 4. Escopo

### Em escopo

- Telegram como interface única de comando.
- Roteamento natural-language para todos os agents existentes.
- Comandos administrativos.
- Central de aprovações.
- Status/custos/histórico.
- Execução on-demand de agents.
- Fluxos multi-step com memória curta por chat.
- Clarificação quando o pedido for incompleto.
- Botões inline para decisões rápidas.
- Registro completo em `agent_runs`, `audit_log`, `processed_events`, `business_metrics`.

### Fora de escopo nesta entrega

- App web completo.
- Multiusuário.
- WhatsApp/OpenClaw.
- Autonomia sem HITL.
- Voice mode.
- Dashboard visual avançado.

---

## 5. Agents e Capacidades Expostas

### Triage

Responsável por entender a mensagem e criar um `CommandIntent`.

Capacidades:

- detectar negócio;
- detectar agent;
- detectar fluxo;
- detectar urgência;
- detectar se falta informação;
- decidir se deve executar, perguntar ou mostrar menu.

### SDR

Fluxos Telegram:

- inbound lead review;
- qualificar lead;
- draft de email;
- sugerir horários;
- preparar follow-up;
- reengajar lead antigo;
- consultar lead por email/nome;
- listar leads pendentes.

Exemplos:

- `qualifica esse lead: Sarah quer patio em Falmouth 20k`
- `manda follow-up para leads Roberts sem resposta`
- `mostra leads quentes de hoje`

### Prospecting

Fluxos:

- Roberts owned list batch;
- Roberts web prospecting;
- DockPlus Apollo batch;
- busca por vertical/fonte/local;
- listar fila;
- pausar campanha;
- enviar lote após aprovação.

Exemplos:

- `prospecta hotéis Cape Cod com google`
- `roda Roberts 10`
- `DockPlus Apollo CEOs 20`

### Marketing

Fluxos:

- criar post;
- refazer caption;
- refazer hashtags;
- criar prompts de imagem;
- agendar post;
- listar calendário de conteúdo;
- revisar tom com Brand Guardian.

Exemplos:

- `faz 3 posts Roberts sobre spring cleanup`
- `refaz a caption mais premium`
- `cria post DockPlus sobre AI automation ROI`

### CFO

Fluxos:

- briefing financeiro;
- margem;
- cashflow;
- reconciliação invoice/pipeline;
- recomendações financeiras;
- alerta de risco.

Exemplos:

- `CFO Roberts agora`
- `qual margem estimada esse mês?`
- `me mostra risco de caixa DockPlus`

### CMO

Fluxos:

- análise de ads;
- ROAS/CPC;
- budget allocation;
- creative tests;
- recomendações de campanha.

Exemplos:

- `CMO Roberts ads`
- `onde cortar budget?`
- `quais criativos testar essa semana?`

### CEO

Fluxos:

- briefing executivo;
- decisões estratégicas;
- prioridade da semana;
- resumo cross-agent;
- riscos e oportunidades.

Exemplos:

- `CEO briefing geral`
- `qual prioridade da semana?`
- `resuma Roberts e DockPlus`

### Operations

Fluxos:

- calendar;
- follow-up operacional;
- pipeline move;
- tarefa interna;
- lembrete;
- preparação de reunião.

Exemplos:

- `agenda call com Sarah quinta 14h`
- `move lead Sarah para estimate sent`
- `prepara follow-up para proposta pendente`

### Brand Guardian

Subagent transversal para revisar outputs públicos:

- email;
- post;
- campanha;
- cold outreach;
- briefing externo.

Deve bloquear ou pedir refação quando o output:

- sai do tom do negócio;
- promete demais;
- usa linguagem ruim;
- viola regra de idioma;
- parece spam.

---

## 6. Comandos Administrativos

### Estado global

- `/stop` — pausa tudo.
- `/start` — retoma tudo.
- `/status` — mostra saúde geral.
- `/costs` — custo hoje/mês.
- `/pending` — aprovações pendentes.
- `/errors` — erros recentes.
- `/agents` — lista agents e status.
- `/help` — menu curto.

### Estado por agent

Formatos aceitos:

- `pausa marketing`
- `retoma sdr`
- `status cfo`
- `últimas execuções do prospecting`
- `erros do cmo hoje`

Critério: agent pausado individualmente não executa por Telegram, webhook ou scheduler, mas o sistema deve responder que ele está pausado.

### Estado por negócio

- `pausa Roberts`
- `retoma DockPlus`
- `status Roberts`
- `custos Roberts hoje`

---

## 7. Fluxos Conversacionais

### Fluxo simples

1. Thiago manda comando claro.
2. MAESTRO responde em até 3s com confirmação curta.
3. Agent executa.
4. Resultado ou approval card aparece.
5. Execução é registrada.

### Fluxo ambíguo

Exemplo: `faz uma campanha`.

MAESTRO deve perguntar:

`Para qual negócio e objetivo?`

Botões:

- `Roberts leads`
- `DockPlus demos`
- `Outro`

### Fluxo longo

Se uma execução passar de 5 segundos:

1. Responder: `Recebi. Rodando CFO Roberts agora.`
2. Continuar processamento.
3. Enviar resultado final.

### Fluxo de aprovação

Approval card deve ter:

- título curto;
- impacto esperado;
- risco/custo;
- preview;
- botões.

Botões padrão:

- `Aprovar`
- `Editar`
- `Rejeitar`
- `Ver detalhes`

---

## 8. Requisitos Funcionais

### RF1 — Intent universal

Criar schema `CommandIntent` com:

- `intent_type`
- `business`
- `agent`
- `subagent`
- `workflow`
- `action`
- `entities`
- `confidence`
- `requires_confirmation`
- `missing_fields`

### RF2 — Command router

Criar camada central entre Telegram e graph:

`Telegram update → CommandParser → CommandRouter → Agent/Workflow/AdminAction`

### RF3 — Agent registry

Criar registry declarativo com:

- agents disponíveis;
- subagents;
- workflows;
- aliases;
- campos obrigatórios;
- risco;
- se precisa HITL;
- se pode rodar em dry-run.

### RF4 — Session state

Manter estado curto por chat:

- comando pendente;
- último negócio;
- último agent;
- approval em edição;
- campos faltantes.

TTL padrão: 15 minutos.

### RF5 — Approval center

Telegram deve suportar:

- listar aprovações pendentes;
- aprovar por ID;
- rejeitar por ID;
- editar antes de aprovar;
- ver detalhes.

### RF6 — Status center

Telegram deve mostrar:

- agents ativos/pausados;
- custo hoje/mês;
- erros recentes;
- últimas execuções;
- pendências;
- scheduler status.

### RF7 — Error handling

Erro deve virar resposta útil:

- o que falhou;
- se algo foi enviado ou não;
- próximo passo;
- ID do run.

Nunca mandar stack trace para Thiago.

---

## 9. Requisitos Não Funcionais

- P90 comando simples: <3s.
- P90 agent síncrono: <15s ou resposta intermediária.
- 100% agent runs com `prompt_version`.
- 100% LLM calls via accounting central.
- 100% ações externas com audit log.
- 0 ações externas sem HITL.
- 0 JSON cru no Telegram.
- 0 PII sensível em logs.
- Idempotência para callbacks e comandos.
- Telegram whitelist obrigatória.

---

## 10. Critérios de Aceite

### CA1 — Comando universal

Dado 50 comandos reais em português/inglês, o sistema roteia corretamente pelo menos 45.

### CA2 — Administração

Thiago consegue pausar/retomar:

- tudo;
- um agent;
- um negócio.

### CA3 — Status

`/status` retorna:

- ambiente;
- dry-run;
- storage;
- agents pausados;
- custo hoje;
- aprovações pendentes;
- erros recentes.

### CA4 — Aprovações

`/pending` lista aprovações e cada item pode ser aprovado/rejeitado por botão.

### CA5 — Fluxos de agents

Cada agent principal tem pelo menos um fluxo Telegram testado end-to-end:

- SDR;
- Prospecting;
- Marketing;
- CFO;
- CMO;
- CEO;
- Operations.

### CA6 — Subagents

Cada subagent existente é chamado direta ou indiretamente em teste unitário ou E2E.

### CA7 — Segurança

Chat não autorizado recebe 403. `/stop` bloqueia execuções antes de gasto ou ação externa.

---

## 11. Roadmap de Implementação

### Sprint 1 — Command Center

- `CommandIntent` schema.
- `AgentRegistry`.
- `CommandParser`.
- `CommandRouter`.
- `/help`, `/status`, `/agents`, `/costs`, `/pending`.

### Sprint 2 — Agent Control

- pausar/retomar por agent;
- pausar/retomar por negócio;
- status por agent;
- últimas execuções;
- erros recentes.

### Sprint 3 — Workflow Router

- fluxos Telegram para SDR, Prospecting, Marketing, CFO, CMO, CEO, Operations.
- missing-field prompts.
- session state robusto.

### Sprint 4 — Approval Center

- listar pendências;
- editar approval;
- ver detalhes;
- aprovar/rejeitar por ID;
- histórico de decisões.

### Sprint 5 — Responsividade e Evals

- typing/progress messages;
- compact cards;
- dataset de 50 comandos reais;
- eval de roteamento;
- soak Telegram.

---

## 12. Definição de Pronto

Este PRD está completo quando Thiago consegue operar o MAESTRO por Telegram por 7 dias sem abrir código, Supabase ou logs para tarefas normais.

O sistema só deve exigir acesso técnico para:

- deploy;
- incidente real;
- nova integração;
- debug profundo.
