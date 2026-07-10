import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.tasks.cleanup_tasks import run_scrape_job_cleanup
from app.tasks.scrape_tasks import (
    run_cisa_kev_ingestion,
    run_mitre_backfill,
    run_nvd_ingestion,
    run_redhat_ingestion,
)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def configure_scheduler() -> None:
    scheduler.add_job(
        run_nvd_ingestion,
        trigger=IntervalTrigger(hours=6),
        id="nvd_ingestion",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        run_cisa_kev_ingestion,
        trigger=IntervalTrigger(hours=2),
        id="cisa_kev_ingestion",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        run_redhat_ingestion,
        trigger=IntervalTrigger(hours=6),
        id="redhat_ingestion",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        run_mitre_backfill,
        trigger=IntervalTrigger(hours=12),
        id="mitre_backfill",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        run_scrape_job_cleanup,
        trigger=IntervalTrigger(hours=24),
        id="scrape_job_cleanup",
        replace_existing=True,
        max_instances=1,
    )


def start_scheduler() -> None:
    configure_scheduler()
    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))


def shutdown_scheduler() -> None:
    scheduler.shutdown(wait=False)
    logger.info("Scheduler shut down")
