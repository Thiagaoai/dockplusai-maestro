CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  telegram_chat_id BIGINT NOT NULL,
  thread_id TEXT NOT NULL UNIQUE,
  business TEXT NOT NULL DEFAULT 'roberts',
  started_at TIMESTAMPTZ DEFAULT NOW(),
  last_active_at TIMESTAMPTZ DEFAULT NOW(),
  message_count INT DEFAULT 0,
  total_cost_usd NUMERIC(10,6) DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_conv_chat ON conversations(telegram_chat_id);
CREATE INDEX IF NOT EXISTS idx_conv_active ON conversations(last_active_at DESC);

CREATE TABLE IF NOT EXISTS agent_runs (
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
  prompt_version TEXT NOT NULL,
  profit_signal TEXT,
  human_approved BOOLEAN,
  dry_run BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_runs_business ON agent_runs(business, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_agent ON agent_runs(agent_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_cost ON agent_runs(cost_usd DESC, created_at DESC);

CREATE TABLE IF NOT EXISTS processed_events (
  event_id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  business TEXT,
  result JSONB,
  processed_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '7 days'
);

CREATE INDEX IF NOT EXISTS idx_events_expires ON processed_events(expires_at);

CREATE TABLE IF NOT EXISTS audit_log (
  id BIGSERIAL PRIMARY KEY,
  event_type TEXT NOT NULL,
  business TEXT,
  agent TEXT,
  action TEXT NOT NULL,
  payload JSONB NOT NULL,
  prev_hash TEXT,
  hash TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_business_time ON audit_log(business, created_at DESC);

CREATE OR REPLACE FUNCTION reject_audit_modifications()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS no_update_audit ON audit_log;
CREATE TRIGGER no_update_audit BEFORE UPDATE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION reject_audit_modifications();

DROP TRIGGER IF EXISTS no_delete_audit ON audit_log;
CREATE TRIGGER no_delete_audit BEFORE DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION reject_audit_modifications();

CREATE TABLE IF NOT EXISTS business_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business TEXT NOT NULL,
  metric_type TEXT NOT NULL,
  metric_data JSONB NOT NULL,
  generated_by TEXT,
  period_start DATE,
  period_end DATE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_metrics_business_type_period
  ON business_metrics(business, metric_type, period_start DESC);

CREATE TABLE IF NOT EXISTS leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id TEXT UNIQUE,
  ghl_contact_id TEXT UNIQUE,
  business TEXT NOT NULL,
  name TEXT,
  phone TEXT,
  email TEXT,
  source TEXT,
  message TEXT,
  estimated_ticket_usd NUMERIC,
  qualification_score INT,
  qualification_reasoning TEXT,
  status TEXT DEFAULT 'new',
  thiago_approved BOOLEAN DEFAULT FALSE,
  thiago_approved_at TIMESTAMPTZ,
  raw JSONB,
  enrichment_data JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_leads_business_status ON leads(business, status);
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(qualification_score DESC);
CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);

CREATE TABLE IF NOT EXISTS prospect_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business TEXT NOT NULL,
  lead_id UUID REFERENCES leads(id),
  source_type TEXT NOT NULL,
  source_name TEXT NOT NULL,
  source_ref TEXT,
  status TEXT NOT NULL DEFAULT 'queued',
  priority INT NOT NULL DEFAULT 50,
  sequence_bucket TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (business, source_type, source_ref)
);

CREATE INDEX IF NOT EXISTS idx_prospect_queue_next
  ON prospect_queue(business, status, priority DESC, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_prospect_queue_source
  ON prospect_queue(business, source_type, status);

CREATE TABLE IF NOT EXISTS clients_web_verified (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business TEXT NOT NULL,
  lead_id UUID REFERENCES leads(id),
  property_name TEXT NOT NULL,
  email TEXT NOT NULL,
  source_name TEXT NOT NULL,
  source_ref TEXT,
  source_url TEXT,
  verification_note TEXT,
  campaign TEXT NOT NULL,
  approval_id UUID REFERENCES approval_requests(id),
  email_id TEXT,
  send_status TEXT NOT NULL DEFAULT 'sent',
  sent_at TIMESTAMPTZ DEFAULT NOW(),
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (business, email, campaign)
);

CREATE INDEX IF NOT EXISTS idx_clients_web_verified_business_sent
  ON clients_web_verified(business, sent_at DESC);

CREATE INDEX IF NOT EXISTS idx_clients_web_verified_email
  ON clients_web_verified(email);

CREATE TABLE IF NOT EXISTS memory_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business TEXT NOT NULL,
  content TEXT NOT NULL,
  embedding VECTOR(1536),
  metadata JSONB,
  importance_score NUMERIC DEFAULT 0.5,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  last_accessed_at TIMESTAMPTZ DEFAULT NOW(),
  access_count INT DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_memory_business ON memory_chunks(business);

CREATE TABLE IF NOT EXISTS corrections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_run_id UUID REFERENCES agent_runs(id),
  feedback TEXT NOT NULL,
  thiago_correction TEXT,
  applied_in_prompt_version TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_costs (
  date DATE PRIMARY KEY,
  total_cost_usd NUMERIC(10,4) NOT NULL,
  by_agent JSONB,
  by_business JSONB,
  alerted BOOLEAN DEFAULT FALSE,
  killed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS approval_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business TEXT NOT NULL,
  lead_id UUID REFERENCES leads(id),
  event_id TEXT NOT NULL,
  action TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  preview JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  decided_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_requests(status, created_at DESC);

CREATE TABLE IF NOT EXISTS approval_threads (
  approval_id UUID PRIMARY KEY REFERENCES approval_requests(id) ON DELETE CASCADE,
  thread_id TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_approval_threads_thread
  ON approval_threads(thread_id);

CREATE TABLE IF NOT EXISTS dry_run_actions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  approval_id UUID REFERENCES approval_requests(id),
  business TEXT,
  action TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dry_run_actions_business_time
  ON dry_run_actions(business, created_at DESC);
