"""Password hashing (Argon2id), JWT access tokens and FastAPI auth dependencies."""
from __future__ import annotations

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


def create_access_token(user_id: int, purpose: str = "access", minutes: int | None = None) -> str:
    s = get_settings()
    exp = datetime.now(UTC) + timedelta(minutes=minutes or s.access_token_minutes)
    return jwt.encode({"sub": str(user_id), "exp": exp, "typ": purpose}, s.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str, purpose: str = "access") -> int:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
        if payload.get("typ") != purpose:
            raise jwt.InvalidTokenError("wrong token type")
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user = db.get(User, decode_token(creds.credentials))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found or disabled")
    return user


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
