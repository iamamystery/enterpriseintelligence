from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scrape_job import STATUS_FAILED, STATUS_RUNNING, STATUS_SUCCESS, ScrapeJob
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


async def test_delete_finished_older_than_removes_only_stale_finished_jobs(db_session: AsyncSession):
    now = datetime.now(UTC)
    old_finished = ScrapeJob(
        job_name="nvd_ingestion",
        status=STATUS_SUCCESS,
        started_at=now - timedelta(days=100),
        finished_at=now - timedelta(days=100),
        items_processed=5,
    )
    recent_finished = ScrapeJob(
        job_name="nvd_ingestion",
        status=STATUS_SUCCESS,
        started_at=now - timedelta(days=1),
        finished_at=now - timedelta(days=1),
        items_processed=5,
    )
    old_still_running = ScrapeJob(
        job_name="nvd_ingestion",
        status=STATUS_RUNNING,
        started_at=now - timedelta(days=100),
        finished_at=None,
    )
    db_session.add_all([old_finished, recent_finished, old_still_running])
    await db_session.flush()

    service = ScrapeJobService(db_session)
    deleted = await service.delete_finished_older_than(days=90)

    assert deleted == 1
    remaining_items, _ = await service.list_recent(limit=100)
    remaining_ids = {job.id for job in remaining_items}
    assert old_finished.id not in remaining_ids
    assert recent_finished.id in remaining_ids
    assert old_still_running.id in remaining_ids
