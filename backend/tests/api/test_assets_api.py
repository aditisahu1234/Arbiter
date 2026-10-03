import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_assets_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test listing assets
        res = await client.get("/api/v1/assets?limit=10")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] > 0
        assert len(data["items"]) <= 10

        # Test listing universes
        u_res = await client.get("/api/v1/universes")
        assert u_res.status_code == 200
        u_data = u_res.json()
        assert len(u_data) > 0
        names = [u["name"] for u in u_data]
        assert "NIFTY50" in names

        # Test lakehouse status
        l_res = await client.get("/api/v1/market-data/lakehouse")
        assert l_res.status_code == 200
        l_data = l_res.json()
        assert "total_files" in l_data
        assert "total_bars_ingested" in l_data
        assert l_data["total_files"] >= 10  # We ingested 11 assets!
        assert l_data["total_bars_ingested"] >= 10000

        # Test single asset OHLCV
        ohlcv_res = await client.get("/api/v1/assets/RELIANCE/ohlcv?limit=5")
        assert ohlcv_res.status_code == 200
        ohlcv_data = ohlcv_res.json()
        assert ohlcv_data["symbol"] == "RELIANCE"
        assert len(ohlcv_data["data"]) == 5
        assert "close" in ohlcv_data["data"][0]
        assert "open" in ohlcv_data["data"][0]
