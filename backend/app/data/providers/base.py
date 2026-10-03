from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional
import pandas as pd


class MarketDataProvider(ABC):
    """Abstract base class for all market data providers (Yahoo, Polygon, Bloomberg, etc.).

    This ensures the quant engine and API layers never couple directly to any single vendor API.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier name (e.g. 'yahoo', 'polygon')."""
        pass

    @abstractmethod
    def get_asset_metadata(self, provider_symbol: str) -> Dict[str, Any]:
        """Fetch asset fundamental profile and metadata from provider."""
        pass

    @abstractmethod
    def get_historical_ohlcv(
        self,
        provider_symbol: str,
        start_date: datetime | str,
        end_date: datetime | str,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data.

        Returns a standardized DataFrame with columns:
        ['timestamp', 'open', 'high', 'low', 'close', 'adjusted_close', 'volume']
        """
        pass

    @abstractmethod
    def get_latest_ohlcv(self, provider_symbol: str) -> pd.DataFrame:
        """Fetch the most recent OHLCV bar for an asset."""
        pass
