-- Landslide Early Warning System — initial schema
-- Two-layer risk model: zones.susceptibility_score (static, written by ML)
-- vs. alerts (dynamic, written by rainfall-threshold rules). Keep these
-- concepts separate in code, not just in this comment.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS zones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    geometry geometry(Polygon, 4326) NOT NULL,
    susceptibility_score DOUBLE PRECISION,
    risk_tier TEXT CHECK (risk_tier IN ('low', 'moderate', 'high')),
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
    zone_id UUID REFERENCES zones(id) ON DELETE SET NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    photo_url TEXT,
    geo_lat DOUBLE PRECISION NOT NULL,
    geo_lng DOUBLE PRECISION NOT NULL,
    description TEXT,
    verified_status TEXT NOT NULL DEFAULT 'unverified' CHECK (verified_status IN ('unverified', 'verified', 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_reports_zone ON citizen_reports (zone_id, submitted_at DESC);
