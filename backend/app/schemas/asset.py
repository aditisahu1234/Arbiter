from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AssetBase(BaseModel):
    symbol: str = Field(..., description="Canonical ticker symbol (e.g. TCS, RELIANCE, INFY)")
    exchange: str = Field("NSE", description="Exchange code (e.g. NSE, BSE)")
    name: str = Field(..., description="Full legal name of company or instrument")
    asset_type: str = Field("EQUITY", description="Asset class (e.g. EQUITY, ETF, INDEX)")
    currency: str = Field("INR", description="Trading currency")
    country: str = Field("IN", description="Country code ISO-3166")
    sector: str | None = Field(None, description="Industry sector classification")
    industry: str | None = Field(None, description="Detailed industry subcategory")
    isin: str | None = Field(None, description="ISIN identifier")
    provider_symbol: str = Field(..., description="Vendor ticker symbol (e.g. TCS.NS)")
    active: bool = Field(True, description="Whether the asset is currently active")


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    isin: str | None = None
    provider_symbol: str | None = None
    active: bool | None = None


class AssetResponse(AssetBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssetFilter(BaseModel):
    search: str | None = None
    exchange: str | None = None
    sector: str | None = None
    active_only: bool = True
    universe: str | None = None
    skip: int = 0
    limit: int = 100
