import logging
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.postgres import AsyncSessionLocal
from app.services.scrape_job_service import ScrapeJobService

logger = logging.getLogger(__name__)


async def run_scrape_job_cleanup(
    *, session_factory: Callable[[], AsyncSession] = AsyncSessionLocal
) -> None:
    try:
        async with session_factory() as session:
            deleted = await ScrapeJobService(session).delete_finished_older_than(
                settings.SCRAPE_JOB_RETENTION_DAYS
            )
            logger.info(
                "Scrape job cleanup complete: removed %d rows older than %d days",
                deleted,
                settings.SCRAPE_JOB_RETENTION_DAYS,
            )
    except Exception:
        logger.exception("Scrape job cleanup failed")
