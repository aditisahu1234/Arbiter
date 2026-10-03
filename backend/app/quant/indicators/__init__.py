"""Quantitative indicators: SMA, EMA, True Range, ATR, Returns."""
from __future__ import annotations

import numpy as np
import pandas as pd
from abc import ABC, abstractmethod
from typing import Literal


class Indicator(ABC):
    @abstractmethod
    def compute(self, df: pd.DataFrame, **kwargs) -> pd.Series: ...


class SimpleMovingAverage(Indicator):
    def __init__(self, window: int = 20):
        self.window = window

    def compute(self, df: pd.DataFrame, **kwargs) -> pd.Series:
        col = kwargs.get("column", "adjusted_close")
        return df[col].rolling(window=self.window, min_periods=self.window).mean()


class ExponentialMovingAverage(Indicator):
    def __init__(self, span: int = 20):
        self.span = span

    def compute(self, df: pd.DataFrame, **kwargs) -> pd.Series:
        col = kwargs.get("column", "adjusted_close")
        return df[col].ewm(span=self.span, adjust=False).mean()


class TrueRange(Indicator):
    def compute(self, df: pd.DataFrame, **kwargs) -> pd.Series:
        """TR_t = max(H_t - L_t, |H_t - C_{t-1}|, |L_t - C_{t-1}|).
        First row TR is NaN (no previous close).
        """
        high = df["high"]
        low = df["low"]
        prev_close = df["adjusted_close"].shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        # First row has no prev_close, so TR is just H-L but conventionally NaN
        tr.iloc[0] = np.nan
        return tr


class AverageTrueRange(Indicator):
    def __init__(self, window: int = 14, smoothing: Literal["rma", "sma", "ema"] = "rma"):
        self.window = window
        self.smoothing = smoothing

    def compute(self, df: pd.DataFrame, **kwargs) -> pd.Series:
        tr = TrueRange().compute(df)
        if self.smoothing == "rma":
            atr = pd.Series(index=tr.index, dtype=float, name="atr")
            atr.iloc[: self.window - 1] = np.nan
            atr.iloc[self.window - 1] = tr.iloc[: self.window].mean()
            for i in range(self.window, len(tr)):
                atr.iloc[i] = (atr.iloc[i - 1] * (self.window - 1) + tr.iloc[i]) / self.window
            return atr
        elif self.smoothing == "sma":
            return tr.rolling(window=self.window, min_periods=self.window).mean()
        else:  # ema
            return tr.ewm(span=self.window, adjust=False).mean()


class ReturnsEngine:
    @staticmethod
    def simple_returns(prices: pd.Series) -> pd.Series:
        return prices.pct_change()

    @staticmethod
    def log_returns(prices: pd.Series) -> pd.Series:
        return np.log(prices / prices.shift(1))

    @staticmethod
    def cumulative_returns(prices: pd.Series) -> pd.Series:
        return (1 + prices.pct_change()).cumprod() - 1

    @staticmethod
    def annualized_return(cum_ret: float, days: int) -> float:
        if days <= 0 or cum_ret <= -1:
            return 0.0
        return (1 + cum_ret) ** (252 / max(days, 1)) - 1

    @staticmethod
    def annual_volatility(returns: pd.Series) -> float:
        if len(returns) < 2:
            return 0.0
        return float(returns.std() * np.sqrt(252))
