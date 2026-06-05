"""Unit tests for password hashing + JWT issue/verify (#89)."""

import time

import jwt
import pytest

from src.core.config import settings
from src.core.security import (
    decode_access_token,
    hash_password,
    issue_access_token,
    verify_password,
)


def test_hash_password_is_not_plaintext():
    h = hash_password("hunter2")
    assert h != "hunter2"
    assert h.startswith("pbkdf2_sha256$")


def test_verify_password_round_trip():
    h = hash_password("hunter2")
    assert verify_password("hunter2", h) is True
    assert verify_password("hunter3", h) is False


def test_verify_password_rejects_malformed_hash():
    assert verify_password("any", "not-a-valid-hash") is False
    assert verify_password("any", "wrong_scheme$1$ab$cd") is False


def test_issue_token_contains_expected_claims():
    token = issue_access_token(
        user_id="u1", company_id="c1", role="admin",
    )
    payload = decode_access_token(token)
    assert payload["sub"] == "u1"
    assert payload["cid"] == "c1"
    assert payload["role"] == "admin"
    assert payload["exp"] > payload["iat"]


def test_decode_rejects_tampered_signature():
    token = issue_access_token(user_id="u1", company_id="c1", role="admin")
    parts = token.split(".")
    bad = ".".join([parts[0], parts[1], "0" * len(parts[2])])
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(bad)


def test_decode_rejects_expired_token(monkeypatch):
    token = issue_access_token(
        user_id="u1", company_id="c1", role="admin", expires_minutes=-1
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_token_uses_configured_algorithm():
    token = issue_access_token(user_id="u1", company_id="c1", role="admin")
    header = jwt.get_unverified_header(token)
    assert header["alg"] == settings.JWT_ALGORITHM
