# SMS & Voice Alert System — Handover Notes

Original module: teammate D's `sms_alerts.py` (SIH26001 backend integration), received
2026-09-13 as a zip with a PDF handover doc, `sms_alerts.py`, `sms_alert_log_migration.sql`,
and `manual_alert_test.py`. This doc records what it does, what was wrong with the
as-received version for this specific codebase, and where it actually lives now.

## What it does

When a zone crosses into danger, `app/services/sms_alerts.py` looks up who to warn, sends
an SMS (and, for the worst cases, places a real phone call to registered officials), and
logs when it last did that so it doesn't repeat every few minutes.

## Fixes made porting the original module into this codebase

The original was written against a raw `psycopg2` connection and a schema that doesn't
match this project's real one. Concretely, before integrating:

1. **DB access style** — the original used `db_conn.cursor()` / `%s` placeholders (plain
   psycopg2). This backend uses SQLAlchemy ORM `Session` everywhere else — passing a
   `Session` into psycopg2-style code would have crashed immediately. Rewritten as SQLAlchemy
   `select()` queries against real ORM models.
2. **Wrong table name** — `get_subscribers_for_zone` queried `FROM reports`; the real table
   is `citizen_reports` (see `app/models.py`).
3. **`zone_id` type** — the original migration typed `sms_alert_log.zone_id` as `TEXT`; this
   schema's `zones.id` is `UUID`. Fixed in `migrations/005_sms_alerts.sql` (proper FK to
   `zones(id)`).
4. **Severity-vocabulary mismatch (the real bug)** — `escalate_critical_alert()` only places
   phone calls when `severity == "critical"`. But the automated rainfall engine
   (`alert_engine.check_and_trigger`) only ever produces `risk_tier` ∈ `{low, moderate, high}`
   — there is no "critical" tier there. `"critical"` only exists where a human picks it, in
   the Broadcast composer (`AlertBroadcast.severity` / `BroadcastIn.severity`). Wired only
   into the automated path as the original handover doc suggested, the call-escalation
   branch would have been permanently dead code.
5. **Config** — Twilio credentials now go through `app.config.settings`
   (`twilio_account_sid` / `twilio_auth_token` / `twilio_from_number`), matching every other
   credential in this project (e.g. `supabase_*`), instead of raw `os.environ.get()`.

## Where it's actually wired in

Two entry points, matching the two places a severity actually comes from:

- **`app/services/alert_engine.py:check_and_trigger()`** — after creating an `Alert` from a
  real rainfall-threshold crossing, calls `trigger_zone_alert()` (SMS only, using the zone's
  `risk_tier` as severity). Sets `Alert.delivery_method` to the schema's existing
  `"sms_twilio"` value if at least one text actually sent, otherwise leaves it `"log_only"`
  — honest either way, and Twilio being unconfigured never breaks the core alert-creation
  logic (wrapped so a Twilio failure can't roll back a real, already-committed alert).
- **`app/routers/alerts.py:broadcast_alert()`** — the operator-driven Broadcast composer,
  the only place `"critical"` severity is ever actually chosen. When `"sms"` is one of the
  chosen `channels`, sends the operator's own written `message` as a real SMS; when
  `severity == "critical"`, also places real calls to every row in `authority_contacts` via
  `escalate_critical_alert()`. `AlertBroadcast.status` becomes `"sent"` only if a real send
  was attempted and Twilio was configured — otherwise it stays `"simulated"`, same honesty
  as before this integration.

## Setup — required before either path sends anything real

1. `twilio` is now in `requirements.txt` / `requirements-backend.txt`.
2. Run `migrations/005_sms_alerts.sql` (via `python scripts/migrate.py`) — creates
   `sms_alert_log` and `authority_contacts`.
3. Set three env vars (`.env` locally, Render's dashboard in production — never commit
   these): `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`.
4. Insert at least one real (or your own, for testing) row into `authority_contacts` for
   calls to have anyone to reach.

**Twilio trial account limitation:** on a trial (not paid) account, both SMS and voice calls
can only reach phone numbers manually verified in the Twilio console first. Verify your own
number and teammates' numbers before rehearsing, or sends will silently fail.

## Known limitations (say these out loud if asked, don't hide them)

- Twilio trial account can only send to manually verified numbers — a real citizen's number
  won't receive anything until the account is upgraded.
- Subscriber list is sourced from citizen report phone numbers, not a proper opt-in flow —
  a real "subscribe to alerts for my area" screen is a legitimate next step, not built yet.
- No retry logic if a send fails (e.g. a transient network issue) — failures are logged and
  returned, not automatically retried.
- Message wording is English only, same multilingual gap already noted elsewhere.
- Neither Render's production env nor this repo's `authority_contacts` table has real
  officials registered yet — both are empty until the team adds them.
