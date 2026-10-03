import pytest

from app.core.database import db_manager, init_db
from app.schemas.asset import AssetCreate, AssetFilter
from app.schemas.universe import UniverseCreate
from app.services.asset_service import asset_service
from app.services.universe_service import universe_service


@pytest.mark.asyncio
async def test_asset_and_universe_lifecycle():
    await init_db()
    assert db_manager.session_maker is not None

    async with db_manager.session_maker() as db:
        # Create test universe
        u_in = UniverseCreate(
            name="TEST_TECH",
            display_name="Tech Innovation Index",
            description="Leading technology innovators",
            is_active=True,
        )
        universe = await universe_service.create_universe(db, u_in)
        assert universe.id is not None
        assert universe.name == "TEST_TECH"

        # Create test assets
        a1_in = AssetCreate(
            symbol="INFY_TEST",
            exchange="NSE",
            name="Infosys Test Ltd",
            asset_type="EQUITY",
            currency="INR",
            country="IN",
            sector="Information Technology",
            industry="IT Services",
            provider_symbol="INFY.NS",
            active=True,
        )
        a2_in = AssetCreate(
            symbol="TCS_TEST",
            exchange="NSE",
            name="TCS Test Ltd",
            asset_type="EQUITY",
            currency="INR",
            country="IN",
            sector="Information Technology",
            industry="IT Services",
            provider_symbol="TCS.NS",
            active=True,
        )

        asset1 = await asset_service.create_asset(db, a1_in)
        asset2 = await asset_service.create_asset(db, a2_in)
        assert asset1.id is not None
        assert asset2.id is not None

        # Add to universe
        await universe_service.add_member(db, universe.id, asset1.id, weight=0.6)
        await universe_service.add_member(db, universe.id, asset2.id, weight=0.4)

        # Query universe assets
        u_assets = await universe_service.get_universe_assets(db, "TEST_TECH")
        symbols = [a.symbol for a in u_assets]
        assert "INFY_TEST" in symbols
        assert "TCS_TEST" in symbols

        # Test asset search and filtering
        assets, total = await asset_service.list_assets(
            db,
            AssetFilter(
                search="Infosys",
                sector="Information Technology",
                universe="TEST_TECH",
            ),
        )
        assert total >= 1
        assert any(a.symbol == "INFY_TEST" for a in assets)

        # Test single asset lookup
        lookup = await asset_service.get_by_symbol(db, "TCS_TEST", "NSE")
        assert lookup is not None
        assert lookup.provider_symbol == "TCS.NS"
