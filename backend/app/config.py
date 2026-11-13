"""Application settings, loaded from environment variables (prefix ``SEO_``) or a ``.env`` file."""
from __future__ import annotations

import contextlib
import os
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
    allow_registration: bool = False  # the very first account can always be created; set true to let others sign up
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    api_rate_limit_per_minute: int = 600
    login_rate_limit_per_minute: int = 10
    max_upload_mb: int = 20
    max_json_body_kb: int = 1024  # request bodies other than file uploads
    trusted_proxies: str = ""  # comma-separated IPs/CIDRs of reverse proxies whose X-Forwarded-For is believed
    enable_api_docs: bool = True  # Swagger UI / ReDoc under /api/docs and /api/redoc

    # Crawler safety
    allow_private_networks: bool = False  # set true only to audit sites on localhost / LAN
    user_agent: str = "UltimateSEOToolkit/0.1 (+https://github.com/ultimate-open-source-seo-toolkit)"
    crawl_max_urls_hard_limit: int = 200_000
    crawl_max_body_mb: int = 8
    max_concurrent_jobs: int = 3
    render_sandbox: bool = True  # Chromium sandbox for JavaScript rendering; set false only where it cannot start (some containers)
    max_jobs_per_user: int = 8  # queued + running background jobs per account

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
            # Owner-only permissions from the first byte (no window in which other local users can read it).
            try:
                fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                pass  # another process created it between the check and now
            else:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(secrets.token_urlsafe(48))
        with contextlib.suppress(OSError):
            f.chmod(0o600)
        return f.read_text(encoding="utf-8").strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
