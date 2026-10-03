"""CAPM and Fama-French regression benchmark tests."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.quant.risk import CAPMEngine, FamaFrenchEngine


@pytest.fixture
def synthetic_data():
    np.random.seed(42)
    n = 500
    market_ret = np.random.randn(n) * 0.01
    alpha = 0.0002
    beta = 1.5
    noise = np.random.randn(n) * 0.005
    asset_ret = alpha + beta * market_ret + noise
    rf = 0.0002
    smb = np.random.randn(n) * 0.003
    hml = np.random.randn(n) * 0.003
    return (
        pd.Series(asset_ret),
        pd.Series(market_ret),
        rf,
        pd.Series(smb),
        pd.Series(hml),
    )


def test_capm_basic(synthetic_data):
    asset_ret, market_ret, rf, smb, hml = synthetic_data
    result = CAPMEngine.compute(asset_ret, market_ret, risk_free_daily=rf)
    assert result.observations == 500
    assert result.r_squared > 0
    assert result.r_squared < 1
    assert abs(result.beta - 1.5) < 0.5


def test_capm_zero_beta(synthetic_data):
    np.random.seed(99)
    n = 300
    market_ret = pd.Series(np.random.randn(n) * 0.01)
    asset_ret = pd.Series(np.random.randn(n) * 0.003)
    result = CAPMEngine.compute(asset_ret, market_ret, risk_free_daily=0.0002)
    assert abs(result.beta) < 0.5


def test_capm_insufficient_data():
    asset_ret = pd.Series([0.01] * 5)
    market_ret = pd.Series([0.01] * 5)
    with pytest.raises(ValueError, match="Insufficient"):
        CAPMEngine.compute(asset_ret, market_ret, risk_free_daily=0.0002)


def test_ff3_basic(synthetic_data):
    asset_ret, market_ret, rf, smb, hml = synthetic_data
    result = FamaFrenchEngine.compute(
        asset_ret, market_ret, smb, hml, risk_free_daily=rf
    )
    assert result.observations == 500
    assert result.r_squared > 0


def test_ff3_outputs_structure(synthetic_data):
    asset_ret, market_ret, rf, smb, hml = synthetic_data
    result = FamaFrenchEngine.compute(
        asset_ret, market_ret, smb, hml, risk_free_daily=rf
    )
    assert hasattr(result, "alpha")
    assert hasattr(result, "beta_market")
    assert hasattr(result, "beta_size")
    assert hasattr(result, "beta_value")
    assert hasattr(result, "r_squared")
    assert hasattr(result, "alpha_se")
    assert hasattr(result, "alpha_t_stat")
    assert hasattr(result, "alpha_p_value")
    assert hasattr(result, "observations")
