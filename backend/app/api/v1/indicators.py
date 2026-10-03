"""Indicator endpoints: SMA, ATR."""
from typing import Any
from fastapi import APIRouter, Query
import pandas as pd

from app.data.storage import storage_manager
from app.quant.indicators import SimpleMovingAverage, AverageTrueRange

router = APIRouter(prefix="/indicators", tags=["Indicators"])


@router.get("/sma")
async def get_sma(
    symbol: str = Query(..., description="Asset symbol"),
    window: int = Query(20, ge=2, le=200, description="SMA window"),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
) -> dict[str, Any]:
    df = storage_manager.load_normalized_ohlcv(symbol, start_date, end_date)
    if df.empty:
        return {"symbol": symbol.upper(), "indicator": "sma", "window": window, "data": [], "message": "No data"}
    sma = SimpleMovingAverage(window).compute(df)
    result = pd.concat([df["timestamp"], sma], axis=1)
    result.columns = ["timestamp", "sma"]
    result = result.dropna()
    return {
        "symbol": symbol.upper(),
        "indicator": "sma",
        "window": window,
        "count": len(result),
        "data": [{"time": str(r["timestamp"])[:10], "sma": float(r["sma"])} for _, r in result.iterrows()],
    }


@router.get("/atr")
async def get_atr(
    symbol: str = Query(..., description="Asset symbol"),
    window: int = Query(14, ge=2, le=100, description="ATR window"),
    smoothing: str = Query("rma", regex="^(rma|sma|ema)$"),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
) -> dict[str, Any]:
    df = storage_manager.load_normalized_ohlcv(symbol, start_date, end_date)
    if df.empty:
        return {"symbol": symbol.upper(), "indicator": "atr", "data": [], "message": "No data"}
    atr = AverageTrueRange(window, smoothing).compute(df)
    result = pd.concat([df["timestamp"], atr], axis=1)
    result.columns = ["timestamp", "atr"]
    result = result.dropna()
    return {
        "symbol": symbol.upper(),
        "indicator": "atr",
        "window": window,
        "smoothing": smoothing,
        "count": len(result),
        "data": [{"time": str(r["timestamp"])[:10], "atr": float(r["atr"])} for _, r in result.iterrows()],
    }
