"""Authentication tests."""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from app.core.security import (
    create_access_token,
    decode_access_token,
)
from fastapi import HTTPException


class TestJWT:
    def test_create_and_decode_token(self):
        token = create_access_token(data={"sub": "test_user"})
        payload = decode_access_token(token)
        assert payload["sub"] == "test_user"
        assert "exp" in payload

    def test_token_expires(self):
        token = create_access_token(
            data={"sub": "test_user"},
            expires_delta=timedelta(minutes=-1)
        )
        with pytest.raises(Exception):
            decode_access_token(token)

    def test_invalid_token(self):
        with pytest.raises(HTTPException):
            decode_access_token("invalid.token.here")


class TestAuthEndpoints:
    """Test auth endpoints with in-memory user store."""

    @pytest.mark.asyncio
    async def test_login_success(self):
        """Test successful login returns token."""
        from httpx import ASGITransport, AsyncClient
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Login (demo mode accepts any credentials)
            login_res = await client.post("/api/v1/auth/login", data={"username": "testuser", "password": "testpass"})
            assert login_res.status_code == 200
            data = login_res.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_invalid_password(self):
        """Test login with invalid password - demo mode accepts any credentials."""
        from httpx import ASGITransport, AsyncClient
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Demo mode accepts any credentials
            login_res = await client.post("/api/v1/auth/login", data={"username": "testuser", "password": "wrongpass"})
            assert login_res.status_code == 200  # Demo mode

    @pytest.mark.asyncio
    async def test_protected_endpoint_without_token(self):
        """Test protected endpoint without auth token."""
        from httpx import ASGITransport, AsyncClient
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Backtest requires auth
            res = await client.post("/api/v1/strategies/backtest?symbol=RELIANCE")
            assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_protected_endpoint_with_token(self):
        """Test protected endpoint with valid token."""
        from httpx import ASGITransport, AsyncClient
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Login first
            login_res = await client.post("/api/v1/auth/login", data={"username": "test", "password": "test"})
            token = login_res.json()["access_token"]

            # Access protected endpoint
            res = await client.post(
                "/api/v1/strategies/backtest?symbol=RELIANCE",
                headers={"Authorization": f"Bearer {token}"}
            )
            # Should get 200 or 404 (no data), not 401
            assert res.status_code in [200, 404]
