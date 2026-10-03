"""APScheduler setup for daily market data ingestion."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.logging import get_logger
from app.jobs.daily_ingestion import run_daily_ingestion_job

logger = get_logger("scheduler")


def setup_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler for daily market data ingestion."""
    scheduler = AsyncIOScheduler(timezone=settings.SCHEDULER_TIMEZONE)

    if settings.ENABLE_SCHEDULER:
        # Run daily at market close (15:30 IST) + 30 min buffer for data availability
        scheduler.add_job(
            run_daily_ingestion_job,
            trigger=CronTrigger(
                hour=16,
                minute=0,
                day_of_week="mon-fri",
                timezone=settings.SCHEDULER_TIMEZONE,
            ),
            id="daily_market_ingestion",
            name="Daily Market Data Ingestion",
            misfire_grace_time=3600,
        )
        logger.info("Scheduler configured for daily ingestion at 16:00 IST")
    else:
        logger.info("Scheduler disabled in config")

    return scheduler


def start_scheduler(scheduler: AsyncIOScheduler) -> None:
    """Start the APScheduler."""
    if settings.ENABLE_SCHEDULER:
        scheduler.start()
        logger.info("Scheduler started")
    else:
        logger.info("Scheduler not started (disabled)")
