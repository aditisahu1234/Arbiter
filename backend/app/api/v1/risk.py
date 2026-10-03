"""Risk analysis endpoints: CAPM and Fama-French."""
from typing import Any
from fastapi import APIRouter, Query, HTTPException
import pandas as pd
import numpy as np

from app.data.storage import storage_manager
from app.quant.risk import CAPMEngine, FamaFrenchEngine

router = APIRouter(prefix="/risk", tags=["Risk"])


@router.get("/capm")
async def get_capm(
    symbol: str = Query(..., description="Asset symbol"),
    market_symbol: str = Query("^NSEI", description="Market benchmark (default NIFTY 50)"),
    risk_free_annual: float = Query(6.5, ge=0.0, le=20.0, description="Annual risk-free rate in %"),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
) -> dict[str, Any]:
    rf_daily = (1 + risk_free_annual / 100) ** (1 / 252) - 1

    asset_df = storage_manager.load_normalized_ohlcv(symbol.upper(), start_date, end_date)
    market_df = storage_manager.load_normalized_ohlcv(market_symbol, start_date, end_date)

    if asset_df.empty or market_df.empty:
        raise HTTPException(status_code=404, detail="Insufficient data for CAPM analysis")

    asset_df = asset_df.sort_values("timestamp").drop_duplicates("timestamp").set_index("timestamp")
    market_df = market_df.sort_values("timestamp").drop_duplicates("timestamp").set_index("timestamp")

    common_idx = asset_df.index.intersection(market_df.index)
    if len(common_idx) < 30:
        raise HTTPException(status_code=400, detail=f"Insufficient common observations: {len(common_idx)}")

    asset_ret = asset_df.loc[common_idx, "adjusted_close"].pct_change()
    market_ret = market_df.loc[common_idx, "adjusted_close"].pct_change()

    result = CAPMEngine.compute(asset_ret, market_ret, risk_free_daily=rf_daily)

    return {
        "symbol": symbol.upper(),
        "market": market_symbol,
        "risk_free_annual_pct": risk_free_annual,
        "risk_free_daily": round(rf_daily, 6),
        "observations": result.observations,
        "alpha": round(float(result.alpha) * 100, 6),
        "beta": round(float(result.beta), 4),
        "r_squared": round(float(result.r_squared), 4),
        "alpha_se": round(float(result.alpha_se) * 100, 6),
        "alpha_t_stat": round(float(result.alpha_t_stat), 4),
        "alpha_p_value": round(float(result.alpha_p_value), 6),
    }


@router.get("/fama-french")
async def get_fama_french(
    symbol: str = Query(..., description="Asset symbol"),
    market_symbol: str = Query("^NSEI", description="Market benchmark"),
    risk_free_annual: float = Query(6.5, ge=0.0, le=20.0),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
) -> dict[str, Any]:
    """Fama-French 3-factor with synthetic SMB/HML from NIFTY 500 constituents."""
    rf_daily = (1 + risk_free_annual / 100) ** (1 / 252) - 1

    asset_df = storage_manager.load_normalized_ohlcv(symbol.upper(), start_date, end_date)
    if asset_df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {symbol.upper()}")

    # Synthetic SMB/HML from price data
    df_all = storage_manager.load_normalized_ohlcv("^NSEI", start_date, end_date)
    market_ret = df_all.set_index("timestamp")["adjusted_close"].pct_change() if not df_all.empty else pd.Series()

    # Create synthetic size/value factors from universe segments
    # Use different assets as proxies
    all_symbols = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN",
                   "TATAMOTORS", "WIPRO", "ASIANPAINT", "ITC", "NTPC", "ONGC",
                   "MARUTI", "SUNPHARMA", "TITAN", "KOTAKBANK", "AXISBANK", "LT"]
    all_dfs = {}
    for sym in all_symbols:
        d = storage_manager.load_normalized_ohlcv(sym, start_date, end_date)
        if not d.empty:
            all_dfs[sym] = d.set_index("timestamp")["adjusted_close"].pct_change()

    if len(all_dfs) < 5:
        raise HTTPException(status_code=400, detail="Insufficient data for Fama-French factor computation")

    # Synthetic SMB: large-cap returns vs small-cap returns
    large_caps = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "NTPC", "ONGC", "LT"]
    small_caps = ["TATAMOTORS", "WIPRO", "SUNPHARMA", "MARUTI", "KOTAKBANK", "AXISBANK"]

    large_ret = pd.concat([all_dfs[s] for s in large_caps if s in all_dfs], axis=1).mean(axis=1)
    small_ret = pd.concat([all_dfs[s] for s in small_caps if s in all_dfs], axis=1).mean(axis=1)
    smb = small_ret - large_ret

    # Synthetic HML: value (high book-to-market proxy using low price) vs growth
    # Use IT (growth) vs FMCG (value) as proxy
    it_ret = all_dfs.get("WIPRO", pd.Series())
    fmcg_ret = all_dfs.get("ITC", pd.Series())
    hml = fmcg_ret - it_ret

    asset_ret = asset_df.set_index("timestamp")["adjusted_close"].pct_change()
    common_idx = asset_ret.index.intersection(market_ret.index).intersection(smb.index).intersection(hml.index)

    if len(common_idx) < 30:
        raise HTTPException(status_code=400, detail=f"Insufficient common observations: {len(common_idx)}")

    result = FamaFrenchEngine.compute(
        asset_ret.loc[common_idx],
        market_ret.loc[common_idx],
        smb.loc[common_idx],
        hml.loc[common_idx],
        risk_free_daily=rf_daily,
    )

    return {
        "symbol": symbol.upper(),
        "risk_free_annual_pct": risk_free_annual,
        "observations": result.observations,
        "alpha": round(float(result.alpha) * 100, 6),
        "beta_market": round(float(result.beta_market), 4),
        "beta_size": round(float(result.beta_size), 4),
        "beta_value": round(float(result.beta_value), 4),
        "r_squared": round(float(result.r_squared), 4),
        "alpha_se": round(float(result.alpha_se) * 100, 6),
        "alpha_t_stat": round(float(result.alpha_t_stat), 4),
        "alpha_p_value": round(float(result.alpha_p_value), 6),
    }
