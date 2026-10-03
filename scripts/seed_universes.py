import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.core.database import db_manager, init_db
from app.core.logging import get_logger, setup_logging
from app.data.seeds import (
    NIFTY_50_SYMBOLS,
    NIFTY_AUTO_SYMBOLS,
    NIFTY_BANK_SYMBOLS,
    NIFTY_ENERGY_SYMBOLS,
    NIFTY_FMCG_SYMBOLS,
    NIFTY_IT_SYMBOLS,
    PREDEFINED_UNIVERSES,
    get_all_initial_assets,
)
from app.models.asset import Asset
from app.models.universe import Universe, UniverseMember
from app.schemas.asset import AssetCreate
from app.schemas.universe import UniverseCreate
from app.services.asset_service import asset_service
from app.services.universe_service import universe_service

setup_logging()
logger = get_logger("seed")


async def seed_data():
    """Seed predefined universes and ~500 assets with universe memberships."""
    logger.info("Starting Arbiter universe and asset catalog seeding...")
    await init_db()

    assert db_manager.session_maker is not None
    async with db_manager.session_maker() as db:
        # 1. Seed Universes
        universe_map: dict[str, Universe] = {}
        for u_data in PREDEFINED_UNIVERSES:
            existing = await universe_service.get_by_name(db, u_data["name"])
            if not existing:
                u = await universe_service.create_universe(db, UniverseCreate(**u_data))
                universe_map[u.name] = u
                logger.info("Created universe", name=u.name)
            else:
                universe_map[existing.name] = existing

        # 2. Seed Assets
        all_assets_data = get_all_initial_assets()
        logger.info("Seeding assets catalog", count=len(all_assets_data))

        asset_objs: dict[str, Asset] = {}
        for a_data in all_assets_data:
            existing_asset = await asset_service.get_by_symbol(
                db, a_data["symbol"], a_data["exchange"]
            )
            if not existing_asset:
                asset_obj = await asset_service.create_asset(db, AssetCreate(**a_data))
                asset_objs[asset_obj.symbol] = asset_obj
            else:
                asset_objs[existing_asset.symbol] = existing_asset

        await db.commit()
        logger.info("Assets catalog seeded successfully", total_assets=len(asset_objs))

        # 3. Assign Universe Memberships
        # NIFTY 50
        nifty50_u = universe_map.get("NIFTY50")
        if nifty50_u:
            for symbol, _, _, _ in NIFTY_50_SYMBOLS:
                if symbol in asset_objs:
                    await universe_service.add_member(db, nifty50_u.id, asset_objs[symbol].id)

        # NIFTY Bank
        nifty_bank_u = universe_map.get("NIFTY_BANK")
        if nifty_bank_u:
            for symbol in NIFTY_BANK_SYMBOLS:
                if symbol in asset_objs:
                    await universe_service.add_member(db, nifty_bank_u.id, asset_objs[symbol].id)

        # NIFTY IT
        nifty_it_u = universe_map.get("NIFTY_IT")
        if nifty_it_u:
            for symbol in NIFTY_IT_SYMBOLS:
                if symbol in asset_objs:
                    await universe_service.add_member(db, nifty_it_u.id, asset_objs[symbol].id)

        # NIFTY Auto
        nifty_auto_u = universe_map.get("NIFTY_AUTO")
        if nifty_auto_u:
            for symbol in NIFTY_AUTO_SYMBOLS:
                if symbol in asset_objs:
                    await universe_service.add_member(db, nifty_auto_u.id, asset_objs[symbol].id)

        # NIFTY FMCG
        nifty_fmcg_u = universe_map.get("NIFTY_FMCG")
        if nifty_fmcg_u:
            for symbol in NIFTY_FMCG_SYMBOLS:
                if symbol in asset_objs:
                    await universe_service.add_member(db, nifty_fmcg_u.id, asset_objs[symbol].id)

        # NIFTY Energy
        nifty_energy_u = universe_map.get("NIFTY_ENERGY")
        if nifty_energy_u:
            for symbol in NIFTY_ENERGY_SYMBOLS:
                if symbol in asset_objs:
                    await universe_service.add_member(db, nifty_energy_u.id, asset_objs[symbol].id)

        # NIFTY 500 (all assets in catalog)
        nifty500_u = universe_map.get("NIFTY500")
        if nifty500_u:
            for asset_obj in asset_objs.values():
                await universe_service.add_member(db, nifty500_u.id, asset_obj.id)

        await db.commit()
        logger.info("Universe memberships populated successfully.")


if __name__ == "__main__":
    asyncio.run(seed_data())
