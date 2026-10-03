import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_v1_router
from app.api.v1.indicators import router as indicators_router
from app.api.v1.backtest import router as backtest_router
from app.api.v1.risk import router as risk_router
from app.core.config import settings
from app.core.database import init_db
from app.core.duckdb import duckdb_manager
from app.core.logging import get_logger, setup_logging
from app.core.redis import cache_manager
from app.jobs import setup_scheduler, start_scheduler

setup_logging()
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Arbiter Quantitative Engine...", version="0.1.0")
    await init_db()
    duckdb_manager.get_connection()
    logger.info("DuckDB analytical engine initialized.")
    await cache_manager.get_client()

    # Setup and start scheduler
    scheduler = setup_scheduler()
    start_scheduler(scheduler)
    app.state.scheduler = scheduler

    logger.info("Arbiter startup complete. Ready for quantitative computation.")

    yield

    logger.info("Shutting down Arbiter...")
    duckdb_manager.close()
    if hasattr(app.state, "scheduler") and app.state.scheduler.running:
        app.state.scheduler.shutdown()
    logger.info("Arbiter shutdown complete.")


app = FastAPI(
    title=f"{settings.PROJECT_NAME} Platform",
    description="Quantitative Market Analysis & Strategy Research Platform API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.include_router(api_v1_router)
app.include_router(indicators_router)
app.include_router(backtest_router)
app.include_router(risk_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_and_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time_ms = (time.perf_counter() - start_time) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"
    return response


@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "version": "0.1.0",
    }
