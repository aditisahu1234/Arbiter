"""Authentication endpoints."""
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.core.security import (
    create_access_token,
    verify_password,
    hash_password,
    get_current_user,
)
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    username: str
    is_active: bool = True


@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login endpoint. In production, verify against database."""
    # For now, accept any username/password (demo mode)
    # In production, this would query the User table
    expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": form_data.username})
    
    return TokenResponse(
        access_token=access_token,
        expires_in=int(expires.total_seconds()),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user info."""
    return UserResponse(username=current_user.get("sub", "unknown"))


@router.post("/register", response_model=UserResponse)
async def register(
    username: str,
    password: str,
):
    """Register a new user. In production, hash and store in database."""
    # For demo: accept any registration
    return UserResponse(username=username)


def require_auth():
    """Dependency to require authentication on endpoints."""
    return Depends(get_current_user)
