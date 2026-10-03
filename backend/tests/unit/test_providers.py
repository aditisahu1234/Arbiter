from datetime import datetime

import pytest

from app.data.providers.base import MarketDataProvider
from app.data.providers.factory import get_market_data_provider
from app.data.providers.mock import MockMarketDataProvider
from app.data.providers.yahoo import YahooFinanceProvider


def test_provider_factory():
    """Verify provider factory returns appropriate provider subclasses."""
    yahoo = get_market_data_provider("yahoo")
    assert isinstance(yahoo, YahooFinanceProvider)
    assert isinstance(yahoo, MarketDataProvider)
    assert yahoo.name == "yahoo"

    mock = get_market_data_provider("mock")
    assert isinstance(mock, MockMarketDataProvider)
    assert isinstance(mock, MarketDataProvider)
    assert mock.name == "mock"

    with pytest.raises(ValueError):
        get_market_data_provider("unsupported_vendor")


def test_mock_provider_ohlcv_contract():
    """Verify data provider returns standardized DataFrame matching quantitative requirements."""
    provider = MockMarketDataProvider(seed=100)
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2023, 1, 31)

    df = provider.get_historical_ohlcv("TCS.NS", start_date, end_date)
    assert not df.empty
    expected_cols = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "adjusted_close",
        "volume",
    ]
    for col in expected_cols:
        assert col in df.columns

    # Verify mathematical ordering
    assert (df["high"] >= df["low"]).all()
    assert (df["high"] >= df["open"]).all()
    assert (df["high"] >= df["close"]).all()
    assert (df["low"] <= df["open"]).all()
    assert (df["low"] <= df["close"]).all()
    assert (df["volume"] >= 0).all()


def test_yahoo_provider_raw_persistence(tmp_path):
    """Verify Yahoo provider writes raw payload to disk for data provenance."""
    provider = YahooFinanceProvider(raw_base_dir=tmp_path)
    sample_raw = {"symbol": "INFY.NS", "records": [{"price": 1500.0}]}
    saved_file = provider._persist_raw_payload("INFY.NS", sample_raw, "2024-01-01")

    assert saved_file.exists()
    assert saved_file.suffix == ".json"
    assert "INFY_NS" in saved_file.name
