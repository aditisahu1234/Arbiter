from fastapi import APIRouter

from app.api.v1.assets import router as assets_router
from app.api.v1.market_data import router as market_data_router
from app.api.v1.universes import router as universes_router
from app.api.v1.indicators import router as indicators_router
from app.api.v1.backtest import router as backtest_router
from app.api.v1.risk import router as risk_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(assets_router)
api_v1_router.include_router(universes_router)
api_v1_router.include_router(market_data_router)
api_v1_router.include_router(indicators_router)
api_v1_router.include_router(backtest_router)
api_v1_router.include_router(risk_router)

__all__ = ["api_v1_router"]
