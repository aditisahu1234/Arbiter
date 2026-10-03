from datetime import datetime, timedelta
from typing import Any, Dict
import numpy as np
import pandas as pd
from app.data.providers.base import MarketDataProvider


class MockMarketDataProvider(MarketDataProvider):
    """Deterministic Mock Market Data Provider for offline testing and mathematical benchmarking."""

    def __init__(self, seed: int = 42):
        self._seed = seed

    @property
    def name(self) -> str:
        return "mock"

    def get_asset_metadata(self, provider_symbol: str) -> Dict[str, Any]:
        symbol = provider_symbol.replace(".NS", "")
        return {
            "symbol": symbol,
            "provider_symbol": provider_symbol,
            "name": f"{symbol} Test Corporation",
            "currency": "INR",
            "country": "IN",
            "sector": "Information Technology",
            "industry": "Software Services",
            "exchange": "NSE",
            "market_cap": 100000000000,
        }

    def get_historical_ohlcv(
        self,
        provider_symbol: str,
        start_date: datetime | str,
        end_date: datetime | str,
        interval: str = "1d",
    ) -> pd.DataFrame:
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        dates = pd.date_range(start=start_dt, end=end_dt, freq="B")  # Business days

        if len(dates) == 0:
            return pd.DataFrame()

        np.random.seed(self._seed + abs(hash(provider_symbol)) % 10000)

        # Generate geometric brownian motion price series
        n = len(dates)
        returns = np.random.normal(0.0005, 0.015, n)
        price_path = 1000.0 * np.exp(np.cumsum(returns))

        raw_highs = price_path * (1 + np.abs(np.random.normal(0.005, 0.005, n)))
        raw_lows = price_path * (1 - np.abs(np.random.normal(0.005, 0.005, n)))
        opens = (raw_highs + raw_lows) / 2 + np.random.normal(0, 1.0, n)
        closes = price_path

        # Mathematically enforce High >= max(Open, Close) and Low <= min(Open, Close)
        highs = np.maximum(raw_highs, np.maximum(opens, closes))
        lows = np.minimum(raw_lows, np.minimum(opens, closes))

        adj_closes = closes * 0.98
        volumes = np.random.randint(100000, 5000000, n).astype(np.int64)

        df = pd.DataFrame({
            "timestamp": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "adjusted_close": adj_closes,
            "volume": volumes,
        })
        return df

    def get_latest_ohlcv(self, provider_symbol: str) -> pd.DataFrame:
        today = datetime.now()
        df = self.get_historical_ohlcv(provider_symbol, today - timedelta(days=5), today)
        return df.tail(1).reset_index(drop=True)
