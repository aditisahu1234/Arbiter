"""Look-ahead bias and backtest execution tests."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.quant.backtesting import BacktestEngine
from app.quant.strategies import StrategyConfig


def _make_up_trend(n=200, start=100):
    np.random.seed(42)
    prices = start + np.cumsum(np.random.randn(n) * 0.3 + 0.05)
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "timestamp": dates,
        "open": prices + np.random.randn(n) * 0.01,
        "high": prices + abs(np.random.randn(n)) * 0.5,
        "low": prices - abs(np.random.randn(n)) * 0.5,
        "close": prices,
        "adjusted_close": prices,
        "volume": np.random.randint(1000, 5000, n),
    })


def _make_down_trend(n=200, start=100):
    np.random.seed(43)
    prices = start + np.cumsum(np.random.randn(n) * 0.3 - 0.05)
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "timestamp": dates,
        "open": prices + np.random.randn(n) * 0.01,
        "high": prices + abs(np.random.randn(n)) * 0.5,
        "low": prices - abs(np.random.randn(n)) * 0.5,
        "close": prices,
        "adjusted_close": prices,
        "volume": np.random.randint(1000, 5000, n),
    })


def test_no_look_ahead():
    df = _make_up_trend(200)
    cfg = StrategyConfig(fast_sma=5, slow_sma=10, cost_bps=10)
    engine = BacktestEngine(cfg)
    result = engine.run(df, "TEST")
    assert result.metrics["total_trades"] >= 0
    for t in result.trades:
        assert t["entry_time"] <= t["exit_time"]


def test_up_trend_positive_return():
    df = _make_up_trend(500)
    cfg = StrategyConfig(fast_sma=5, slow_sma=15)
    engine = BacktestEngine(cfg)
    result = engine.run(df, "TEST")
    assert result.metrics["net_return"] > 0


def test_down_trend_negative_return():
    df = _make_down_trend(500)
    cfg = StrategyConfig(fast_sma=5, slow_sma=15)
    engine = BacktestEngine(cfg)
    result = engine.run(df, "TEST")
    assert result.metrics["net_return"] < 0


def test_metrics_structure():
    df = _make_up_trend(300)
    cfg = StrategyConfig(fast_sma=5, slow_sma=10)
    engine = BacktestEngine(cfg)
    result = engine.run(df, "TEST")
    m = result.metrics
    assert "gross_return" in m
    assert "net_return" in m
    assert "gross_cagr" in m
    assert "net_cagr" in m
    assert "sharpe_ratio" in m
    assert "sortino_ratio" in m
    assert "max_drawdown" in m
    assert "win_rate" in m
    assert "profit_factor" in m
    assert "total_trades" in m
    assert m["total_trades"] == m["winning_trades"] + m["losing_trades"]


def test_trade_log_structure():
    df = _make_up_trend(300)
    cfg = StrategyConfig(fast_sma=5, slow_sma=10)
    engine = BacktestEngine(cfg)
    result = engine.run(df, "TEST")
    for t in result.trades:
        assert "entry_time" in t
        assert "entry_price" in t
        assert "exit_time" in t
        assert "exit_price" in t
        assert "exit_reason" in t
        assert "pnl_pct" in t
        assert t["exit_time"] >= t["entry_time"]


def test_cost_deducts_net_from_gross():
    df = _make_up_trend(400)
    cfg = StrategyConfig(fast_sma=5, slow_sma=10, cost_bps=10)
    engine = BacktestEngine(cfg)
    result = engine.run(df, "TEST")
    assert result.metrics["net_return"] <= result.metrics["gross_return"]
