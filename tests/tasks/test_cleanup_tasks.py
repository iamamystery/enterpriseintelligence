import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models.scrape_job import STATUS_SUCCESS, ScrapeJob
from app.tasks.cleanup_tasks import run_scrape_job_cleanup


async def test_run_scrape_job_cleanup_removes_only_old_finished_jobs(test_engine: AsyncEngine):
    job_name = f"test-cleanup-{uuid.uuid4().hex[:8]}"
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    now = datetime.now(UTC)

    async with session_factory() as session:
        old_job = ScrapeJob(
            job_name=job_name,
            status=STATUS_SUCCESS,
            started_at=now - timedelta(days=settings.SCRAPE_JOB_RETENTION_DAYS + 30),
            finished_at=now - timedelta(days=settings.SCRAPE_JOB_RETENTION_DAYS + 30),
            items_processed=1,
        )
        recent_job = ScrapeJob(
            job_name=job_name,
            status=STATUS_SUCCESS,
            started_at=now - timedelta(days=1),
            finished_at=now - timedelta(days=1),
            items_processed=1,
        )
        session.add_all([old_job, recent_job])
        await session.commit()

    try:
        await run_scrape_job_cleanup(session_factory=session_factory)

        async with session_factory() as session:
            remaining = (
                await session.execute(select(ScrapeJob.status).where(ScrapeJob.job_name == job_name))
            ).scalars().all()
            assert remaining == [STATUS_SUCCESS]
    finally:
        async with session_factory() as session:
            await session.execute(delete(ScrapeJob).where(ScrapeJob.job_name == job_name))
            await session.commit()
