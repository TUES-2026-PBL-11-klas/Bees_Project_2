"""
Authentication primitives (issue #89).

* Password hashing — PBKDF2-HMAC-SHA256 with per-user salt. Chosen over
  bcrypt to avoid a native build dep and because pbkdf2_hmac is in the
  Python stdlib.
* JWT issue/verify — PyJWT HS256, signed with settings.JWT_SECRET.

The token payload carries ``sub`` (user id), ``cid`` (company id), and
``role`` so the auth dependency can authorise without a DB lookup on
every request (still re-validates the user exists + is active).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, TypedDict

import jwt

from src.core.config import settings


_PBKDF2_ITERATIONS = 200_000
_SALT_BYTES = 16


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Return a stored-hash string of the form ``pbkdf2_sha256$iter$salt_hex$hash_hex``."""
    salt = os.urandom(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iter_s, salt_hex, hash_hex = stored.split("$", 3)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    try:
        iterations = int(iter_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except ValueError:
        return False
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(derived, expected)


# ---------------------------------------------------------------------------
# JWT issue / verify
# ---------------------------------------------------------------------------


class TokenPayload(TypedDict, total=False):
    sub: str
    cid: str
    role: str
    exp: int
    iat: int
    jti: str


def issue_access_token(
    *, user_id: str, company_id: str, role: str,
    expires_minutes: Optional[int] = None,
) -> str:
    exp_minutes = expires_minutes or settings.JWT_EXPIRES_MINUTES
    now = datetime.now(timezone.utc)
    payload: TokenPayload = {
        "sub": user_id,
        "cid": company_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=exp_minutes)).timestamp()),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> TokenPayload:
    """Decode + verify a JWT, raising ``jwt.PyJWTError`` on any failure."""
    return jwt.decode(
        token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
    )
