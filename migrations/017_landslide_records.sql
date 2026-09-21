-- Real historical landslide records (Geological Survey of India inventories, one per
-- state), loaded by scripts/load_landslide_records.py. They replace the sample
-- "incidents" the dashboard used to show. The inventories carry a place, coordinates and
-- an activity status but almost never a date or severity, so neither is stored or shown.
-- slide_no is the GSI's own reference; it is NOT unique or always present (75 of Sikkim's
-- rows have none), so rows have their own id.
CREATE TABLE IF NOT EXISTS landslide_records (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slide_no     TEXT,
    state        TEXT NOT NULL CHECK (state IN ('Sikkim','Assam','Arunachal Pradesh','Manipur','Meghalaya','Mizoram','Nagaland','Tripura')),
    district     TEXT,
    slide_name   TEXT,
    location     TEXT,               -- the road section / place description
    lat          DOUBLE PRECISION NOT NULL,
    lng          DOUBLE PRECISION NOT NULL,
    activity     TEXT NOT NULL DEFAULT 'Unknown',
    material     TEXT,
    movement     TEXT,
    history_note TEXT,               -- free text from the inventory (dates are not parsed)
    source       TEXT NOT NULL DEFAULT 'Geological Survey of India landslide inventory'
);
CREATE INDEX IF NOT EXISTS landslide_records_state ON landslide_records (state, district);
CREATE INDEX IF NOT EXISTS landslide_records_state_activity ON landslide_records (state, activity);
