"""Risk analysis endpoints: CAPM and Fama-French."""
from typing import Any
from fastapi import APIRouter, Query, HTTPException
import pandas as pd
import numpy as np

from app.data.storage import storage_manager
from app.quant.risk import CAPMEngine, FamaFrenchEngine
from app.data.providers.ff3 import IndiaFF3ProviderFactory
from app.data.providers.risk_free import IndiaRiskFreeProviderFactory

router = APIRouter(prefix="/risk", tags=["Risk"])


@router.get("/capm")
async def get_capm(
    symbol: str = Query(..., description="Asset symbol"),
    market_symbol: str = Query("^NSEI", description="Market benchmark (default NIFTY 50)"),
    risk_free_source: str = Query("fallback", pattern="^(rbi|fallback)$", description="Risk-free rate source: rbi (requires data file) or fallback"),
    risk_free_annual: float = Query(6.5, ge=0.0, le=20.0, description="Annual risk-free rate in % (used for fallback)"),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
) -> dict[str, Any]:
    # Get risk-free rate
    if risk_free_source == "rbi":
        try:
            from app.data.providers.risk_free import RBITBillProvider
            provider = RBITBillProvider()
            rf_data = provider.get_rates(start_date, end_date)
            rf_daily = rf_data.rates.mean()
            rf_annual = rf_data.annualized
            rf_source = rf_data.source
        except Exception:
            # Fallback to constant
            from app.data.providers.risk_free import ConstantFallbackProvider
            provider = ConstantFallbackProvider(risk_free_annual)
            rf_data = provider.get_rates()
            rf_daily = rf_data.rates.mean()
            rf_annual = rf_data.annualized
            rf_source = rf_data.source
    else:
        from app.data.providers.risk_free import ConstantFallbackProvider
        provider = ConstantFallbackProvider(risk_free_annual)
        rf_data = provider.get_rates()
        rf_daily = rf_data.rates.mean()
        rf_annual = rf_data.annualized
        rf_source = rf_data.source

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
        "risk_free_source": rf_source.name,
        "risk_free_annual_pct": rf_annual,
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
    factor_source: str = Query("synthetic", pattern="^(iim_ahmedabad|synthetic)$", description="FF3 factor source: iim_ahmedabad (requires data) or synthetic"),
    risk_free_annual: float = Query(6.5, ge=0.0, le=20.0),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
) -> dict[str, Any]:
    """Fama-French 3-factor analysis with India-specific or synthetic factors."""
    # Get factors
    provider = IndiaFF3ProviderFactory.get_default(storage_manager)
    try:
        if factor_source == "iim_ahmedabad":
            ff3_data = provider.get_factors(start_date, end_date)
            factors_provenance = ff3_data.source
        else:
            # Use synthetic provider
            from app.data.providers.ff3 import SyntheticFF3Provider
            synth_provider = SyntheticFF3Provider(storage_manager)
            ff3_data = synth_provider.get_factors(start_date, end_date)
            factors_provenance = ff3_data.source
    except Exception as e:
        # Fallback to synthetic
        from app.data.providers.ff3 import SyntheticFF3Provider
        synth_provider = SyntheticFF3Provider(storage_manager)
        ff3_data = synth_provider.get_factors(start_date, end_date)
        factors_provenance = ff3_data.source

    rf_daily = (1 + risk_free_annual / 100) ** (1 / 252) - 1

    asset_df = storage_manager.load_normalized_ohlcv(symbol.upper(), start_date, end_date)
    if asset_df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {symbol.upper()}")

    asset_ret = asset_df.set_index("timestamp")["adjusted_close"].pct_change()

    # Align with factors
    common_idx = asset_ret.index.intersection(ff3_data.dates)
    if len(common_idx) < 30:
        raise HTTPException(status_code=400, detail=f"Insufficient common observations: {len(common_idx)}")

    result = FamaFrenchEngine.compute(
        asset_ret.loc[common_idx],
        ff3_data.mkt_rf.loc[common_idx],
        ff3_data.smb.loc[common_idx],
        ff3_data.hml.loc[common_idx],
        risk_free_daily=rf_daily,
    )

    return {
        "symbol": symbol.upper(),
        "factor_source": factors_provenance.name,
        "factor_frequency": factors_provenance.frequency,
        "factor_provenance": factors_provenance.description,
        "is_production_factor": factors_provenance.is_production,
        "risk_free_source": "rbi" if factor_source == "iim_ahmedabad" else "fallback",
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
