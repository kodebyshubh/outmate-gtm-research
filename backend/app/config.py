from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


def _is_set(value: str) -> bool:
    """A key counts as configured only if it is non-empty and not a placeholder."""
    v = (value or "").strip()
    return bool(v) and not v.upper().startswith("PASTE_")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    exa_api_key: str = ""
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    enrichment_provider: str = "none"  # none, mock or moltsets
    moltsets_api_key: str = ""
    moltsets_base_url: str = "https://api.moltsets.com/api/v1/tools"
    frontend_origin: str = "http://localhost:3000"

    exa_timeout_seconds: float = 12.0
    groq_timeout_seconds: float = 30.0
    moltsets_timeout_seconds: float = 15.0

    @property
    def exa_configured(self) -> bool:
        return _is_set(self.exa_api_key)

    @property
    def groq_configured(self) -> bool:
        return _is_set(self.groq_api_key)

    @property
    def moltsets_configured(self) -> bool:
        return _is_set(self.moltsets_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
