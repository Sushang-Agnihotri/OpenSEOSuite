"""Authentication endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import APP_NAME, APP_VERSION, get_settings
from ..db import get_db
from ..models import User
from ..security.auth import create_access_token, current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
_DUMMY_HASH = hash_password("not-a-real-password")


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
def status(db: Session = Depends(get_db)) -> dict:
    """Public: tells the UI whether to show first-run setup or the login form."""
    users = db.scalar(select(func.count()).select_from(User)) or 0
    s = get_settings()
    return {"app": APP_NAME, "version": APP_VERSION, "has_users": users > 0,
            "registration_open": users == 0 or s.allow_registration, "private_networks_allowed": s.allow_private_networks}


@router.post("/register", status_code=201)
def register(body: Credentials, db: Session = Depends(get_db)) -> dict:
    users = db.scalar(select(func.count()).select_from(User)) or 0
    if users > 0 and not get_settings().allow_registration:
        raise HTTPException(403, "Registration is disabled on this instance")
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=email, password_hash=hash_password(body.password), is_admin=users == 0)
    db.add(user)
    db.commit()
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": _user_out(user)}


@router.post("/login")
def login(body: LoginBody, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.email == body.email.lower().strip()))
    # Always run one hash verification so response time does not reveal whether the account exists.
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok or not user.is_active:
        raise HTTPException(401, "Incorrect email or password")
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": _user_out(user)}


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return _user_out(user)


@router.post("/password")
def change_password(body: PasswordChange, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    db.get(User, user.id).password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}
