import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.core.duckdb import duckdb_manager
from app.core.logging import get_logger, setup_logging
from app.core.redis import cache_manager

# Initialize structured logging
setup_logging()
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown hooks."""
    logger.info("Starting Arbiter Quantitative Engine...", version="0.1.0")

    # 1. Initialize DB tables
    await init_db()

    # 2. Initialize DuckDB analytical engine
    duckdb_manager.get_connection()
    logger.info("DuckDB analytical engine initialized.")

    # 3. Initialize Redis client
    await cache_manager.get_client()

    logger.info("Arbiter startup complete. Ready for quantitative computation.")

    yield

    # Shutdown
    logger.info("Shutting down Arbiter...")
    duckdb_manager.close()
    logger.info("Arbiter shutdown complete.")


app = FastAPI(
    title=f"{settings.PROJECT_NAME} Platform",
    description="Quantitative Market Analysis & Strategy Research Platform API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_and_request_id(request: Request, call_next):
    """Attach unique request ID and measure processing latency."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start_time = time.perf_counter()

    response = await call_next(request)

    process_time_ms = (time.perf_counter() - start_time) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"

    return response


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint providing runtime and database status."""
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "version": "0.1.0",
    }
