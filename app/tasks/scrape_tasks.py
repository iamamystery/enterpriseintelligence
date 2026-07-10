import logging

from app.database.postgres import AsyncSessionLocal
from app.repositories.postgres.vulnerability_repository import VulnerabilityRepository
from app.services.scraping_service import ScrapingService

logger = logging.getLogger(__name__)


async def run_nvd_ingestion() -> None:
    try:
        async with AsyncSessionLocal() as session:
            count = await ScrapingService(session).ingest_nvd_recent(results_per_page=50)
            logger.info("Scheduled NVD ingestion complete: %d CVEs", count)
    except Exception:
        logger.exception("Scheduled NVD ingestion failed")


async def run_cisa_kev_ingestion() -> None:
    try:
        async with AsyncSessionLocal() as session:
            count = await ScrapingService(session).ingest_cisa_kev()
            logger.info("Scheduled CISA KEV ingestion complete: %d entries", count)
    except Exception:
        logger.exception("Scheduled CISA KEV ingestion failed")


async def run_redhat_ingestion() -> None:
    try:
        async with AsyncSessionLocal() as session:
            count = await ScrapingService(session).ingest_redhat_recent(per_page=50)
            logger.info("Scheduled Red Hat ingestion complete: %d CVEs", count)
    except Exception:
        logger.exception("Scheduled Red Hat ingestion failed")


async def run_mitre_backfill(batch_size: int = 25) -> None:
    try:
        async with AsyncSessionLocal() as session:
            cve_ids = await VulnerabilityRepository(session).list_cve_ids_missing_mitre_enrichment(
                limit=batch_size
            )
            if not cve_ids:
                logger.info("Scheduled MITRE backfill: nothing to enrich")
                return
            count = await ScrapingService(session).ingest_mitre_cves(cve_ids)
            logger.info("Scheduled MITRE backfill complete: %d CVEs", count)
    except Exception:
        logger.exception("Scheduled MITRE backfill failed")
