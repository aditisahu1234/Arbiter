from app.core.config import settings
from app.data.providers.base import MarketDataProvider
from app.data.providers.mock import MockMarketDataProvider
from app.data.providers.yahoo import YahooFinanceProvider

_provider_registry: dict[str, type[MarketDataProvider]] = {
    "yahoo": YahooFinanceProvider,
    "mock": MockMarketDataProvider,
}


def get_market_data_provider(provider_name: str | None = None) -> MarketDataProvider:
    """Factory function returning the configured market data provider instance.

    Guarantees that quantitative algorithms and API endpoints access market data
    strictly via the MarketDataProvider interface, enabling zero-code provider swaps.
    """
    target = (provider_name or settings.MARKET_DATA_PROVIDER).lower()
    provider_cls = _provider_registry.get(target)
    if not provider_cls:
        raise ValueError(
            f"Unsupported market data provider: '{target}'. Available: {list(_provider_registry.keys())}"
        )
    return provider_cls()
