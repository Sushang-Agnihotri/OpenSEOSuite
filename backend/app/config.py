"""Application settings, loaded from environment variables (prefix ``SEO_``) or a ``.env`` file."""
from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_NAME = "Ultimate Open-Source SEO Toolkit"
APP_VERSION = "0.1.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SEO_", extra="ignore")

    # Storage
    data_dir: str = "./data"
    database_url: str = ""  # default: sqlite file inside data_dir

    # Security
    secret_key: str = ""  # default: generated once and stored in data_dir/.secret_key
    access_token_minutes: int = 720
    allow_registration: bool = True  # the very first account can always be created
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    api_rate_limit_per_minute: int = 600
    login_rate_limit_per_minute: int = 10
    max_upload_mb: int = 20

    # Crawler safety
    allow_private_networks: bool = False  # set true only to audit sites on localhost / LAN
    user_agent: str = "UltimateSEOToolkit/0.1 (+https://github.com/ultimate-open-source-seo-toolkit)"
    crawl_max_urls_hard_limit: int = 200_000
    crawl_max_body_mb: int = 8
    max_concurrent_jobs: int = 3

    # Misc
    public_base_url: str = "http://localhost:8000"  # used for OAuth redirect URIs
    frontend_dist: str = "../frontend/dist"
    scheduler_enabled: bool = True
    log_level: str = "INFO"
    log_json: bool = False

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_path / 'seotoolkit.db').as_posix()}"

    @property
    def jwt_secret(self) -> str:
        if self.secret_key:
            return self.secret_key
        f = self.data_path / ".secret_key"
        if not f.exists():
            f.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        return f.read_text(encoding="utf-8").strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
