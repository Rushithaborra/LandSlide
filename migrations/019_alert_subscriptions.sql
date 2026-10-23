-- Opt-in alert subscriptions: a resident subscribes THEIR OWN device to warnings near a point
-- (a village), instead of being inferred from a citizen report's phone number. Channel-agnostic:
-- 'webpush' stores the browser's push endpoint and keys (no phone number, no name); 'sms' is
-- reserved for later, when a confirmed phone number can be stored in `endpoint`.
-- Public data is limited to what a notification needs: where, how wide, which language.
-- `unsubscribe_token` is the only credential: whoever holds it can delete the row (the
-- browser keeps it in localStorage); it is never returned by any list endpoint.
CREATE TABLE IF NOT EXISTS alert_subscriptions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel           TEXT NOT NULL CHECK (channel IN ('webpush', 'sms')),
    endpoint          TEXT NOT NULL UNIQUE,
    p256dh            TEXT,
    auth              TEXT,
    lat               DOUBLE PRECISION NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lng               DOUBLE PRECISION NOT NULL CHECK (lng BETWEEN -180 AND 180),
    radius_km         DOUBLE PRECISION NOT NULL DEFAULT 3 CHECK (radius_km > 0 AND radius_km <= 10),
    place_label       TEXT,
    language          TEXT NOT NULL DEFAULT 'en' CHECK (language IN ('en', 'hi', 'ne')),
    unsubscribe_token TEXT NOT NULL UNIQUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_notified_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_alert_subscriptions_area ON alert_subscriptions (lat, lng);

-- Row-level security ON with no policies: Supabase's public REST API (anon key) can read or write
-- nothing in this table. The backend connects as the postgres role, which bypasses RLS, so it is
-- unaffected. Push endpoints and keys are credentials-adjacent and should never be world-readable.
ALTER TABLE alert_subscriptions ENABLE ROW LEVEL SECURITY;

-- When subscribers were told an alert had reached Warning level (a crossing in a short
-- window), so each alert notifies once on reaching it. Null = not notified (yet).
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS warning_notified_at TIMESTAMPTZ;
