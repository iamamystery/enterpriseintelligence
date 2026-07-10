from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scrape_job import STATUS_FAILED, STATUS_RUNNING, STATUS_SUCCESS
from app.services.scrape_job_service import ScrapeJobService


async def test_start_creates_running_job(db_session: AsyncSession):
    job = await ScrapeJobService(db_session).start("nvd_ingestion")

    assert job.job_name == "nvd_ingestion"
    assert job.status == STATUS_RUNNING
    assert job.finished_at is None
    assert job.items_processed is None


async def test_mark_success_updates_job(db_session: AsyncSession):
    service = ScrapeJobService(db_session)
    job = await service.start("cisa_kev_ingestion")

    await service.mark_success(job.id, items_processed=42)

    updated = await service.get_by_id(job.id)
    assert updated.status == STATUS_SUCCESS
    assert updated.items_processed == 42
    assert updated.finished_at is not None


async def test_mark_failed_updates_job(db_session: AsyncSession):
    service = ScrapeJobService(db_session)
    job = await service.start("redhat_ingestion")

    await service.mark_failed(job.id, "ConnectionError: timed out")

    updated = await service.get_by_id(job.id)
    assert updated.status == STATUS_FAILED
    assert updated.error_message == "ConnectionError: timed out"
    assert updated.finished_at is not None


async def test_list_recent_filters_by_job_name(db_session: AsyncSession):
    service = ScrapeJobService(db_session)
    await service.start("nvd_ingestion")
    await service.start("mitre_backfill")
    await service.start("mitre_backfill")

    items, total = await service.list_recent(job_name="mitre_backfill")
    assert total == 2
    assert all(job.job_name == "mitre_backfill" for job in items)


async def test_list_recent_orders_newest_first(db_session: AsyncSession):
    service = ScrapeJobService(db_session)
    first = await service.start("nvd_ingestion")
    second = await service.start("nvd_ingestion")

    items, _ = await service.list_recent(job_name="nvd_ingestion")
    assert items[0].id == second.id
    assert items[1].id == first.id
