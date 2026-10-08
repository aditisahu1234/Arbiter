"""Position and strategy calculation API endpoints."""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.duckdb import duckdb_manager
from app.data.storage import storage_manager
from app.models.position import Position, PositionStatus
from app.quant.strategies import StrategyConfig
from app.services.position_service import position_service
from app.services.strategy_calc_service import StrategyCalcEngine

router = APIRouter(prefix="/positions", tags=["Positions"])


class CreatePositionRequest(BaseModel):
    symbol: str
    signal_date: str
    entry_date: str
    entry_price: float
    fast_sma: int = Field(default=10, ge=2, le=200)
    slow_sma: int = Field(default=50, ge=5, le=500)
    atr_window: int = Field(default=14, ge=2, le=100)
    atr_multiplier: float = Field(default=2.0, ge=0.5, le=10.0)
    cost_bps: float = Field(default=10.0, ge=0.0, le=100.0)


class CreatePositionResponse(BaseModel):
    id: int
    symbol: str
    status: str
    signal_date: Optional[str]
    entry_date: Optional[str]
    entry_price: Optional[float]
    fast_sma: int
    slow_sma: int
    atr_window: int
    atr_multiplier: float
    cost_bps: float
    stop_price: Optional[float]
    current_price: Optional[float]
    created_at: str
    last_updated: str


class PositionDetailResponse(BaseModel):
    id: int
    symbol: str
    status: str
    signal_date: Optional[str]
    entry_date: Optional[str]
    entry_price: Optional[float]
    quantity: float
    stop_price: Optional[float]
    exit_signal: Optional[str]
    exit_date: Optional[str]
    exit_price: Optional[float]
    exit_reason: Optional[str]
    gross_pnl: float
    transaction_cost: float
    net_pnl: float
    current_price: Optional[float]
    created_at: str
    last_updated: str


class StrategyCalcRequest(BaseModel):
    symbol: str
    fast_sma: int = Field(default=10, ge=2, le=200)
    slow_sma: int = Field(default=50, ge=5, le=500)
    atr_window: int = Field(default=14, ge=2, le=100)
    atr_multiplier: float = Field(default=2.0, ge=0.5, le=10.0)
    cost_bps: float = Field(default=10.0, ge=0.0, le=100.0)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    strategy_date: Optional[str] = None


class DailyCalcResponse(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    adjusted_close: float
    fast_sma: Optional[float]
    slow_sma: Optional[float]
    prev_fast_sma: Optional[float]
    prev_slow_sma: Optional[float]
    true_range: Optional[float]
    atr: Optional[float]
    signal: str
    stop_price: Optional[float]
    entry_date: Optional[str]
    entry_price: Optional[float]
    exit_date: Optional[str]
    exit_price: Optional[float]
    exit_reason: Optional[str]
    position: Optional[str]


class StrategyCalcResponse(BaseModel):
    symbol: str
    config: dict
    calculations: List[DailyCalcResponse]
    signals: List[dict]
    trades: List[dict]
    selected_date: Optional[str] = None
    selected_calculation: Optional[DailyCalcResponse] = None


@router.post("", response_model=CreatePositionResponse)
async def create_position(
    req: CreatePositionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new tracked position."""
    # Validate the asset exists
    p_path = storage_manager.get_asset_parquet_path(req.symbol.upper())
    if not p_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No data available for {req.symbol.upper()}. Run ingestion first.",
        )

    position = await position_service.create_position(
        db=db,
        symbol=req.symbol,
        signal_date=req.signal_date,
        entry_date=req.entry_date,
        entry_price=req.entry_price,
        fast_sma=req.fast_sma,
        slow_sma=req.slow_sma,
        atr_window=req.atr_window,
        atr_multiplier=req.atr_multiplier,
        cost_bps=req.cost_bps,
    )

    return CreatePositionResponse(
        id=position.id,
        symbol=position.symbol,
        status=position.status.value,
        signal_date=position.signal_date,
        entry_date=position.entry_date,
        entry_price=position.entry_price,
        fast_sma=position.fast_sma,
        slow_sma=position.slow_sma,
        atr_window=position.atr_window,
        atr_multiplier=position.atr_multiplier,
        cost_bps=position.cost_bps,
        stop_price=position.stop_price,
        current_price=position.current_price,
        created_at=position.created_at.isoformat() if position.created_at else "",
        last_updated=position.last_updated.isoformat() if position.last_updated else "",
    )


@router.get("/open", response_model=List[PositionDetailResponse])
async def list_open_positions(
    db: AsyncSession = Depends(get_db),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
):
    """Get all open positions."""
    positions = await position_service.get_open_positions(db, symbol)
    return [
        PositionDetailResponse(
            id=p.id,
            symbol=p.symbol,
            status=p.status.value,
            signal_date=p.signal_date,
            entry_date=p.entry_date,
            entry_price=p.entry_price,
            quantity=p.quantity,
            stop_price=p.stop_price,
            exit_signal=p.exit_signal,
            exit_date=p.exit_date,
            exit_price=p.exit_price,
            exit_reason=p.exit_reason,
            gross_pnl=p.gross_pnl,
            transaction_cost=p.transaction_cost,
            net_pnl=p.net_pnl,
            current_price=p.current_price,
            created_at=p.created_at.isoformat() if p.created_at else "",
            last_updated=p.last_updated.isoformat() if p.last_updated else "",
        )
        for p in positions
    ]


@router.get("", response_model=List[PositionDetailResponse])
async def list_all_positions(
    db: AsyncSession = Depends(get_db),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    status: Optional[str] = Query(None, description="Filter by status: OPEN, CLOSED, EXITED"),
):
    """Get all positions with optional filtering."""
    if status and status.upper() == "OPEN":
        positions = await position_service.get_open_positions(db, symbol)
    else:
        positions = await position_service.get_closed_positions(db, symbol)
    
    return [
        PositionDetailResponse(
            id=p.id,
            symbol=p.symbol,
            status=p.status.value,
            signal_date=p.signal_date,
            entry_date=p.entry_date,
            entry_price=p.entry_price,
            quantity=p.quantity,
            stop_price=p.stop_price,
            exit_signal=p.exit_signal,
            exit_date=p.exit_date,
            exit_price=p.exit_price,
            exit_reason=p.exit_reason,
            gross_pnl=p.gross_pnl,
            transaction_cost=p.transaction_cost,
            net_pnl=p.net_pnl,
            current_price=p.current_price,
            created_at=p.created_at.isoformat() if p.created_at else "",
            last_updated=p.last_updated.isoformat() if p.last_updated else "",
        )
        for p in positions
    ]


@router.get("/{position_id}", response_model=PositionDetailResponse)
async def get_position(
    position_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single position by ID."""
    position = await position_service.get_position(db, position_id)
    if not position:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found")

    return PositionDetailResponse(
        id=position.id,
        symbol=position.symbol,
        status=position.status.value,
        signal_date=position.signal_date,
        entry_date=position.entry_date,
        entry_price=position.entry_price,
        quantity=position.quantity,
        stop_price=position.stop_price,
        exit_signal=position.exit_signal,
        exit_date=position.exit_date,
        exit_price=position.exit_price,
        exit_reason=position.exit_reason,
        gross_pnl=position.gross_pnl,
        transaction_cost=position.transaction_cost,
        net_pnl=position.net_pnl,
        current_price=position.current_price,
        created_at=position.created_at.isoformat() if position.created_at else "",
        last_updated=position.last_updated.isoformat() if position.last_updated else "",
    )


@router.post("/{position_id}/refresh")
async def refresh_position_price(
    position_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Refresh position price from latest market data."""
    position = await position_service.get_position(db, position_id)
    if not position:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found")
    if position.status != PositionStatus.OPEN:
        raise HTTPException(status_code=400, detail="Can only refresh open positions")

    # Get latest price
    df = storage_manager.load_normalized_ohlcv(position.symbol)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {position.symbol}")

    latest_close = float(df.iloc[-1]["close"])
    await position_service.refresh_position_price(db, position_id, latest_close)

    return {"symbol": position.symbol, "current_price": latest_close}


@router.post("/{position_id}/close")
async def close_position(
    position_id: int,
    exit_date: str = Query(..., description="Exit date YYYY-MM-DD"),
    exit_price: float = Query(..., description="Exit price"),
    exit_reason: str = Query("manual", description="Exit reason"),
    db: AsyncSession = Depends(get_db),
):
    """Manually close a position."""
    position = await position_service.close_position(
        db, position_id, exit_date, exit_price, exit_reason
    )
    if not position:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found or already closed")
    return PositionDetailResponse(
        id=position.id,
        symbol=position.symbol,
        status=position.status.value,
        signal_date=position.signal_date,
        entry_date=position.entry_date,
        entry_price=position.entry_price,
        quantity=position.quantity,
        stop_price=position.stop_price,
        exit_signal=position.exit_signal,
        exit_date=position.exit_date,
        exit_price=position.exit_price,
        exit_reason=position.exit_reason,
        gross_pnl=position.gross_pnl,
        transaction_cost=position.transaction_cost,
        net_pnl=position.net_pnl,
        current_price=position.current_price,
        created_at=position.created_at.isoformat() if position.created_at else "",
        last_updated=position.last_updated.isoformat() if position.last_updated else "",
    )


@router.post("/strategy-calculations", response_model=StrategyCalcResponse)
async def compute_strategy_calculations(
    req: StrategyCalcRequest,
):
    """Run strategy calculations for an asset."""
    symbol = req.symbol.upper()
    df = storage_manager.load_normalized_ohlcv(
        symbol=symbol,
        start_date=req.start_date,
        end_date=req.end_date,
    )
    if df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No data available for {symbol}. Run ingestion first.",
        )

    cfg = StrategyConfig(
        fast_sma=req.fast_sma,
        slow_sma=req.slow_sma,
        atr_window=req.atr_window,
        atr_multiplier=req.atr_multiplier,
        cost_bps=req.cost_bps,
    )
    engine = StrategyCalcEngine(cfg)
    result = engine.compute(df, symbol)

    # If strategy_date is provided, find that specific date's calculation
    selected_calc = None
    if req.strategy_date:
        for calc in result.calculations:
            if calc.date == req.strategy_date:
                selected_calc = calc
                break

    calculations = [
        DailyCalcResponse(
            date=c.date,
            open=c.open,
            high=c.high,
            low=c.low,
            close=c.close,
            adjusted_close=c.adjusted_close,
            fast_sma=c.fast_sma,
            slow_sma=c.slow_sma,
            prev_fast_sma=c.prev_fast_sma,
            prev_slow_sma=c.prev_slow_sma,
            true_range=c.true_range,
            atr=c.atr,
            signal=c.signal,
            stop_price=c.stop_price,
            entry_date=c.entry_date,
            entry_price=c.entry_price,
            exit_date=c.exit_date,
            exit_price=c.exit_price,
            exit_reason=c.exit_reason,
            position=c.position,
        )
        for c in result.calculations
    ]

    return StrategyCalcResponse(
        symbol=result.symbol,
        config={
            "fast_sma": result.config.fast_sma,
            "slow_sma": result.config.slow_sma,
            "atr_window": result.config.atr_window,
            "atr_multiplier": result.config.atr_multiplier,
            "cost_bps": result.config.cost_bps,
        },
        calculations=calculations,
        signals=result.signals,
        trades=result.trades,
        selected_date=result.strategy_date if req.strategy_date else None,
        selected_calculation=selected_calc,
    )
