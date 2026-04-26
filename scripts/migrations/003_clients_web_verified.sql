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
