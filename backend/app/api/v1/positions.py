"""Position and strategy calculation API endpoints."""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.database import get_db, db_manager
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
    next_session_recommendation: Optional[dict] = None
    data_status: Optional[dict] = None


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


def _get_data_status(symbol: str, check_provider: bool = False) -> dict:
    """Get data freshness status using NSE trading calendar and provider availability.

    Market-close alone does not guarantee the provider has published today's
    completed candle (Yahoo Finance lags). When check_provider=True we query the
    provider's latest published session; the expected "current" session is the
    LATER of the NSE calendar expectation and the provider's actual latest candle.
    We never mark an asset as current merely because a request returned HTTP 200.
    """
    latest_ts = duckdb_manager.get_latest_timestamp(symbol)

    if latest_ts is None:
        return {
            "symbol": symbol,
            "has_data": False,
            "latest_date": None,
            "is_current": False,
            "status": "no_data",
            "message": "No data available. Run ingestion first.",
        }

    from datetime import datetime, timezone, timedelta

    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_tz)
    today_ist = now_ist.date()

    # NSE trading hours: 09:15 – 15:30 IST
    market_close_ist = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
    market_open_ist = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
    is_market_open = market_open_ist <= now_ist <= market_close_ist

    # Trading-day predicate: use the `holidays` package if installed, else weekday-only.
    try:
        import holidays
        nse_cal = holidays.India(years=[today_ist.year - 1, today_ist.year, today_ist.year + 1])
        is_trading_day = lambda d: d.weekday() < 5 and d not in nse_cal
    except ImportError:
        is_trading_day = lambda d: d.weekday() < 5

    # Determine the last expected completed NSE trading session from the calendar.
    if is_market_open:
        cursor = today_ist - timedelta(days=1)
        while not is_trading_day(cursor):
            cursor -= timedelta(days=1)
        expected_last_session = cursor
    else:
        if is_trading_day(today_ist):
            expected_last_session = today_ist
        else:
            cursor = today_ist - timedelta(days=1)
            while not is_trading_day(cursor):
                cursor -= timedelta(days=1)
            expected_last_session = cursor

    # Query the provider's actual latest published session if requested.
    provider_latest_date = None
    provider_available = True
    if check_provider:
        try:
            from app.data.providers.factory import get_market_data_provider
            import pandas as pd
            provider = get_market_data_provider()
            asset_symbol = symbol
            # Use the asset's provider symbol if available
            provider_latest_df = provider.get_latest_ohlcv(f"{asset_symbol}.NS" if not asset_symbol.endswith(".NS") else asset_symbol)
            if provider_latest_df is not None and not provider_latest_df.empty:
                provider_latest_date = pd.Timestamp(provider_latest_df["timestamp"].iloc[-1]).date()
        except Exception:
            provider_available = False

    # The effective "current" session is the LATER of the calendar expectation and
    # the provider's actual latest candle. This avoids marking data as stale when
    # the provider simply hasn't published today's candle yet.
    if provider_latest_date is not None:
        effective_last_session = max(expected_last_session, provider_latest_date)
        provider_lagging = expected_last_session > provider_latest_date
    else:
        effective_last_session = expected_last_session
        provider_lagging = False

    latest_date = latest_ts.date()
    # Data is "current" if it reaches the effective last session. If the provider
    # is lagging (today's candle not yet published), we use the provider's latest
    # as the bar for freshness, so the asset is current if it matches that.
    is_current = latest_date >= effective_last_session

    # Count trading days behind relative to the effective last session.
    trading_days_behind = 0
    if not is_current:
        cursor = latest_date + timedelta(days=1)
        while cursor <= effective_last_session:
            if is_trading_day(cursor):
                trading_days_behind += 1
            cursor += timedelta(days=1)

    result = {
        "symbol": symbol,
        "has_data": True,
        "latest_date": latest_date.isoformat(),
        # Backward-compatible key
        "last_completed_trading_day": expected_last_session.isoformat(),
        "expected_last_session": expected_last_session.isoformat(),
        "provider_latest_date": provider_latest_date.isoformat() if provider_latest_date else None,
        "provider_available": provider_available,
        "provider_lagging": provider_lagging,
        "is_current": is_current,
        "days_behind": (today_ist - latest_date).days,
        "trading_days_behind": trading_days_behind,
        "market_status": "open" if is_market_open else "closed",
        "needs_refresh": not is_current,
        "message": (
            "Data is current" if is_current
            else f"Data is {trading_days_behind} trading day(s) behind expected session {effective_last_session.isoformat()}"
            + (f" (provider last published {provider_latest_date.isoformat()})" if provider_latest_date else "")
        ),
    }
    return result


@router.get("/{symbol}/data-status")
async def get_asset_data_status(
    symbol: str,
    check_provider: bool = Query(False, description="Query provider for latest published session"),
):
    """Get data freshness status for an asset using NSE trading calendar."""
    return _get_data_status(symbol.upper(), check_provider=check_provider)


@router.post("/{symbol}/refresh-data")
async def refresh_asset_data(
    symbol: str,
):
    """Refresh data for an asset by fetching latest from provider."""
    from app.data.ingestion import ingestion_service
    from app.models.asset import Asset
    from sqlalchemy import select
    from app.core.database import db_manager

    symbol = symbol.upper()

    # Initialize database if needed
    if db_manager.session_maker is None:
        db_manager.init_engine()

    # Get asset from database
    async with db_manager.session_maker() as db:
        result = await db.execute(select(Asset).where(Asset.symbol == symbol))
        asset = result.scalar_one_or_none()

        if not asset:
            raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")

        # Get latest stored date
        latest_ts = duckdb_manager.get_latest_timestamp(symbol)
        latest_date = latest_ts.date() if latest_ts else None

        # Fetch from provider
        ingest_result = await ingestion_service.ingest_asset_historical(
            symbol=symbol,
            asset_id=asset.id,
            provider_symbol=asset.provider_symbol,
            years=1,  # Only fetch last year for incremental update
        )

        # Get new latest date
        new_latest_ts = duckdb_manager.get_latest_timestamp(symbol)
        new_latest_date = new_latest_ts.date() if new_latest_ts else None

        return {
            "symbol": symbol,
            "previous_latest_date": latest_date.isoformat() if latest_date else None,
            "new_latest_date": new_latest_date.isoformat() if new_latest_date else None,
            "rows_fetched": ingest_result.get("rows_ingested", 0),
            "status": ingest_result.get("status", "unknown"),
        }


@router.get("/{symbol}/live-quote")
async def get_asset_live_quote(symbol: str):
    """Return a bounded live/delayed intraday quote for the asset.

    This endpoint exposes the most recent verified price with its timestamp and
    a data_state (live / delayed / unavailable). It does NOT modify completed
    daily candles or historical backtests. If the provider has no usable
    current-session value, data_state is "unavailable" and the caller should
    fall back to the last completed daily candle.
    """
    from app.data.providers.factory import get_market_data_provider

    symbol = symbol.upper()
    provider = get_market_data_provider()

    # Determine the provider symbol (append .NS for NSE equities if needed)
    provider_symbol = symbol if symbol.endswith(".NS") else f"{symbol}.NS"

    # Check if the asset has stored data first (so we can label the fallback)
    latest_ts = duckdb_manager.get_latest_timestamp(symbol)
    fallback_date = latest_ts.date().isoformat() if latest_ts else None

    quote = provider.get_live_quote(provider_symbol)
    quote["fallback_daily_date"] = fallback_date
    return quote


@router.post("/strategy-calculations", response_model=StrategyCalcResponse)
async def compute_strategy_calculations(
    req: StrategyCalcRequest,
):
    """Run strategy calculations for an asset.
    
    Loads the full stored dataset for the symbol (for indicator warm-up),
    computes signals over the whole dataset, then filters calculations/signals/trades
    to the requested start_date/end_date interval. This preserves valid indicator
    values even when the user selects a short interval.
    """
    symbol = req.symbol.upper()
    # Load the full available dataset so SMA/ATR have proper warm-up history.
    # The engine filters to the requested interval after computing indicators.
    df = storage_manager.load_normalized_ohlcv(symbol=symbol)
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
    result = engine.compute(
        df, symbol,
        strategy_date=req.strategy_date,
        start_date=req.start_date,
        end_date=req.end_date,
    )

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

    # Convert selected_calc to response format if it exists
    selected_calc_response = None
    if selected_calc:
        selected_calc_response = DailyCalcResponse(
            date=selected_calc.date,
            open=selected_calc.open,
            high=selected_calc.high,
            low=selected_calc.low,
            close=selected_calc.close,
            adjusted_close=selected_calc.adjusted_close,
            fast_sma=selected_calc.fast_sma,
            slow_sma=selected_calc.slow_sma,
            prev_fast_sma=selected_calc.prev_fast_sma,
            prev_slow_sma=selected_calc.prev_slow_sma,
            true_range=selected_calc.true_range,
            atr=selected_calc.atr,
            signal=selected_calc.signal,
            stop_price=selected_calc.stop_price,
            entry_date=selected_calc.entry_date,
            entry_price=selected_calc.entry_price,
            exit_date=selected_calc.exit_date,
            exit_price=selected_calc.exit_price,
            exit_reason=selected_calc.exit_reason,
            position=selected_calc.position,
        )

    # Include current data freshness status
    data_status = _get_data_status(symbol)

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
        selected_calculation=selected_calc_response,
        next_session_recommendation=result.next_session_recommendation,
        data_status=data_status,
    )
