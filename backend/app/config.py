from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

_ENV_FILE = Path(__file__).parent.parent / ".env"
_CONFIG_FILE = Path(__file__).parent.parent / "config.yaml"


class YamlSettingsSource(PydanticBaseSettingsSource):
    """Loads non-secret config from config.yaml."""

    def __init__(self, settings_cls: type[BaseSettings], path: Path) -> None:
        super().__init__(settings_cls)
        self._data: dict[str, Any] = {}
        if path.exists():
            with open(path) as f:
                self._data = yaml.safe_load(f) or {}

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        value = self._data.get(field_name)
        return value, field_name, False

    def __call__(self) -> dict[str, Any]:
        return {k: v for k, v in self._data.items() if v is not None}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Secrets (from .env only) ───────────────────────────────────────────
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    finnhub_api_key: str | None = None
    marketaux_api_key: str | None = None
    tavily_api_key: str | None = None

    # ── Config (from config.yaml) ──────────────────────────────────────────
    default_provider: str = "openai"
    default_model: str = "gpt-4o-mini"
    news_sources: list[str] = ["finnhub"]
    app_debug: bool = False

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            dotenv_settings,                                   # .env  → secrets
            YamlSettingsSource(settings_cls, _CONFIG_FILE),   # config.yaml → settings
        )

    # ── Helpers ────────────────────────────────────────────────────────────

    def news_api_keys(self) -> dict[str, str]:
        mapping = {
            "finnhub": self.finnhub_api_key,
            "marketaux": self.marketaux_api_key,
        }
        return {k: v for k, v in mapping.items() if v}


@lru_cache
def get_settings() -> Settings:
    return Settings()
