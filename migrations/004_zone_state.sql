-- NER expansion, phase 1: zones need to know which state they belong to.
-- DEFAULT 'Sikkim' makes this non-destructive for the 3,921 existing real
-- rows -- they're correctly backfilled by the column default itself, no
-- separate UPDATE needed. CHECK constraint keeps a typo from silently
-- creating an unfilterable ghost state.

ALTER TABLE zones ADD COLUMN IF NOT EXISTS state TEXT NOT NULL DEFAULT 'Sikkim';

ALTER TABLE zones DROP CONSTRAINT IF EXISTS zones_state_check;
ALTER TABLE zones ADD CONSTRAINT zones_state_check CHECK (state IN ('Sikkim', 'Assam', 'Mizoram'));

CREATE INDEX IF NOT EXISTS idx_zones_state ON zones (state);
