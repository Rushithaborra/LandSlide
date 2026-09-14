-- Fixes a real, demonstrated production bug: zones.centroid_lat/lng were
-- computed in Python (Shapely, per-row) on every GET /zones request instead
-- of stored. That was tolerable at Sikkim's 3,921 zones (already a slow
-- ~45-60s load) but made GET /zones time out completely once Assam's
-- 66,677 real road-corridor zones landed -- confirmed live: a raw SQL
-- COUNT(*) over the same table took 0.56s, so the database itself was never
-- the bottleneck, only the per-request Python centroid computation + fully
-- unbounded response size were.

ALTER TABLE zones ADD COLUMN IF NOT EXISTS centroid_lat DOUBLE PRECISION;
ALTER TABLE zones ADD COLUMN IF NOT EXISTS centroid_lng DOUBLE PRECISION;

-- One-time backfill for all existing rows, done in PostGIS (fast, set-based)
-- instead of row-by-row Python -- the same operation that was silently
-- costing every API request now happens once, here.
UPDATE zones
SET centroid_lat = ST_Y(ST_Centroid(geometry)),
    centroid_lng = ST_X(ST_Centroid(geometry))
WHERE centroid_lat IS NULL OR centroid_lng IS NULL;

-- GET /zones and /corridors both now ORDER BY susceptibility_score before
-- LIMIT (see app/routers/zones.py) so a capped response still surfaces the
-- zones that matter most -- without an index, that sort has to scan and
-- order every matching row (66,677 for Assam alone) before applying the
-- limit.
CREATE INDEX IF NOT EXISTS idx_zones_state_score
    ON zones (state, susceptibility_score DESC);
