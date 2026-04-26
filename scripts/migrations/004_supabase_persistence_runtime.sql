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
