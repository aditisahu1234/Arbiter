import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_assets_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/assets?limit=10")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) <= 10

        u_res = await client.get("/api/v1/universes")
        assert u_res.status_code == 200
        u_data = u_res.json()
        assert len(u_data) > 0
        names = [u["name"] for u in u_data]
        assert "NIFTY50" in names

        h_res = await client.get("/health")
        assert h_res.status_code == 200
        assert h_res.json()["status"] == "ok"

        i_res = await client.get("/api/v1/indicators/sma?symbol=RELIANCE&window=20")
        assert i_res.status_code == 200
        assert "data" in i_res.json()

        # Backtest is POST endpoint
        b_res = await client.post("/api/v1/strategies/backtest", params={"symbol": "RELIANCE"})
        assert b_res.status_code in (200, 404)

        # Risk endpoints
        r_res = await client.get("/api/v1/risk/capm?symbol=RELIANCE")
        assert r_res.status_code in (200, 404)

        ff_res = await client.get("/api/v1/risk/fama-french?symbol=RELIANCE")
        assert ff_res.status_code in (200, 400, 404)
