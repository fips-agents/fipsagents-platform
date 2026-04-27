"""Settings loaded from environment.

Single source of truth for backend selection, auth mode, and connection
strings. Validated at startup; misconfiguration fails loudly rather than
silently degrading.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PLATFORM_",
        env_file=".env",
        extra="ignore",
    )

    backend: Literal["sqlite", "postgres"] = "sqlite"
    sqlite_path: str = "./platform.db"
    database_url: str = ""

    auth_mode: Literal["none", "keycloak"] = "none"
    keycloak_issuer: str = ""
    keycloak_audience: str = ""
    keycloak_jwks_cache_seconds: int = 300

    log_level: str = "INFO"

    @model_validator(mode="after")
    def _check_backend(self) -> "Settings":
        if self.backend == "postgres" and not self.database_url:
            raise ValueError(
                "PLATFORM_BACKEND=postgres requires PLATFORM_DATABASE_URL"
            )
        return self

    @model_validator(mode="after")
    def _check_auth(self) -> "Settings":
        if self.auth_mode == "keycloak":
            if not self.keycloak_issuer:
                raise ValueError(
                    "PLATFORM_AUTH_MODE=keycloak requires PLATFORM_KEYCLOAK_ISSUER"
                )
            if not self.keycloak_audience:
                raise ValueError(
                    "PLATFORM_AUTH_MODE=keycloak requires PLATFORM_KEYCLOAK_AUDIENCE"
                )
        return self


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings_for_tests() -> None:
    """Force re-read of environment in tests."""
    global _settings
    _settings = None
