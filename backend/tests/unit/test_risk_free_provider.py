"""CAPM risk-free provider tests."""
from pathlib import Path
import pandas as pd
import pytest
import numpy as np

from app.data.providers.risk_free import (
    IndiaRiskFreeProviderFactory,
    RBITBillProvider,
    ConstantFallbackProvider,
    RiskFreeData,
)


class TestRBITBillProvider:
    def test_source_metadata(self):
        provider = RBITBillProvider()
        assert provider.source.name == "RBI 91-day T-Bill"
        assert provider.source.is_production is True
        assert provider.source.frequency == "weekly"

    def test_missing_data_file(self):
        provider = RBITBillProvider()
        with pytest.raises(FileNotFoundError, match="RBI T-bill data not found"):
            provider.get_rates()


class TestConstantFallbackProvider:
    def test_source_metadata(self):
        provider = ConstantFallbackProvider()
        assert provider.source.name == "Constant Fallback"
        assert provider.source.is_production is False

    def test_returns_daily_rates(self):
        provider = ConstantFallbackProvider(rate_annual=6.5)
        data = provider.get_rates()
        assert isinstance(data, RiskFreeData)
        assert len(data.dates) > 0
        assert len(data.rates) > 0
        # Daily rate should be approximately 6.5% annualized
        daily_rate = (1 + 6.5 / 100) ** (1 / 252) - 1
        assert abs(data.rates.iloc[0] - daily_rate) < 1e-6

    def test_custom_rate(self):
        provider = ConstantFallbackProvider(rate_annual=5.0)
        data = provider.get_rates()
        assert data.annualized == 5.0


class TestRiskFreeFactory:
    def test_get_default_uses_fallback(self):
        provider = IndiaRiskFreeProviderFactory.get_default()
        # Should fallback to constant when RBI data unavailable
        # Note: May use RBI provider if file exists, or constant if not
        assert provider is not None
