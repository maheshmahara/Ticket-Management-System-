from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    cors_origins: str = ""

    # --- Notifications (SMS + Email for high/urgent priority tickets) ---
    # See docs/BACKEND_ARCHITECTURE.md "Notifications" section.

    notifications_enabled: bool = True
    # Priorities that trigger SMS + Email alerts, comma-separated.
    notify_priorities: str = "high,urgent"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "notifications@hnbg.example"
    smtp_use_tls: bool = True

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def notify_priority_list(self) -> list[str]:
        return [p.strip().lower() for p in self.notify_priorities.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
