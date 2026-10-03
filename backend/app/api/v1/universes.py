from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.universe_service import universe_service

router = APIRouter(prefix="/universes", tags=["Universes"])


@router.get("", response_model=list[dict[str, Any]])
async def list_universes(db: AsyncSession = Depends(get_db)):
    """List all universes with constituent counts."""
    universes = await universe_service.list_universes(db)
    return [
        {
            "id": u.id,
            "name": u.name,
            "display_name": u.display_name,
            "description": u.description,
            "is_active": u.is_active,
            "member_count": len(u.members),
        }
        for u in universes
    ]


@router.get("/{name}")
async def get_universe_detail(name: str, db: AsyncSession = Depends(get_db)):
    """Get universe detail with constituent assets list."""
    universe = await universe_service.get_by_name(db, name, load_members=True)
    if not universe:
        raise HTTPException(status_code=404, detail=f"Universe '{name}' not found")

    members = []
    for m in universe.members:
        members.append(
            {
                "asset_id": m.asset.id,
                "symbol": m.asset.symbol,
                "name": m.asset.name,
                "exchange": m.asset.exchange,
                "sector": m.asset.sector,
                "weight": m.weight,
            }
        )

    return {
        "id": universe.id,
        "name": universe.name,
        "display_name": universe.display_name,
        "description": universe.description,
        "member_count": len(members),
        "members": members,
    }
