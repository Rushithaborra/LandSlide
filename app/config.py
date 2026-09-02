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

    # No default: the app must be told what threshold to use, from .env or
    # real env vars — see RAINFALL_THRESHOLD__* in .env.example. Startup
    # fails loudly rather than silently falling back to a guessed number.
    rainfall_threshold: RainfallThresholdConfig


settings = Settings()
