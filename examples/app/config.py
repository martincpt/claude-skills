"""Configs for the My Project package."""

import sys
import tomllib
from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings class."""

    # ---- Pydantic Config ----
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- App Settings ----
    debug: bool = False
    host: str = "0.0.0.0"  # noqa: S104
    port: int = 8000
    log_level: str = "info"
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "fastapi-template"
    sql_uri: str = "sqlite+aiosqlite:///db.sqlite3"
    language: str = "hu"
    api_prefix: str = ""
    api_use_camel_case: bool = False
    frontend_url: str = ""
    is_testing: bool = "pytest" in sys.modules
    document_model_modules: list[str] = [
        "app.auth.fastapi_users.models",
        "app.crud.handlers.beanie.models",
    ]


@lru_cache
def get_settings() -> Settings:
    """Settings factory."""
    return Settings()


@lru_cache
def get_pyproject() -> dict[str, Any]:
    """Get the pyproject.toml file."""
    with open("pyproject.toml", "rb") as f:
        return tomllib.load(f)


# ---- Globals ----
settings = get_settings()
pyproject = get_pyproject()
