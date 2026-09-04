-- GPS is unreliable in the mountainous, poor-signal terrain this app
-- targets. The citizen-reporting frontend deliberately allows a report with
-- a place name alone when GPS capture fails (see app/schemas.py --
-- CitizenReportIn still requires at least one of the two). Relax the
-- corresponding DB constraint to match. Non-destructive: only loosens a
-- NOT NULL constraint, touches no existing data. Safe to re-run --
-- DROP CONSTRAINT IF EXISTS-equivalent behavior for DROP NOT NULL is a
-- no-op in Postgres if already dropped.

ALTER TABLE citizen_reports ALTER COLUMN geo_lat DROP NOT NULL;
ALTER TABLE citizen_reports ALTER COLUMN geo_lng DROP NOT NULL;
