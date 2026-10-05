"""FF3 provider tests with deterministic fixtures."""
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest
import numpy as np

from app.data.providers.ff3 import (
    IndiaFF3ProviderFactory,
    IIMAhmedabadFF3Provider,
    SyntheticFF3Provider,
    FF3Factors,
)
from app.data.storage import storage_manager


class TestIIMAhmedabadProvider:
    def test_source_metadata(self):
        provider = IIMAhmedabadFF3Provider()
        assert provider.source.name == "IIM Ahmedabad FF3"
        assert provider.source.is_production is True
        assert provider.source.frequency == "monthly"

    def test_missing_data_file_raises_error(self):
        """Should raise explicit error, not silently fallback."""
        provider = IIMAhmedabadFF3Provider()
        with pytest.raises(FileNotFoundError, match="IIM Ahmedabad FF3 factors not found"):
            provider.get_factors()


class TestSyntheticProvider:
    def test_source_metadata(self):
        provider = SyntheticFF3Provider(storage_manager)
        assert provider.source.name == "Synthetic (Research Only)"
        assert provider.source.is_production is False
        assert provider.source.frequency == "daily"

    def test_produces_factors_with_mock_data(self):
        """Test synthetic provider with mock data."""
        # Create mock data for required symbols
        base_date = pd.Timestamp("2024-01-01")
        dates = pd.date_range(base_date, periods=100, freq="D")

        mock_data = {}
        for sym in ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "NTPC", "ONGC", "LT",
                     "TATAMOTORS", "WIPRO", "SUNPHARMA", "MARUTI", "KOTAKBANK", "AXISBANK", "ITC"]:
            prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
            mock_data[sym] = pd.DataFrame({
                "timestamp": dates,
                "open": prices,
                "high": prices + 1,
                "low": prices - 1,
                "close": prices,
                "adjusted_close": prices,
                "volume": [1000] * 100,
            })

        # Mock the storage manager including NIFTY 50
        mock_data["^NSEI"] = pd.DataFrame({
            "timestamp": dates,
            "open": 100 + np.cumsum(np.random.randn(100) * 0.3),
            "high": 100 + np.cumsum(np.random.randn(100) * 0.3) + 1,
            "low": 100 + np.cumsum(np.random.randn(100) * 0.3) - 1,
            "close": 100 + np.cumsum(np.random.randn(100) * 0.3),
            "adjusted_close": 100 + np.cumsum(np.random.randn(100) * 0.3),
            "volume": [1000] * 100,
        })

        with patch.object(storage_manager, 'load_normalized_ohlcv', side_effect=lambda sym, *a, **k: mock_data.get(sym, pd.DataFrame())):
            provider = SyntheticFF3Provider(storage_manager)
            factors = provider.get_factors()
            assert isinstance(factors, FF3Factors)
            assert len(factors.dates) > 0
            assert len(factors.mkt_rf) > 0
            assert len(factors.smb) > 0
            assert len(factors.hml) > 0


class TestFF3Factory:
    def test_create_iim(self):
        provider = IndiaFF3ProviderFactory.create("iim_ahmedabad")
        assert isinstance(provider, IIMAhmedabadFF3Provider)

    def test_create_synthetic(self):
        provider = IndiaFF3ProviderFactory.create("synthetic", asset_storage=storage_manager)
        assert isinstance(provider, SyntheticFF3Provider)

    def test_get_default_fallback(self):
        provider = IndiaFF3ProviderFactory.get_default(storage_manager)
        # Should return a provider instance (either IIM or Synthetic)
        assert provider is not None
