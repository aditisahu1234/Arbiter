from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.universe import Universe, UniverseMember
from app.schemas.asset import AssetCreate, AssetFilter, AssetUpdate


class AssetService:
    """Service layer for asset identity and catalogue management."""

    async def create_asset(self, db: AsyncSession, asset_in: AssetCreate) -> Asset:
        asset = Asset(**asset_in.model_dump())
        db.add(asset)
        await db.flush()
        await db.refresh(asset)
        return asset

    async def get_by_id(self, db: AsyncSession, asset_id: int) -> Asset | None:
        result = await db.execute(select(Asset).where(Asset.id == asset_id))
        return result.scalar_one_or_none()

    async def get_by_symbol(
        self, db: AsyncSession, symbol: str, exchange: str = "NSE"
    ) -> Asset | None:
        result = await db.execute(
            select(Asset).where(Asset.symbol == symbol.upper(), Asset.exchange == exchange.upper())
        )
        return result.scalar_one_or_none()

    async def get_by_provider_symbol(self, db: AsyncSession, provider_symbol: str) -> Asset | None:
        result = await db.execute(select(Asset).where(Asset.provider_symbol == provider_symbol))
        return result.scalar_one_or_none()

    async def list_assets(
        self, db: AsyncSession, filter_params: AssetFilter
    ) -> tuple[Sequence[Asset], int]:
        query = select(Asset)

        if filter_params.active_only:
            query = query.where(Asset.active.is_(True))

        if filter_params.exchange:
            query = query.where(Asset.exchange == filter_params.exchange.upper())

        if filter_params.sector:
            query = query.where(Asset.sector == filter_params.sector)

        if filter_params.search:
            search_term = f"%{filter_params.search}%"
            query = query.where(
                (Asset.symbol.ilike(search_term))
                | (Asset.name.ilike(search_term))
                | (Asset.provider_symbol.ilike(search_term))
            )

        if filter_params.universe:
            query = (
                query.join(UniverseMember, Asset.id == UniverseMember.asset_id)
                .join(Universe, UniverseMember.universe_id == Universe.id)
                .where(Universe.name == filter_params.universe.upper())
            )

        # Count total matching
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Paginate
        query = (
            query.order_by(Asset.symbol.asc()).offset(filter_params.skip).limit(filter_params.limit)
        )
        result = await db.execute(query)
        assets = result.scalars().all()

        return assets, total

    async def update_asset(
        self, db: AsyncSession, asset: Asset, asset_update: AssetUpdate
    ) -> Asset:
        update_data = asset_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(asset, field, value)
        await db.flush()
        await db.refresh(asset)
        return asset

    async def bulk_upsert(self, db: AsyncSession, assets_in: list[AssetCreate]) -> list[Asset]:
        results: list[Asset] = []
        for asset_data in assets_in:
            existing = await self.get_by_symbol(
                db, symbol=asset_data.symbol, exchange=asset_data.exchange
            )
            if existing:
                for k, v in asset_data.model_dump().items():
                    setattr(existing, k, v)
                results.append(existing)
            else:
                new_asset = Asset(**asset_data.model_dump())
                db.add(new_asset)
                results.append(new_asset)
        await db.flush()
        return results


asset_service = AssetService()
