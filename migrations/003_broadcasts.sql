-- An alert being written to the DB (alerts table) is not the same thing as
-- an officer actually deciding to push it out to the public. This table
-- records that separate, explicit human action -- one alert can have zero
-- or several broadcast attempts (a first draft, a correction, a re-send).
-- status stays 'simulated' honestly: no real SMS/CAP/siren gateway is wired
-- up yet, same honesty pattern as alerts.delivery_method='log_only'.

CREATE TABLE IF NOT EXISTS alert_broadcasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id UUID NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    headline TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('moderate', 'high', 'critical')),
    message TEXT NOT NULL,
    channels TEXT[] NOT NULL,
    status TEXT NOT NULL DEFAULT 'simulated' CHECK (status IN ('simulated', 'sent')),
    dispatched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_broadcasts_alert ON alert_broadcasts (alert_id, dispatched_at DESC);
