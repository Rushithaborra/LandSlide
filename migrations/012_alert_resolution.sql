-- Records when an alert was resolved and by whom, so an alert the system closes
-- itself (its rainfall cleared -- see app/services/rainfall_refresh.py) can be
-- told apart from one an officer closed, and shown that way on the Alerts page.
-- Both columns are nullable and additive; existing rows are unaffected (alerts
-- resolved before this migration simply have no timestamp or resolver).
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS resolved_by TEXT;

DO $$
BEGIN
    ALTER TABLE alerts
        ADD CONSTRAINT alerts_resolved_by_check CHECK (resolved_by IS NULL OR resolved_by IN ('officer', 'system'));
EXCEPTION WHEN duplicate_object THEN
    NULL;  -- already applied
END $$;
