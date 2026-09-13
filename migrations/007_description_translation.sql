-- AI-translated English rendering of a citizen report's description (see
-- app/services/translation.py). The original description column is never
-- altered; this is a separate, additive field shown alongside it.

ALTER TABLE citizen_reports ADD COLUMN IF NOT EXISTS description_translated TEXT;
