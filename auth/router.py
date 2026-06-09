"""
auth/router.py — /auth/* endpoints.

Public (no auth required):
    POST /auth/login
    POST /auth/refresh

All other endpoints require JWT.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from config.settings import config
from db.models import User
from db.session import get_db

log = logging.getLogger(__name__)

# ── Auth security scheme ─────────────────────────────────────────────────────

security = HTTPBearer(auto_error=False)

# In-memory rate limiter: {ip: [timestamps]}
_login_attempts: dict[str, list[float]] = {}
_MAX_ATTEMPTS = 5
_WINDOW_SEC = 15 * 60

router = APIRouter(prefix="/auth")


# ── Rate limit helpers ────────────────────────────────────────────────────────

def _is_rate_limited(ip: str) -> bool:
    now = time.time()
    timestamps = _login_attempts.get(ip, [])
    _login_attempts[ip] = [t for t in timestamps if now - t < _WINDOW_SEC]
    return len(_login_attempts[ip]) >= _MAX_ATTEMPTS


def _record_attempt(ip: str) -> None:
    _login_attempts.setdefault(ip, []).append(time.time())


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── Request models ────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserCreateRequest(BaseModel):
    username: str
    password: str
    is_admin: bool = False


# ── Current-user FastAPI dependency ──────────────────────────────────────────

async def _get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency: extracts Bearer token from Authorization header,
    validates it, and returns the User. Raises 401 on any failure.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Not authenticated"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return get_current_user(credentials.credentials, db)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/login")
async def login(
    request: Request,
    body: LoginRequest,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """
    Authenticate user. Rate-limited: 5 failures per IP per 15 minutes.

    Request body: { "username": str, "password": str }

    Returns: { access_token, refresh_token, token_type: "bearer", username, is_admin }

    Frontend stores access_token in window.authToken (memory only),
    refresh_token in sessionStorage (cleared on tab close).
    """
    ip = _client_ip(request)

    if _is_rate_limited(ip):
        log.warning("Login rate-limited: ip=%s", ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "Too many login attempts. Please wait 15 minutes."},
        )

    user = db.query(User).filter(User.username == body.username).first()

    if user is None or not verify_password(body.password, user.hashed_password):
        _record_attempt(ip)
        log.warning("Failed login: username=%s ip=%s", body.username, ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Invalid username or password"},
        )

    if not user.is_active:
        log.warning("Login blocked — inactive user: username=%s ip=%s", body.username, ip)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Account is disabled"},
        )

    # ── Success ──
    _login_attempts.pop(ip, None)
    user.last_login = datetime.utcnow()
    db.flush()

    token_data = {"sub": user.username}
    access = create_access_token(token_data)
    refresh = create_refresh_token(token_data)

    log.info("Login: username=%s ip=%s", body.username, ip)

    return JSONResponse({
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "username": user.username,
        "is_admin": user.role == "admin",
    })


@router.post("/refresh")
async def refresh(
    body: RefreshRequest,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """
    Exchange a valid refresh token for a new access token.

    Request body: { "refresh_token": str }

    Returns: { access_token, token_type: "bearer" }
    """
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Invalid token type"},
        )

    username: Optional[str] = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail={"error": "Invalid token"})

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail={"error": "User not found or inactive"})

    access = create_access_token({"sub": user.username})
    log.info("Token refresh: username=%s", username)

    return JSONResponse({
        "access_token": access,
        "token_type": "bearer",
    })


@router.post("/logout")
async def logout() -> JSONResponse:
    """
    Client-side logout. Access tokens are stateless — server just confirms.
    Frontend must clear window.authToken and sessionStorage.removeItem('refresh_token').
    """
    return JSONResponse({"message": "logged out"})


@router.get("/me")
async def me(
    current_user: User = Depends(_get_current_user),
) -> dict:
    """Return current authenticated user info — never returns hashed_password."""
    return {
        "username": current_user.username,
        "is_admin": current_user.role == "admin",
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
    }


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """
    Change current user's password. Requires current password for verification.
    """
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Current password is incorrect"},
        )

    if len(body.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "New password must be at least 6 characters"},
        )

    current_user.hashed_password = hash_password(body.new_password)
    db.flush()
    log.info("Password changed: username=%s", current_user.username)

    return JSONResponse({"message": "Password changed successfully"})


@router.post("/users")
async def create_user(
    body: UserCreateRequest,
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Admin-only: create a new user."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Admin access required"},
        )

    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": f"User '{body.username}' already exists"},
        )

    user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
        role="admin" if body.is_admin else "trader",
        is_active=True,
    )
    db.add(user)
    db.flush()
    log.info("User created: username=%s by=%s role=%s", body.username, current_user.username, user.role)

    return JSONResponse({
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "is_active": user.is_active,
    }, status_code=status.HTTP_201_CREATED)
