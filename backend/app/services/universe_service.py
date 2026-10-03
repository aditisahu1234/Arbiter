from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset import Asset
from app.models.universe import Universe, UniverseMember
from app.schemas.universe import UniverseCreate


class UniverseService:
    """Service layer for Universe definition, membership, and constituent querying."""

    async def create_universe(self, db: AsyncSession, universe_in: UniverseCreate) -> Universe:
        universe = Universe(**universe_in.model_dump())
        db.add(universe)
        await db.flush()
        await db.refresh(universe)
        return universe

    async def get_by_name(
        self, db: AsyncSession, name: str, load_members: bool = False
    ) -> Universe | None:
        query = select(Universe).where(Universe.name == name.upper())
        if load_members:
            query = query.options(selectinload(Universe.members).selectinload(UniverseMember.asset))
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(
        self, db: AsyncSession, universe_id: int, load_members: bool = False
    ) -> Universe | None:
        query = select(Universe).where(Universe.id == universe_id)
        if load_members:
            query = query.options(selectinload(Universe.members).selectinload(UniverseMember.asset))
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def list_universes(self, db: AsyncSession) -> Sequence[Universe]:
        query = (
            select(Universe).options(selectinload(Universe.members)).order_by(Universe.name.asc())
        )
        result = await db.execute(query)
        return result.scalars().all()

    async def add_member(
        self,
        db: AsyncSession,
        universe_id: int,
        asset_id: int,
        weight: float | None = None,
    ) -> UniverseMember:
        existing = await db.execute(
            select(UniverseMember).where(
                UniverseMember.universe_id == universe_id,
                UniverseMember.asset_id == asset_id,
            )
        )
        member = existing.scalar_one_or_none()
        if member:
            member.weight = weight
            await db.flush()
            return member

        new_member = UniverseMember(
            universe_id=universe_id,
            asset_id=asset_id,
            weight=weight,
        )
        db.add(new_member)
        await db.flush()
        await db.refresh(new_member)
        return new_member

    async def get_universe_assets(self, db: AsyncSession, universe_name: str) -> Sequence[Asset]:
        query = (
            select(Asset)
            .join(UniverseMember, Asset.id == UniverseMember.asset_id)
            .join(Universe, UniverseMember.universe_id == Universe.id)
            .where(Universe.name == universe_name.upper(), Asset.active.is_(True))
            .order_by(Asset.symbol.asc())
        )
        result = await db.execute(query)
        return result.scalars().all()

    async def set_universe_constituents(
        self,
        db: AsyncSession,
        universe_name: str,
        asset_ids: list[int],
    ) -> None:
        universe = await self.get_by_name(db, universe_name)
        if not universe:
            raise ValueError(f"Universe {universe_name} not found")

        # Delete existing members
        await db.execute(delete(UniverseMember).where(UniverseMember.universe_id == universe.id))

        # Add new members
        for asset_id in asset_ids:
            member = UniverseMember(universe_id=universe.id, asset_id=asset_id)
            db.add(member)
        await db.flush()


universe_service = UniverseService()
