import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.postgres import AsyncSessionLocal
from app.repositories.postgres.vulnerability_repository import VulnerabilityRepository
from app.services.scrape_job_service import ScrapeJobService
from app.services.scraping_service import ScrapingService

logger = logging.getLogger(__name__)


async def _run_tracked(
    job_name: str,
    ingest: Callable[[AsyncSession], Awaitable[int]],
    *,
    session_factory: Callable[[], AsyncSession] = AsyncSessionLocal,
) -> None:
    async with session_factory() as tracking_session:
        job = await ScrapeJobService(tracking_session).start(job_name)

    try:
        async with session_factory() as session:
            count = await ingest(session)
        async with session_factory() as tracking_session:
            await ScrapeJobService(tracking_session).mark_success(job.id, count)
        logger.info("Scheduled %s complete: %d items", job_name, count)
    except Exception as exc:
        async with session_factory() as tracking_session:
            await ScrapeJobService(tracking_session).mark_failed(
                job.id, f"{type(exc).__name__}: {exc}"
            )
        logger.exception("Scheduled %s failed", job_name)


async def run_nvd_ingestion() -> None:
    await _run_tracked(
        "nvd_ingestion",
        lambda session: ScrapingService(session).ingest_nvd_recent(results_per_page=50),
    )


async def run_cisa_kev_ingestion() -> None:
    await _run_tracked("cisa_kev_ingestion", lambda session: ScrapingService(session).ingest_cisa_kev())


async def run_redhat_ingestion() -> None:
    await _run_tracked(
        "redhat_ingestion",
        lambda session: ScrapingService(session).ingest_redhat_recent(per_page=50),
    )


async def run_mitre_backfill(batch_size: int = 25) -> None:
    async def _ingest(session: AsyncSession) -> int:
        cve_ids = await VulnerabilityRepository(session).list_cve_ids_missing_mitre_enrichment(
            limit=batch_size
        )
        if not cve_ids:
            return 0
        return await ScrapingService(session).ingest_mitre_cves(cve_ids)

    await _run_tracked("mitre_backfill", _ingest)
