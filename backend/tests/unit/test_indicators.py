"""True Range and ATR mathematical correctness tests."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.quant.indicators import (
    SimpleMovingAverage,
    TrueRange,
    AverageTrueRange,
    ReturnsEngine,
)


def _make_ohlcv(n=100, seed=42):
    np.random.seed(seed)
    prices = 100 + np.cumsum(np.random.randn(n) * 0.5)
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "timestamp": dates,
        "open": prices + np.random.randn(n) * 0.1,
        "high": prices + abs(np.random.randn(n)) * 0.5,
        "low": prices - abs(np.random.randn(n)) * 0.5,
        "close": prices,
        "adjusted_close": prices,
        "volume": np.random.randint(1000, 10000, n),
    })


class TestSMA:
    def test_sma_2_window(self):
        df = pd.DataFrame({"adjusted_close": [10, 20, 30, 40]})
        sma = SimpleMovingAverage(2).compute(df)
        assert pd.isna(sma.iloc[0])
        assert sma.iloc[1] == 15.0
        assert sma.iloc[2] == 25.0
        assert sma.iloc[3] == 35.0

    def test_sma_exact(self):
        df = pd.DataFrame({"adjusted_close": list(range(1, 11))})
        sma = SimpleMovingAverage(3).compute(df)
        assert pd.isna(sma.iloc[0])
        assert pd.isna(sma.iloc[1])
        assert sma.iloc[2] == 2.0
        assert sma.iloc[3] == 3.0


class TestTrueRange:
    def test_tr_first_row_nan(self):
        """TR is undefined for first row (no prev close)."""
        df = pd.DataFrame({
            "high": [10, 12, 11],
            "low": [8, 9, 10],
            "adjusted_close": [9, 11, 10.5],
        })
        tr = TrueRange().compute(df)
        assert pd.isna(tr.iloc[0])

    def test_tr_basic(self):
        df = pd.DataFrame({
            "high": [10, 12],
            "low": [8, 9],
            "adjusted_close": [9, 11],
        })
        tr = TrueRange().compute(df)
        assert pd.isna(tr.iloc[0])
        # TR_1 = max(12-9, |12-9|, |9-9|) = max(3, 3, 0) = 3
        assert tr.iloc[1] == 3.0

    def test_tr_gap_up(self):
        df = pd.DataFrame({
            "high": [100, 110],
            "low": [90, 95],
            "adjusted_close": [95, 105],
        })
        tr = TrueRange().compute(df)
        assert pd.isna(tr.iloc[0])
        # TR_1 = max(110-95, |110-95|, |95-95|) = max(15, 15, 0) = 15
        assert tr.iloc[1] == 15.0

    def test_tr_gap_down(self):
        df = pd.DataFrame({
            "high": [100, 80],
            "low": [90, 70],
            "adjusted_close": [95, 75],
        })
        tr = TrueRange().compute(df)
        assert pd.isna(tr.iloc[0])
        # TR_1 = max(80-70, |80-95|, |70-95|) = max(10, 15, 25) = 25
        assert tr.iloc[1] == 25.0


class TestATR:
    def test_atr_rma_init(self):
        df = _make_ohlcv(50)
        atr = AverageTrueRange(14, "rma").compute(df)
        assert pd.isna(atr.iloc[:13]).all()
        assert not pd.isna(atr.iloc[13])

    def test_atr_sma_vs_rma(self):
        df = _make_ohlcv(50)
        atr_rma = AverageTrueRange(14, "rma").compute(df)
        atr_sma = AverageTrueRange(14, "sma").compute(df)
        assert not atr_rma.equals(atr_sma)
        # Both start NaN at same positions (after TR[0]=NaN, need 14 TR values for init)
        assert pd.isna(atr_rma.iloc[0])
        assert pd.isna(atr_sma.iloc[0])

    def test_atr_ema(self):
        df = _make_ohlcv(50)
        atr_ema = AverageTrueRange(14, "ema").compute(df)
        assert not pd.isna(atr_ema).all()

    def test_atr_values_positive(self):
        df = _make_ohlcv(100)
        atr = AverageTrueRange(14, "rma").compute(df)
        valid = atr.dropna()
        assert (valid > 0).all()


class TestReturns:
    def test_simple_returns(self):
        prices = pd.Series([100, 110, 99])
        rets = ReturnsEngine.simple_returns(prices)
        assert abs(rets.iloc[1] - 0.1) < 1e-10
        assert abs(rets.iloc[2] - (-0.1)) < 1e-10

    def test_log_returns(self):
        prices = pd.Series([100, 110])
        rets = ReturnsEngine.log_returns(prices)
        assert abs(rets.iloc[1] - np.log(1.1)) < 1e-10

    def test_cumulative_returns(self):
        prices = pd.Series([100, 110, 99])
        cum = ReturnsEngine.cumulative_returns(prices)
        assert abs(cum.iloc[1] - 0.1) < 1e-10

    def test_annualized_return_1yr(self):
        ret = ReturnsEngine.annualized_return(0.21, 252)
        assert abs(ret - 0.21) < 1e-6

    def test_annualized_return_half_year(self):
        ret = ReturnsEngine.annualized_return(0.10, 126)
        assert ret > 0.18

    def test_annual_volatility(self):
        returns = pd.Series([0.01, -0.01, 0.005, -0.005, 0.02, -0.02] * 10)
        vol = ReturnsEngine.annual_volatility(returns)
        assert vol > 0
        assert vol < 1.0
