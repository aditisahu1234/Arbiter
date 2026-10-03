from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.duckdb import duckdb_manager
from app.data.storage import storage_manager
from app.schemas.asset import AssetFilter
from app.services.asset_service import asset_service

router = APIRouter(prefix="/assets", tags=["Assets"])


@router.get("", response_model=dict[str, Any])
async def list_assets(
    search: str | None = Query(None, description="Search symbol or company name"),
    sector: str | None = Query(None, description="Filter by sector"),
    universe: str | None = Query(None, description="Filter by universe (e.g. NIFTY50, NIFTY_BANK)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List assets with filtering, pagination, and lakehouse data status."""
    filter_params = AssetFilter(
        search=search,
        sector=sector,
        universe=universe,
        skip=skip,
        limit=limit,
    )
    assets, total = await asset_service.list_assets(db, filter_params)

    # Check which assets have Parquet data in the lakehouse
    items = []
    for a in assets:
        p_path = storage_manager.get_asset_parquet_path(a.symbol)
        has_data = p_path.exists()
        latest_ts = duckdb_manager.get_latest_timestamp(a.symbol) if has_data else None

        items.append(
            {
                "id": a.id,
                "symbol": a.symbol,
                "name": a.name,
                "exchange": a.exchange,
                "sector": a.sector,
                "industry": a.industry,
                "provider_symbol": a.provider_symbol,
                "has_data": has_data,
                "latest_date": latest_ts.strftime("%Y-%m-%d") if latest_ts is not None else None,
            }
        )

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": items,
    }


@router.get("/{identifier}")
async def get_asset(
    identifier: str,
    db: AsyncSession = Depends(get_db),
):
    """Get single asset by ID or Symbol."""
    if identifier.isdigit():
        asset = await asset_service.get_by_id(db, int(identifier))
    else:
        asset = await asset_service.get_by_symbol(db, identifier)

    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset '{identifier}' not found")

    p_path = storage_manager.get_asset_parquet_path(asset.symbol)
    has_data = p_path.exists()
    latest_ts = duckdb_manager.get_latest_timestamp(asset.symbol) if has_data else None

    return {
        "id": asset.id,
        "symbol": asset.symbol,
        "name": asset.name,
        "exchange": asset.exchange,
        "currency": asset.currency,
        "country": asset.country,
        "sector": asset.sector,
        "industry": asset.industry,
        "provider_symbol": asset.provider_symbol,
        "active": asset.active,
        "has_data": has_data,
        "latest_date": latest_ts.strftime("%Y-%m-%d") if latest_ts is not None else None,
    }


@router.get("/{symbol}/ohlcv")
async def get_asset_ohlcv(
    symbol: str,
    start_date: str | None = Query(None, description="Start date YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date YYYY-MM-DD"),
    limit: int | None = Query(1500, description="Max bars to return"),
):
    """Get historical OHLCV data from DuckDB / Parquet lakehouse."""
    df = storage_manager.load_normalized_ohlcv(
        symbol=symbol.upper(),
        start_date=start_date,
        end_date=end_date,
    )

    if df.empty:
        return {
            "symbol": symbol.upper(),
            "count": 0,
            "data": [],
            "message": "No data ingested yet for this asset. Use /api/v1/market-data/ingest/{symbol} to fetch.",
        }

    if limit and len(df) > limit:
        df = df.tail(limit)

    # Format timestamp as YYYY-MM-DD string for TradingView chart compatibility
    records = []
    for _, row in df.iterrows():
        ts = row["timestamp"]
        time_str = ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)[:10]
        records.append(
            {
                "time": time_str,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "adjusted_close": float(row["adjusted_close"]),
                "volume": int(row["volume"]),
            }
        )

    return {
        "symbol": symbol.upper(),
        "count": len(records),
        "first_date": records[0]["time"] if records else None,
        "last_date": records[-1]["time"] if records else None,
        "data": records,
    }


@router.get("/{symbol}/latest")
async def get_asset_latest_bar(symbol: str):
    """Get the latest daily bar with price and volume change."""
    df = storage_manager.load_normalized_ohlcv(symbol=symbol.upper())
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No market data available for '{symbol}'")

    last_bar = df.iloc[-1]
    prev_bar = df.iloc[-2] if len(df) > 1 else last_bar

    change = float(last_bar["close"]) - float(prev_bar["close"])
    pct_change = (
        (change / float(prev_bar["close"]) * 100.0) if float(prev_bar["close"]) > 0 else 0.0
    )

    return {
        "symbol": symbol.upper(),
        "date": str(last_bar["timestamp"])[:10],
        "open": float(last_bar["open"]),
        "high": float(last_bar["high"]),
        "low": float(last_bar["low"]),
        "close": float(last_bar["close"]),
        "adjusted_close": float(last_bar["adjusted_close"]),
        "volume": int(last_bar["volume"]),
        "change": round(change, 2),
        "pct_change": round(pct_change, 2),
    }
