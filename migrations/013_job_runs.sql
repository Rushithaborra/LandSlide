-- Remembers when a background job (today: the rainfall refresh) last completed, so the
-- app can tell "stale, refresh now" from "fresh, skip" without a scheduler of its own,
-- and the dashboard can say "rainfall updated 12 min ago". One row per job name.
-- Additive: nothing else reads or writes this table.
CREATE TABLE IF NOT EXISTS job_runs (
    name        TEXT PRIMARY KEY,
    last_run_at TIMESTAMPTZ NOT NULL,
    summary     JSONB
);
