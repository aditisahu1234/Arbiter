"""Trading strategies: SMA Crossover with ATR Stop-loss."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional

import numpy as np
import pandas as pd

from app.quant.indicators import SimpleMovingAverage, AverageTrueRange


class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class Trade:
    symbol: str
    entry_time: str
    entry_price: float
    exit_time: str
    exit_price: float
    stop_loss: float
    exit_reason: str
    pnl_pct: float


@dataclass
class StrategyConfig:
    fast_sma: int = 10
    slow_sma: int = 50
    atr_window: int = 14
    atr_multiplier: float = 3.0
    initial_capital: float = 1_000_000.0
    cost_bps: float = 10.0  # round-trip transaction cost in basis points


class SMACrossoverStrategy:
    """Long entry when SMA_fast crosses above SMA_slow; exit on reverse or ATR stop.

    Stop-loss = entry_price - atr_multiplier * atr (computed at entry bar).
    Signals generated on bar t using data through t; executed on bar t+1 open.
    """

    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig()

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Returns DataFrame with: timestamp, signal, fast_sma, slow_sma, atr, stop_loss.

        stop_loss is trailing — updated each bar to entry_price - k*ATR as of that bar.
        """
        cfg = self.config
        sma_fast = SimpleMovingAverage(cfg.fast_sma).compute(df)
        sma_slow = SimpleMovingAverage(cfg.slow_sma).compute(df)
        atr = AverageTrueRange(cfg.atr_window, "rma").compute(df)

        out = pd.DataFrame({
            "timestamp": df["timestamp"],
            "fast_sma": sma_fast,
            "slow_sma": sma_slow,
            "atr": atr,
        })

        cross_up = (sma_fast > sma_slow) & (sma_fast.shift(1) <= sma_slow.shift(1))
        cross_down = (sma_fast < sma_slow) & (sma_fast.shift(1) >= sma_slow.shift(1))

        out["signal"] = "HOLD"
        out.loc[cross_up.fillna(False), "signal"] = "BUY"
        out.loc[cross_down.fillna(False), "signal"] = "SELL"

        return out
