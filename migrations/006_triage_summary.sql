-- AI-generated one-line triage summary per citizen report (see
-- app/services/triage_summary.py). Nullable: reports submitted before this
-- migration, or without ANTHROPIC_API_KEY configured, simply have none.

ALTER TABLE citizen_reports ADD COLUMN IF NOT EXISTS triage_summary TEXT;
