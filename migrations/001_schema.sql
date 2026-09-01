-- Landslide Early Warning System — initial schema
-- Two-layer risk model: zones.susceptibility_score (static, written by ML)
-- vs. alerts (dynamic, written by rainfall-threshold rules). Keep these
-- concepts separate in code, not just in this comment.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS zones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    geometry geometry(Polygon, 4326) NOT NULL,
    susceptibility_score DOUBLE PRECISION CHECK (susceptibility_score IS NULL OR (susceptibility_score BETWEEN 0 AND 1)),
    risk_tier TEXT CHECK (risk_tier IN ('low', 'moderate', 'high')),
    model_version TEXT,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_zones_geometry ON zones USING GIST (geometry);

CREATE TABLE IF NOT EXISTS rainfall_readings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zone_id UUID NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    "timestamp" TIMESTAMPTZ NOT NULL,
    intensity_mm DOUBLE PRECISION NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('open-meteo', 'imd')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rainfall_zone_time ON rainfall_readings (zone_id, "timestamp" DESC);

CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zone_id UUID NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    threshold_crossed TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'resolved')),
    delivery_method TEXT NOT NULL CHECK (delivery_method IN ('sms_mock', 'sms_twilio', 'log_only'))
);

CREATE INDEX IF NOT EXISTS idx_alerts_zone ON alerts (zone_id, triggered_at DESC);

CREATE TABLE IF NOT EXISTS citizen_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Client-generated UUID, sent by the reporting frontend so a retried
    -- submission (e.g. after an offline-queue flush) can be deduped instead
    -- of creating a second row. Unique but nullable -- older/other clients
    -- that don't send one still work, just without dedupe protection.
    client_report_id UUID UNIQUE,
    zone_id UUID REFERENCES zones(id) ON DELETE SET NULL,
    report_type TEXT NOT NULL CHECK (report_type IN ('crack', 'movement', 'road', 'other')),
    severity TEXT NOT NULL CHECK (severity IN ('low', 'moderate', 'high', 'critical')),
    geo_lat DOUBLE PRECISION NOT NULL,
    geo_lng DOUBLE PRECISION NOT NULL,
    geo_accuracy_m DOUBLE PRECISION,
    place_name TEXT,
    description TEXT NOT NULL,
    reporter_name TEXT,
    reporter_phone TEXT,
    photo_url TEXT,
    captured_at TIMESTAMPTZ NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    verified_status TEXT NOT NULL DEFAULT 'unverified' CHECK (verified_status IN ('unverified', 'verified', 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_reports_zone ON citizen_reports (zone_id, submitted_at DESC);
