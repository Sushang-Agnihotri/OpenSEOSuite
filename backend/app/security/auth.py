"""Password hashing (Argon2id), JWT access tokens and FastAPI auth dependencies."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Site, User

_hasher = PasswordHasher()
_bearer = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (Argon2Error, InvalidHashError):
        return False


def password_version(user: User) -> str:
    """Fingerprint of the current password hash. Embedded in access tokens, so changing the password
    invalidates every token issued before it (there is no other server-side session state)."""
    return hashlib.sha256(user.password_hash.encode("utf-8")).hexdigest()[:16]


def create_access_token(user_id: int, purpose: str = "access", minutes: int | None = None, **claims) -> str:
    s = get_settings()
    exp = datetime.now(UTC) + timedelta(minutes=minutes or s.access_token_minutes)
    return jwt.encode({**claims, "sub": str(user_id), "exp": exp, "typ": purpose}, s.jwt_secret, algorithm=ALGORITHM)


def access_token_for(user: User) -> str:
    return create_access_token(user.id, pv=password_version(user))


def decode_payload(token: str, purpose: str = "access") -> dict:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
        if payload.get("typ") != purpose:
            raise jwt.InvalidTokenError("wrong token type")
        int(payload["sub"])
        return payload
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc


def decode_token(token: str, purpose: str = "access") -> int:
    return int(decode_payload(token, purpose)["sub"])


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    payload = decode_payload(creds.credentials)
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found or disabled")
    if payload.get("pv") != password_version(user):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session ended: the password was changed. Sign in again.")
    return user


def optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> User | None:
    """The signed-in user, or None for anonymous callers and invalid tokens (never raises)."""
    try:
        return current_user(creds, db) if creds else None
    except HTTPException:
        return None


def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return user


def get_site_for(db: Session, user: User, site_id: int) -> Site:
    """Return the site if the user owns it. Other users' sites look like they do not exist."""
    site = db.get(Site, site_id)
    if site is None or site.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Site not found")
    return site
