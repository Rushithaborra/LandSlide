-- Closes a latent gap left by migrations/009_zone_centroid_columns.sql:
-- centroid_lat/lng had to start nullable (existing rows had no value yet at
-- ALTER TABLE time), but ZoneOut (app/schemas.py) has always required both
-- as plain, non-optional floats. Every current zone-creation path already
-- sets them (scripts/seed_zone.py, scripts/integrate_zone_predictions.py),
-- and 009's backfill covers every existing row -- verified live, zero NULL
-- rows in production. Enforcing NOT NULL now turns "a future insert path
-- forgets to set centroid" from a silent GET /zones 500 (Pydantic
-- validation failure on serialization, for every zone in that response, not
-- just the bad row) into a loud insert-time database error instead.

ALTER TABLE zones ALTER COLUMN centroid_lat SET NOT NULL;
ALTER TABLE zones ALTER COLUMN centroid_lng SET NOT NULL;
