-- Villages, towns and emergency services (hospital, clinic, police, fire station)
-- from OpenStreetMap, loaded by scripts/load_osm_places.py from a dated snapshot
-- (scripts/fetch_osm_places.py). Used by GET /zones/{id}/surroundings to show what
-- lies around a road stretch. OpenStreetMap is volunteer-mapped: treat it as
-- incomplete and possibly out of date. Distances are straight-line.
CREATE TABLE IF NOT EXISTS places (
    osm_id     TEXT PRIMARY KEY,               -- n123 / w123 / r123
    kind       TEXT NOT NULL CHECK (kind IN ('village', 'town', 'city', 'hospital', 'clinic', 'police', 'fire_station')),
    name       TEXT,
    lat        DOUBLE PRECISION NOT NULL,
    lng        DOUBLE PRECISION NOT NULL,
    phone      TEXT,                           -- only if OpenStreetMap has one; unverified
    fetched_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS places_kind_lat_lng ON places (kind, lat, lng);
