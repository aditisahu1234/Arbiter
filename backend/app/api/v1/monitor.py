"""Market status and price monitor endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.price_monitor import price_monitor, get_market_status

router = APIRouter(prefix="/monitor", tags=["Monitor"])


@router.get("/market-status")
async def get_market_status_endpoint():
    """Get current market status (open/closed)."""
    return get_market_status()


@router.get("/positions/refresh")
async def refresh_all_positions(db: AsyncSession = Depends(get_db)):
    """Manually trigger price refresh for all open positions."""
    from app.models.position import Position, PositionStatus
    from sqlalchemy import select
    
    stmt = select(Position).where(Position.status == PositionStatus.OPEN)
    result = await db.execute(stmt)
    positions = list(result.scalars().all())
    
    refreshed = []
    for pos in positions:
        df = await db.run_sync(lambda: __import__('app.data.storage', fromlist=['storage_manager']).storage_manager.load_normalized_ohlcv(pos.symbol))
        if not df.empty:
            latest_close = float(df.iloc[-1]["close"])
            pos.current_price = latest_close
            refreshed.append({
                "id": pos.id,
                "symbol": pos.symbol,
                "current_price": latest_close,
            })
    
    await db.commit()
    return {"refreshed": len(refreshed), "positions": refreshed}
