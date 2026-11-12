"""Instance-wide integration settings stored in the database (set from the Settings page).

Secrets are write-only through the API: reads return a masked placeholder. They are stored
unencrypted in the application database - protect the database file accordingly (see SECURITY.md).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Setting

SECRET_FIELDS = {"api_key", "client_secret", "access_token", "refresh_token", "tokens"}
MASK = "********"

DEFAULTS: dict[str, dict] = {
    "serp": {"provider": "none", "searxng_url": "", "google_cse_key": "", "google_cse_cx": "", "brave_key": ""},
    "pagespeed": {"api_key": ""},
    "ai": {"provider": "none", "base_url": "http://localhost:11434", "model": "llama3.1", "api_key": ""},
    "gsc": {"client_id": "", "client_secret": ""},
}
_SECRET_KEYS = {"serp": {"google_cse_key", "brave_key"}, "pagespeed": {"api_key"}, "ai": {"api_key"}, "gsc": {"client_secret"}}


def get_setting(db: Session, key: str) -> dict:
    row = db.get(Setting, key)
    value = dict(DEFAULTS.get(key, {}))
    if row and isinstance(row.value, dict):
        value.update(row.value)
    return value


def set_setting(db: Session, key: str, value: dict) -> dict:
    current = get_setting(db, key)
    for k, v in value.items():
        if k in _SECRET_KEYS.get(key, set()) and v == MASK:
            continue  # unchanged secret echoed back by the UI
        if key in DEFAULTS and k not in DEFAULTS[key]:
            continue
        current[k] = v
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=current))
    else:
        row.value = current
    db.flush()
    return current


def masked(key: str, value: dict) -> dict:
    out = dict(value)
    for k in _SECRET_KEYS.get(key, set()):
        if out.get(k):
            out[k] = MASK
    return out


def get_private(db: Session, key: str) -> dict:
    """Internal state that is never exposed through the settings API (OAuth tokens)."""
    row = db.get(Setting, f"_private:{key}")
    return dict(row.value) if row and isinstance(row.value, dict) else {}


def set_private(db: Session, key: str, value: dict) -> None:
    row = db.get(Setting, f"_private:{key}")
    if row is None:
        db.add(Setting(key=f"_private:{key}", value=value))
    else:
        row.value = value
    db.flush()
