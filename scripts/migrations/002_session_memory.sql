-- Migration: session_memory
-- Purpose: Persistent cross-session dev memory for MAESTRO.
-- Usage: python scripts/session_memory.py last  →  resume from last session

CREATE TABLE IF NOT EXISTS session_memory (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at timestamptz DEFAULT now(),
  session_date date DEFAULT current_date,
  title text NOT NULL,
  summary text NOT NULL,
  pending jsonb DEFAULT '[]'::jsonb,
  done jsonb DEFAULT '[]'::jsonb,
  metadata jsonb DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS session_memory_date_idx ON session_memory (session_date DESC);
CREATE INDEX IF NOT EXISTS session_memory_created_at_idx ON session_memory (created_at DESC);

COMMENT ON TABLE session_memory IS 'Persistent cross-session memory for MAESTRO development. Query ORDER BY created_at DESC LIMIT 1 to resume.';
