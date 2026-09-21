from pydantic import BaseModel, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RainfallThresholdConfig(BaseModel):
    """Rainfall intensity-duration (I-D) threshold definition. Deliberately a
    data structure, not a Python constant — swap the whole thing via env vars
    (or a future admin endpoint) as the team's literature research firms up,
    without touching code. No field here has an invented value: every number
    must trace to `source`/`source_doi`, and `verified_against_primary_text`
    must be set honestly.
    """

    region: str
    equation_type: str = "power_law_intensity_duration"  # I = coefficient * D^exponent
    coefficient: float
    exponent: float
    duration_unit: str = "days"
    intensity_unit: str = "mm/day"
    durations_days: list[int] = [1, 3, 5, 7, 10, 15, 20]
    source: str
    source_doi: str | None = None
    # False unless someone has actually read the primary text and confirmed
    # these coefficients. Do not flip this to True on trust alone.
    verified_against_primary_text: bool = False

    @model_validator(mode="after")
    def _engine_units_are_days_and_mm_per_day(self):
        """The alert engine computes `coefficient * D**exponent` with D in DAYS
        and reads the result as mm/day; the unit fields are documentation, not
        conversions. A published equation in other units (Assam's is in mm/h and
        hours) must be converted BEFORE it is configured -- silently feeding raw
        hourly coefficients into the daily formula put Assam's thresholds 5.2x
        too low. Failing here turns that mistake into a startup error."""
        if self.duration_unit != "days" or self.intensity_unit != "mm/day":
            raise ValueError(
                f"rainfall threshold for {self.region!r} is declared in {self.intensity_unit} / "
                f"{self.duration_unit}, but the alert engine works in mm/day and days: convert the "
                "coefficient first, then set duration_unit=days and intensity_unit=mm/day"
            )
        return self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:5432/landslide_ews"

    # Officer access key (app/security.py). Unset = not enforced.
    api_key: str | None = None

    # States whose rainfall threshold may fire ALERTS (and SMS). Deliberately an
    # explicit list, default Sikkim only (what production has always done): a
    # state can have a threshold configured for display and data refresh without
    # being trusted to alert. Assam's Guwahati equation, for one, is fit to only 19
    # landslides in one city and sits below ordinary monsoon rain (all 25 of Assam's
    # highest-risk zones were over it in mid-September), so it must not be the rule
    # that alerts. To switch a state on, remove its own RAINFALL_THRESHOLDS__<STATE>__*
    # block if that block is not fit for the whole state (the IMD baseline below then
    # applies) and add it here (RAINFALL_ALERT_STATES=["sikkim","assam"]).
    rainfall_alert_states: list[str] = ["sikkim"]

    # Auto-resolve (app/services/alert_engine.has_cleared): an alert closes itself
    # only once the rainfall has stayed below its threshold for this many days in
    # a row. More than one so a brief lull mid-storm doesn't close a live alert
    # (and re-alert, and re-text people, an hour later).
    rainfall_alert_clear_days: int = 2

    # "Rain worsened" update (app/services/alert_engine.escalate_if_worsened): an
    # already-active alert is updated (and citizens re-texted) when its zone's rain
    # is at least this much further above the danger level than when the alert was
    # last raised/updated -- measured in multiples of the danger level, so 0.5 means
    # "half the danger level again". Then at most once per `min_hours` per alert, so
    # a long storm doesn't text people every hour. The step and gap are the team's
    # own explainable rule, not literature-sourced.
    rainfall_escalation_step: float = 0.5
    rainfall_escalation_min_hours: int = 6
    # Only windows up to this many days count when judging "worse": a 15-20 day window
    # is dominated by rain already counted when the alert was raised and barely moves
    # with a new burst, while a fading storm can make it look worse for no new rain.
    rainfall_escalation_max_window_days: int = 5

    # Rainfall is refreshed automatically when it is older than this. Anyone opening
    # the dashboard can trigger it (POST /rainfall/refresh-if-stale), but never more
    # often than this, so it can't be used to hammer Open-Meteo. Hourly matches how
    # often Open-Meteo itself updates; ~77 zones a run is well inside its free limits.
    rainfall_refresh_max_age_minutes: int = 150

    # Scheduled rainfall refresh (app/services/rainfall_refresh.py): how many of
    # each state's highest-risk zones to refresh per run. Only states with a
    # configured rainfall threshold are refreshed (others can't alert).
    rainfall_refresh_zones_per_state: int = 25

    open_meteo_base_url: str = "https://api.open-meteo.com/v1/forecast"

    # Citizen report photo upload (app/routers/reports.py) -- stored in
    # Supabase Storage, not local disk (a deployed host's filesystem is
    # ephemeral; Supabase Storage is the same free project already used for
    # the database, so no extra service to set up). Optional at the Settings
    # level so importing app.config doesn't require these to be set unless a
    # photo is actually uploaded -- _save_photo() checks and raises a clear
    # error at that point instead.
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_storage_bucket: str = "citizen-reports"
    max_photo_size_bytes: int = 10 * 1024 * 1024  # 10MB
    allowed_photo_content_types: list[str] = [
        "image/jpeg", "image/png", "image/heic", "image/heif",
    ]

    # Original single-state field, kept as-is on purpose: Render's live
    # deployment already has RAINFALL_THRESHOLD__COEFFICIENT etc. set in its
    # dashboard (not this repo -- see render.yaml's `sync: false` entries),
    # and this session has no way to edit Render's env vars directly. Making
    # this optional and keeping it, rather than renaming/removing it, means
    # Sikkim's alerting keeps working in production with zero manual steps.
    rainfall_threshold: RainfallThresholdConfig | None = None

    # NER expansion, phase 1: new states get their own entry here instead of
    # reusing Sikkim's config. Keyed by state, lowercased by pydantic-settings'
    # env parsing (e.g. RAINFALL_THRESHOLDS__ASSAM__COEFFICIENT ->
    # thresholds["assam"]). A state with no entry (e.g. Mizoram, which has no
    # dedicated published equation yet) means alert_engine.py honestly skips
    # alerting for it rather than borrowing another state's number.
    rainfall_thresholds: dict[str, RainfallThresholdConfig] = {}

    # Real SMS/voice delivery (app/services/sms_alerts.py), teammate D's
    # module. Optional, same pattern as supabase_* above -- the app runs fine
    # without these, but sms_alerts.get_twilio_client() raises a clear error
    # the moment something actually tries to send. Never commit real values.
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None

    # AI-generated triage summary (app/services/triage_summary.py) -- condenses
    # a citizen report's free-text description into a one-line priority
    # summary via Gemini (Google AI Studio's free tier -- no budget for
    # Anthropic's prepaid API credits on this project). Optional, same
    # pattern as everything else above: POST /reports still works without
    # it, just leaves triage_summary null.
    google_api_key: str | None = None

    # India Meteorological Department API portal (app/services/imd.py). The key is bound to
    # one registered server IP; the JWT is minted from the portal account's email and
    # password, so those are secrets too. SecretStr keeps them out of logs and reprs.
    imd_api_key: SecretStr | None = None
    imd_email: str | None = None
    imd_password: SecretStr | None = None


settings = Settings()


# The baseline for a state with no published landslide threshold of its own: the India
# Meteorological Department's "heavy rain" category, 64.5 mm or more in 24 hours
# (heavy 64.5-115.5, very heavy 115.6-204.4, extremely heavy 204.5+). It is a rainfall
# category the IMD uses for its own warnings, NOT a landslide-specific threshold, and the
# team's susceptibility scaling still applies on top (a high-risk road alerts at 80% of
# it). One 24-hour window only: the multi-day windows of an intensity-duration curve are
# what made Assam's Guwahati equation fire all monsoon. Nothing here is borrowed from
# another state's landslide study.
IMD_HEAVY_RAIN = RainfallThresholdConfig(
    region="IMD heavy-rain level (national baseline)",
    equation_type="fixed_daily_amount",
    coefficient=64.5,
    exponent=0.0,
    durations_days=[1],
    source=(
        "India Meteorological Department rainfall categories: 'heavy rain' is 64.5-115.5 mm in 24 hours. "
        "A rainfall category, not a landslide-specific threshold."
    ),
    verified_against_primary_text=False,  # confirmed from several published summaries, not IMD's own page
)


def get_rainfall_threshold(state: str) -> RainfallThresholdConfig:
    """This state's own configured threshold if it has one, else the IMD baseline. Never
    another state's number."""
    per_state = settings.rainfall_thresholds.get(state.lower())
    if per_state is not None:
        return per_state
    # Backward-compat: Sikkim's threshold has always lived in the single original
    # field (still true in production today), not the per-state dict.
    if state == "Sikkim" and settings.rainfall_threshold is not None:
        return settings.rainfall_threshold
    return IMD_HEAVY_RAIN
