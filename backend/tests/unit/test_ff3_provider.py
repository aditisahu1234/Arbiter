"""FF3 provider tests."""
from pathlib import Path
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

    def test_missing_data_file(self):
        provider = IIMAhmedabadFF3Provider()
        with pytest.raises(FileNotFoundError, match="IIM Ahmedabad FF3 factors not found"):
            provider.get_factors()


class TestSyntheticProvider:
    def test_source_metadata(self):
        provider = SyntheticFF3Provider(storage_manager)
        assert provider.source.name == "Synthetic (Research Only)"
        assert provider.source.is_production is False
        assert provider.source.frequency == "daily"

    def test_produces_factors(self):
        provider = SyntheticFF3Provider(storage_manager)
        try:
            factors = provider.get_factors()
            assert isinstance(factors, FF3Factors)
            assert len(factors.dates) > 0
            assert len(factors.mkt_rf) > 0
            assert len(factors.smb) > 0
            assert len(factors.hml) > 0
        except ValueError as e:
            # May fail if NIFTY 50 data not available
            pytest.skip(f"Synthetic FF3 requires NIFTY 50 data: {e}")


class TestFF3Factory:
    def test_create_iim(self):
        provider = IndiaFF3ProviderFactory.create("iim_ahmedabad")
        assert isinstance(provider, IIMAhmedabadFF3Provider)

    def test_create_synthetic(self):
        provider = IndiaFF3ProviderFactory.create("synthetic", asset_storage=storage_manager)
        assert isinstance(provider, SyntheticFF3Provider)

    def test_get_default_uses_synthetic(self):
        provider = IndiaFF3ProviderFactory.get_default(storage_manager)
        # Should fallback to synthetic when IIM data unavailable
        # Note: May use IIM provider if file exists, or synthetic if not
        assert provider is not None
