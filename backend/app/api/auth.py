"""Authentication endpoints."""
from __future__ import annotations

import threading

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import APP_NAME, APP_VERSION, get_settings
from ..db import get_db
from ..models import User
from ..security.auth import access_token_for, current_user, hash_password, optional_user, verify_password
from ..security.ratelimit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])
_DUMMY_HASH = hash_password("not-a-real-password")
# Creating the first account and counting accounts must be one step, or two simultaneous first
# registrations could both become administrators. (One worker process by design; see ADR-003.)
_register_lock = threading.Lock()
FAIL_WINDOW_S = 900.0
FAIL_LIMIT = 20  # failed sign-ins per account per window, on top of the per-address limit


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class LoginBody(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=200)


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


def _user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "is_admin": u.is_admin, "created_at": u.created_at.isoformat()}


@router.get("/status")
def status(db: Session = Depends(get_db), viewer: User | None = Depends(optional_user)) -> dict:
    """Public: tells the UI whether to show first-run setup or the login form."""
    users = db.scalar(select(func.count()).select_from(User)) or 0
    s = get_settings()
    out = {"app": APP_NAME, "version": APP_VERSION, "has_users": users > 0, "registration_open": users == 0 or s.allow_registration}
    if viewer is not None:  # how the crawler's network guard is configured is not for anonymous callers
        out["private_networks_allowed"] = s.allow_private_networks
    return out


@router.post("/register", status_code=201)
def register(body: Credentials, db: Session = Depends(get_db)) -> dict:
    email = body.email.lower()
    with _register_lock:
        users = db.scalar(select(func.count()).select_from(User)) or 0
        if users > 0 and not get_settings().allow_registration:
            raise HTTPException(403, "Registration is disabled on this instance")
        if db.scalar(select(User).where(User.email == email)):
            raise HTTPException(409, "An account with this email already exists")
        user = User(email=email, password_hash=hash_password(body.password), is_admin=users == 0)
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "An account with this email already exists") from None
    return {"access_token": access_token_for(user), "token_type": "bearer", "user": _user_out(user)}


@router.post("/login")
def login(body: LoginBody, db: Session = Depends(get_db)) -> dict:
    email = body.email.lower().strip()
    fail_key = f"fail:{email}"
    if limiter.count(fail_key, FAIL_WINDOW_S) >= FAIL_LIMIT:
        raise HTTPException(429, "Too many failed sign-in attempts for this account. Try again in a few minutes.",
                            headers={"Retry-After": "300"})
    user = db.scalar(select(User).where(User.email == email))
    # Always run one hash verification so response time does not reveal whether the account exists.
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok or not user.is_active:
        limiter.hit(fail_key, FAIL_WINDOW_S)
        raise HTTPException(401, "Incorrect email or password")
    limiter.clear(fail_key)
    return {"access_token": access_token_for(user), "token_type": "bearer", "user": _user_out(user)}


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return _user_out(user)


@router.post("/password")
def change_password(body: PasswordChange, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    row = db.get(User, user.id)
    row.password_hash = hash_password(body.new_password)
    db.commit()
    # Tokens issued before this moment stop working; hand the caller a fresh one so this session continues.
    return {"ok": True, "access_token": access_token_for(row), "token_type": "bearer"}
