"""Authentication tests."""
import pytest
from datetime import datetime, timedelta, timezone

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    get_current_user,
)
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials


class TestPasswordHashing:
    @pytest.mark.skip(reason="bcrypt compatibility issue in test environment")
    def test_hash_and_verify(self):
        password = "test"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)
        assert not verify_password("wrong", hashed)

    @pytest.mark.skip(reason="bcrypt compatibility issue in test environment")
    def test_different_hashes_same_password(self):
        password = "test"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2  # bcrypt generates different salts
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)


class TestJWT:
    def test_create_and_decode_token(self):
        token = create_access_token(data={"sub": "test_user"})
        payload = decode_access_token(token)
        assert payload["sub"] == "test_user"
        assert "exp" in payload

    def test_token_expires(self):
        token = create_access_token(
            data={"sub": "test_user"},
            expires_delta=timedelta(minutes=-1)  # Expired
        )
        with pytest.raises(Exception):  # JWT expiring raises exception
            decode_access_token(token)

    def test_invalid_token(self):
        with pytest.raises(HTTPException):
            decode_access_token("invalid.token.here")
