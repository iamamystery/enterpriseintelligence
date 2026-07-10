import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.scrape_job import STATUS_FAILED, STATUS_RUNNING, STATUS_SUCCESS, ScrapeJob
from app.repositories.postgres.scrape_job_repository import ScrapeJobRepository


class ScrapeJobService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.scrape_jobs = ScrapeJobRepository(session)

    async def start(self, job_name: str) -> ScrapeJob:
        job = await self.scrape_jobs.create(
            ScrapeJob(job_name=job_name, status=STATUS_RUNNING, started_at=datetime.now(UTC))
        )
        await self.session.commit()
        return job

    async def mark_success(self, scrape_job_id: uuid.UUID, items_processed: int) -> None:
        job = await self.scrape_jobs.get_by_id(scrape_job_id)
        if job is None:
            return
        job.status = STATUS_SUCCESS
        job.finished_at = datetime.now(UTC)
        job.items_processed = items_processed
        await self.session.commit()

    async def mark_failed(self, scrape_job_id: uuid.UUID, error_message: str) -> None:
        job = await self.scrape_jobs.get_by_id(scrape_job_id)
        if job is None:
            return
        job.status = STATUS_FAILED
        job.finished_at = datetime.now(UTC)
        job.error_message = error_message
        await self.session.commit()

    async def list_recent(
        self, *, job_name: str | None = None, limit: int = 20, offset: int = 0
    ) -> tuple[list[ScrapeJob], int]:
        return await self.scrape_jobs.list_recent(job_name=job_name, limit=limit, offset=offset)

    async def get_by_id(self, scrape_job_id: uuid.UUID) -> ScrapeJob:
        job = await self.scrape_jobs.get_by_id(scrape_job_id)
        if job is None:
            raise NotFoundError(f"Scrape job '{scrape_job_id}' not found")
        return job
