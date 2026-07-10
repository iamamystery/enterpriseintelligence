import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models.scrape_job import STATUS_FAILED, STATUS_SUCCESS, ScrapeJob
from app.tasks.scrape_tasks import _run_tracked


async def test_run_tracked_records_success(test_engine: AsyncEngine):
    job_name = f"test-job-{uuid.uuid4().hex[:8]}"
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def fake_ingest(session: AsyncSession) -> int:
        return 7

    try:
        await _run_tracked(job_name, fake_ingest, session_factory=session_factory)

        async with session_factory() as session:
            job = (
                await session.execute(select(ScrapeJob).where(ScrapeJob.job_name == job_name))
            ).scalar_one()
            assert job.status == STATUS_SUCCESS
            assert job.items_processed == 7
            assert job.finished_at is not None
    finally:
        async with session_factory() as session:
            await session.execute(delete(ScrapeJob).where(ScrapeJob.job_name == job_name))
            await session.commit()


async def test_run_tracked_records_failure(test_engine: AsyncEngine):
    job_name = f"test-job-{uuid.uuid4().hex[:8]}"
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def failing_ingest(session: AsyncSession) -> int:
        raise ValueError("simulated scraper failure")

    try:
        await _run_tracked(job_name, failing_ingest, session_factory=session_factory)

        async with session_factory() as session:
            job = (
                await session.execute(select(ScrapeJob).where(ScrapeJob.job_name == job_name))
            ).scalar_one()
            assert job.status == STATUS_FAILED
            assert "simulated scraper failure" in job.error_message
    finally:
        async with session_factory() as session:
            await session.execute(delete(ScrapeJob).where(ScrapeJob.job_name == job_name))
            await session.commit()
