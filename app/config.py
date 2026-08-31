from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:5432/landslide_ews"
    open_meteo_base_url: str = "https://api.open-meteo.com/v1/forecast"

    # Literature-sourced rainfall intensity-duration threshold for alert triggering.
    # Placeholder default — replace with the team's cited source before demo.
    rainfall_alert_threshold_mm_per_hour: float = 20.0


settings = Settings()
