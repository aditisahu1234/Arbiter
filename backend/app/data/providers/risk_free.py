"""India risk-free rate provider abstraction."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np


@dataclass
class RiskFreeSource:
    """Metadata about risk-free rate source."""
    name: str
    description: str
    url: str
    frequency: str  # "daily", "monthly", "annual"
    is_production: bool
    last_updated: Optional[str] = None


@dataclass
class RiskFreeData:
    """Risk-free rate data with provenance."""
    dates: pd.DatetimeIndex
    rates: pd.Series  # Daily rates
    annualized: float  # Annualized rate
    source: RiskFreeSource


class IndiaRiskFreeProvider(ABC):
    """Abstract provider for India risk-free rates."""

    @abstractmethod
    def get_rates(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> RiskFreeData:
        pass

    @property
    @abstractmethod
    def source(self) -> RiskFreeSource:
        pass


class RBITBillProvider(IndiaRiskFreeProvider):
    """Provider for RBI 91-day T-bill rates.

    Source: Reserve Bank of India statistical data warehouse
    URL: https://data-rbi.mospi.gov.in/

    Notes:
    - Requires manual download or API access to RBI data
    - 91-day T-bill yield is the standard risk-free proxy for India
    - Data is published weekly
    """

    _RATE_FILE = Path("data/factors/rbi_tbill_91d.csv")

    @property
    def source(self) -> RiskFreeSource:
        return RiskFreeSource(
            name="RBI 91-day T-Bill",
            description="91-day Treasury Bill yield from Reserve Bank of India",
            url="https://data-rbi.mospi.gov.in/",
            frequency="weekly",
            is_production=True,
        )

    def get_rates(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> RiskFreeData:
        if not self._RATE_FILE.exists():
            raise FileNotFoundError(
                f"RBI T-bill data not found at {self._RATE_FILE}. "
                "Please download from https://data-rbi.mospi.gov.in/ "
                "and place in data/factors/rbi_tbill_91d.csv"
            )

        df = pd.read_csv(self._RATE_FILE, parse_dates=["date"])
        df = df.sort_values("date").set_index("date")

        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]

        if df.empty:
            raise ValueError("No rate data in requested date range")

        # Convert annual rate to daily
        annual_rate = df["rate"].iloc[-1] if len(df) > 0 else 6.5
        daily_rates = (1 + annual_rate / 100) ** (1 / 252) - 1

        # Create daily series
        dates = pd.date_range(df.index.min(), df.index.max(), freq="D")
        rates = pd.Series(daily_rates, index=dates)

        return RiskFreeData(
            dates=dates,
            rates=rates,
            annualized=annual_rate,
            source=self.source,
        )


class ConstantFallbackProvider(IndiaRiskFreeProvider):
    """Fallback provider using constant risk-free rate.

    Uses a configurable constant rate (default 6.5% annualized).
    This is NOT production data - only for offline/testing.
    """

    def __init__(self, rate_annual: float = 6.5):
        self._rate_annual = rate_annual

    @property
    def source(self) -> RiskFreeSource:
        return RiskFreeSource(
            name="Constant Fallback",
            description="Configurable constant risk-free rate (NOT live RBI data)",
            url="",
            frequency="constant",
            is_production=False,
            last_updated=datetime.now().strftime("%Y-%m-%d"),
        )

    def get_rates(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> RiskFreeData:
        start = pd.Timestamp(start_date) if start_date else pd.Timestamp("2021-01-01")
        end = pd.Timestamp(end_date) if end_date else pd.Timestamp("2026-10-01")

        dates = pd.date_range(start, end, freq="D")
        daily_rate = (1 + self._rate_annual / 100) ** (1 / 252) - 1
        rates = pd.Series(daily_rate, index=dates)

        return RiskFreeData(
            dates=dates,
            rates=rates,
            annualized=self._rate_annual,
            source=self.source,
        )


class IndiaRiskFreeProviderFactory:
    """Factory for creating India risk-free providers."""

    @classmethod
    def get_default(cls):
        """Get the best available provider."""
        try:
            return RBITBillProvider()
        except Exception:
            return ConstantFallbackProvider()
