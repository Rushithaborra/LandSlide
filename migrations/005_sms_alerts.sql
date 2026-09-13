-- Real SMS/voice alert delivery (app/services/sms_alerts.py), ported from
-- teammate D's handover module. zone_id is UUID + FK here (not TEXT, as the
-- original handover doc's migration had it) to match zones.id.

CREATE TABLE IF NOT EXISTS sms_alert_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zone_id UUID NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    severity TEXT NOT NULL,
    recipient_count INTEGER NOT NULL,
    channel TEXT NOT NULL DEFAULT 'sms' CHECK (channel IN ('sms', 'call')),
    sent_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Speeds up "what was the last alert for this zone+channel" cooldown lookups.
CREATE INDEX IF NOT EXISTS idx_sms_alert_log_zone_channel_sent_at
    ON sms_alert_log (zone_id, channel, sent_at DESC);

-- Hand-registered officials who get an actual phone call on CRITICAL
-- broadcasts only -- deliberately separate from citizen_reports, since
-- officials need to be properly registered, not scraped from reports.
CREATE TABLE IF NOT EXISTS authority_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    role TEXT,
    phone_number TEXT NOT NULL,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Example row -- replace with real officials before the demo:
-- INSERT INTO authority_contacts (name, role, phone_number)
-- VALUES ('Test Officer', 'District DM Officer', '+91XXXXXXXXXX');
