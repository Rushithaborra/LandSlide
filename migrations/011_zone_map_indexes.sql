-- Fixes a real, measured slowness once the table passed ~50k zones: every
-- query NOT filtered by state (the "All States" counts, the whole-region map,
-- the top-N highest-risk list) did a full sequential scan of `zones`, which is
-- 220 MB for 56,466 rows because each row carries its road-corridor polygon
-- (EXPLAIN ANALYZE: ~4.1 s for a plain COUNT with filters). State-filtered
-- queries were fast (~1 s) only because they use idx_zones_state.
--
-- Both indexes are small (a few MB) and additive; nothing else changes.

-- 1. Map viewport + counts (GET /zones/map, GET /zones/stats). The covering
--    INCLUDE columns let Postgres answer them from the index alone, without
--    reading the polygons in the table. Leading on the centroid columns so a
--    bounding-box query narrows on latitude whether or not a state is given.
CREATE INDEX IF NOT EXISTS idx_zones_map
    ON zones (centroid_lat, centroid_lng) INCLUDE (state, risk_tier);

-- 2. "Highest-risk N zones" with no state filter (Overview cards, rainfall
--    trend). Matches the ORDER BY in GET /zones exactly (score desc, nulls
--    last, id as the paging tiebreaker) so LIMIT N reads N index entries
--    instead of sorting every zone. idx_zones_state_score only helps when a
--    state is given.
CREATE INDEX IF NOT EXISTS idx_zones_score_id
    ON zones (susceptibility_score DESC NULLS LAST, id);

-- 3. Highway Corridors (GET /corridors) groups every zone by road code, which
--    needs each zone's name, tier and score. Carrying them in the index lets
--    that whole aggregate run from the index instead of reading 220 MB of
--    polygons (All States took 7-9 s at 56k zones).
CREATE INDEX IF NOT EXISTS idx_zones_corridor
    ON zones (state) INCLUDE (id, name, risk_tier, susceptibility_score);
