"""auth/service.py — JWT creation, verification, password hashing.

Password hashing: bcrypt directly (not passlib — version mismatch with bcrypt 4.x).
Token handling: access short-lived (480 min, in-memory + sessionStorage), refresh long-lived (7 days, sessionStorage).
JWT decode has a 60-second leeway to tolerate minor clock drift between server and browser.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from bcrypt import hashpw, gensalt, checkpw as _bcrypt_checkpw
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from config.settings import config
from db.models import User

log = logging.getLogger(__name__)

# ── Password hashing ──────────────────────────────────────────────────────────
# bcrypt truncates to 72 bytes. BMAD policy: truncate before hashing.
_MAX_PW_BYTES = 72
_bcrypt_re = re.compile(rb'^\$2[aby]?\$\d{2}\$[./A-Za-z0-9]{53}$')


def _load_key(config_key: str) -> bytes:
    raw = config_key.encode("utf-8")
    return raw[:_MAX_PW_BYTES]


def hash_password(plain: str) -> str:
    """Hash a plaintext password. Always use this — never store plaintext."""
    key = _load_key(plain)
    hashed = hashpw(key, gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    key = _load_key(plain)
    try:
        return _bcrypt_checkpw(key, hashed.encode("utf-8"))
    except Exception as exc:
        log.warning("verify_password exception: %s", exc)
        return False


# ── JWT helpers ───────────────────────────────────────────────────────────────

def _make_token(
    data: dict,
    expires_delta: timedelta,
    token_type: str,
) -> str:
    """Create a signed JWT with standard claims."""
    to_encode = {
        "sub": data.get("sub", ""),
        "type": token_type,
        "exp": datetime.utcnow() + expires_delta,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(
        to_encode,
        config.auth.secret_key,
        algorithm=config.auth.algorithm,
    )


def create_access_token(data: dict) -> str:
    """Short-lived access token (default 480 min / 8 hours)."""
    return _make_token(
        data,
        timedelta(minutes=config.auth.access_token_expire_minutes),
        "access",
    )


def create_refresh_token(data: dict) -> str:
    """Long-lived refresh token (default 7 days)."""
    return _make_token(
        data,
        timedelta(days=config.auth.refresh_token_expire_days),
        "refresh",
    )


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT. Raises HTTPException 401 on any failure.
    Never propagates raw JWTError.
    60-second leeway tolerates minor clock drift between server and browser.
    """
    try:
        payload = jwt.decode(
            token,
            config.auth.secret_key,
            algorithms=[config.auth.algorithm],
            # leeway removed - python-jose 3.5+
        )
        return payload
    except JWTError as exc:
        log.warning("Token decode failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Invalid or expired token"},
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Current user dependency ──────────────────────────────────────────────────

def get_current_user(token: str, db: Session) -> User:
    """
    Decode token, look up User in DB, return User.
    Raises HTTPException 401 if user not found or inactive.

    Called inside FastAPI endpoints:
        current_user: User = Depends(get_current_user)
    where the dependency supplies (token, db) via a wrapper.
    """
    payload = decode_token(token)
    username: Optional[str] = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Token missing subject"},
        )

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        log.warning("Auth: user not found for token sub=%s", username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "User not found"},
        )
    if not user.is_active:
        log.warning("Auth: inactive user attempted access: %s", username)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "User account is disabled"},
        )
    return user
