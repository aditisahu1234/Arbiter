"""Backtest endpoints."""
from typing import Any
from fastapi import APIRouter, Query, HTTPException
import pandas as pd

from app.core.database import db_manager
from app.data.storage import storage_manager
from app.models.asset import Asset
from app.quant.backtesting import BacktestEngine
from app.quant.strategies import StrategyConfig
from app.quant.costs import get_default_cost_model

router = APIRouter(prefix="/strategies", tags=["Strategies"])


@router.post("/backtest")
async def run_backtest(
    symbol: str = Query(..., description="Asset symbol"),
    fast_sma: int = Query(10, ge=2, le=200),
    slow_sma: int = Query(50, ge=5, le=500),
    atr_window: int = Query(14, ge=2, le=100),
    atr_mult: float = Query(3.0, ge=0.5, le=10.0),
    cost_bps: float = Query(10.0, ge=0.0, le=100.0),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
) -> dict[str, Any]:
    df = storage_manager.load_normalized_ohlcv(symbol.upper(), start_date, end_date)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {symbol.upper()}")

    cfg = StrategyConfig(
        fast_sma=fast_sma, slow_sma=slow_sma,
        atr_window=atr_window, atr_multiplier=atr_mult,
        cost_bps=cost_bps,
    )
    engine = BacktestEngine(cfg)
    result = engine.run(df, symbol.upper())

    return {
        "symbol": symbol.upper(),
        "config": {
            "fast_sma": cfg.fast_sma, "slow_sma": cfg.slow_sma,
            "atr_window": cfg.atr_window, "atr_multiplier": cfg.atr_multiplier,
            "cost_bps": cfg.cost_bps,
        },
        "metrics": result.metrics,
        "trades": result.trades,
        "equity_curve": {
            "gross": [{"time": str(t), "equity": float(e)} for t, e in result.equity_curve_gross.items()],
            "net": [{"time": str(t), "equity": float(e)} for t, e in result.equity_curve_net.items()],
        },
    }
