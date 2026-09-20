-- "Rain worsened" updates for alerts that are already active. An alert is raised
-- once and never re-raised while it stays active, so heavier rain later used to be
-- invisible on it. These columns record how bad the rain was when the alert was
-- last raised/updated (peak_ratio = mean rainfall / danger level, 1.0 = exactly at
-- the level), and when and how often it has since been updated because the rain
-- got clearly worse. All additive; existing alerts start with no baseline and are
-- measured from the next refresh (no update is sent for them on deploy).
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS peak_ratio DOUBLE PRECISION;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS worsened_at TIMESTAMPTZ;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS worsened_count INTEGER NOT NULL DEFAULT 0;
