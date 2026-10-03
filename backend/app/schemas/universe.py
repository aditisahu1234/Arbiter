from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.asset import AssetResponse


class UniverseBase(BaseModel):
    name: str = Field(..., description="Unique machine identifier for universe (e.g. NIFTY50)")
    display_name: str = Field(..., description="Human readable title (e.g. NIFTY 50 Index)")
    description: str | None = Field(
        None, description="Detailed description of universe methodology"
    )
    is_active: bool = Field(
        True, description="Whether universe is active for ingestion and screening"
    )


class UniverseCreate(UniverseBase):
    pass


class UniverseMemberResponse(BaseModel):
    id: int
    universe_id: int
    asset_id: int
    weight: float | None = None
    added_at: datetime
    asset: AssetResponse

    model_config = ConfigDict(from_attributes=True)


class UniverseResponse(UniverseBase):
    id: int
    created_at: datetime
    updated_at: datetime
    member_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class UniverseDetailResponse(UniverseResponse):
    members: list[UniverseMemberResponse] = []
