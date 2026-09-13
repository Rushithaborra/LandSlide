from pydantic import BaseModel
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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:5432/landslide_ews"
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


settings = Settings()


def get_rainfall_threshold(state: str) -> RainfallThresholdConfig | None:
    per_state = settings.rainfall_thresholds.get(state.lower())
    if per_state is not None:
        return per_state
    # Backward-compat fallback: Sikkim's threshold has always lived in the
    # single original field (still true in production today), not the new
    # per-state dict.
    if state == "Sikkim":
        return settings.rainfall_threshold
    return None
