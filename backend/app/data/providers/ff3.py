"""India Fama-French 3-factor provider abstraction."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
import numpy as np


@dataclass
class FactorSource:
    """Metadata about factor data source."""
    name: str
    description: str
    url: str
    frequency: str  # "daily", "monthly"
    start_date: str
    end_date: str
    is_production: bool


@dataclass
class FF3Factors:
    """Fama-French 3-factor data with provenance."""
    dates: pd.DatetimeIndex
    mkt_rf: pd.Series  # Market excess return
    smb: pd.Series     # Size factor
    hml: pd.Series     # Value factor
    rf: pd.Series      # Risk-free rate
    source: FactorSource


class IndiaFF3Provider(ABC):
    """Abstract provider for India-specific Fama-French factors."""

    @abstractmethod
    def get_factors(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> FF3Factors:
        """Fetch FF3 factors for the given date range."""
        pass

    @property
    @abstractmethod
    def source(self) -> FactorSource:
        """Return source metadata."""
        pass


class IIMAhmedabadFF3Provider(IndiaFF3Provider):
    """Provider for IIM Ahmedabad India FF3 factors.

    Source: https://www.iima.ac.in/en/faculty/agarwalla/data
    Dataset: India-specific Fama-French factors computed by Agarwalla, Jacob, Varma

    Notes:
    - Requires manual download of factor data from IIM Ahmedabad
    - Factors are monthly, must be interpolated to daily for our use case
    - Production use requires acquiring the dataset
    """

    _FACTORS_FILE = Path("data/factors/india_ff3_monthly.csv")

    @property
    def source(self) -> FactorSource:
        return FactorSource(
            name="IIM Ahmedabad FF3",
            description="India-specific Fama-French factors from IIM Ahmedabad research data",
            url="https://www.iima.ac.in/en/faculty/agarwalla/data",
            frequency="monthly",
            start_date="2000-01-01",
            end_date="2026-10-01",
            is_production=True,
        )

    def get_factors(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> FF3Factors:
        if not self._FACTORS_FILE.exists():
            raise FileNotFoundError(
                f"IIM Ahmedabad FF3 factors not found at {self._FACTORS_FILE}. "
                "Please download from https://www.iima.ac.in/en/faculty/agarwalla/data "
                "and place in data/factors/india_ff3_monthly.csv"
            )

        df = pd.read_csv(self._FACTORS_FILE, parse_dates=["date"])
        df = df.sort_values("date").set_index("date")

        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]

        if df.empty:
            raise ValueError("No factor data in requested date range")

        # Interpolate to daily frequency
        daily_index = pd.date_range(df.index.min(), df.index.max(), freq="D")
        df = df.reindex(daily_index)
        df = df.interpolate(method="time")
        df = df.fillna(method="ffill")

        return FF3Factors(
            dates=df.index,
            mkt_rf=df["mkt_rf"],
            smb=df["smb"],
            hml=df["hml"],
            rf=df["rf"],
            source=self.source,
        )


class SyntheticFF3Provider(IndiaFF3Provider):
    """Fallback provider using synthetic factors from price data.

    This is NOT India-specific FF3. It uses NIFTY 500 constituents to construct
    synthetic size and value factors for research/development purposes only.

    WARNING: These factors are synthetic and should not be used for production research.
    """

    def __init__(self, asset_storage):
        self.storage = asset_storage

    @property
    def source(self) -> FactorSource:
        return FactorSource(
            name="Synthetic (Research Only)",
            description="Synthetic factors constructed from NIFTY 500 constituents. NOT India-specific FF3.",
            url="",
            frequency="daily",
            start_date="2021-09-20",
            end_date="2026-10-01",
            is_production=False,
        )

    def get_factors(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> FF3Factors:
        # Large-cap vs small-cap returns
        large_caps = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "NTPC", "ONGC", "LT"]
        small_caps = ["TATAMOTORS", "WIPRO", "SUNPHARMA", "MARUTI", "KOTAKBANK", "AXISBANK"]

        all_symbols = large_caps + small_caps + ["ITC", "ASIANPAINT"]  # ITC for HML

        returns = {}
        for sym in all_symbols:
            df = self.storage.load_normalized_ohlcv(sym, start_date, end_date)
            if not df.empty:
                returns[sym] = df.set_index("timestamp")["adjusted_close"].pct_change()

        if len(returns) < 5:
            raise ValueError("Insufficient data for synthetic factor construction")

        large_ret = pd.concat([returns[s] for s in large_caps if s in returns], axis=1).mean(axis=1)
        small_ret = pd.concat([returns[s] for s in small_caps if s in returns], axis=1).mean(axis=1)
        smb = small_ret - large_ret

        # HML: FMCG (value) vs IT (growth)
        it_ret = returns.get("WIPRO", pd.Series())
        fmcg_ret = returns.get("ITC", pd.Series())
        hml = fmcg_ret - it_ret

        # Market factor (NIFTY 50)
        nse_df = self.storage.load_normalized_ohlcv("^NSEI", start_date, end_date)
        if nse_df.empty:
            raise ValueError("NIFTY 50 data required for market factor")
        mkt_rf = nse_df.set_index("timestamp")["adjusted_close"].pct_change()

        # Align all series
        common_idx = mkt_rf.index.intersection(smb.index).intersection(hml.index)
        if len(common_idx) < 30:
            raise ValueError(f"Insufficient common observations: {len(common_idx)}")

        rf = pd.Series(0.0, index=common_idx)  # Synthetic factors don't include RF

        return FF3Factors(
            dates=common_idx,
            mkt_rf=mkt_rf.loc[common_idx],
            smb=smb.loc[common_idx],
            hml=hml.loc[common_idx],
            rf=rf.loc[common_idx],
            source=self.source,
        )


class IndiaFF3ProviderFactory:
    """Factory for creating India FF3 providers."""

    _providers = {
        "iim_ahmedabad": IIMAhmedabadFF3Provider,
        "synthetic": SyntheticFF3Provider,
    }

    @classmethod
    def create(cls, source: Literal["iim_ahmedabad", "synthetic"], **kwargs):
        provider_class = cls._providers.get(source)
        if not provider_class:
            raise ValueError(f"Unknown FF3 provider: {source}")
        return provider_class(**kwargs)

    @classmethod
    def get_default(cls, asset_storage):
        """Get the best available provider."""
        try:
            return IIMAhmedabadFF3Provider()
        except Exception:
            return SyntheticFF3Provider(asset_storage)
