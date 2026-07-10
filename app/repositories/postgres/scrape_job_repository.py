import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scrape_job import ScrapeJob


class ScrapeJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, scrape_job: ScrapeJob) -> ScrapeJob:
        self.session.add(scrape_job)
        await self.session.flush()
        await self.session.refresh(scrape_job)
        return scrape_job

    async def get_by_id(self, scrape_job_id: uuid.UUID) -> ScrapeJob | None:
        return await self.session.get(ScrapeJob, scrape_job_id)

    async def list_recent(
        self,
        *,
        job_name: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ScrapeJob], int]:
        conditions = []
        if job_name:
            conditions.append(ScrapeJob.job_name == job_name)

        total = (
            await self.session.execute(select(func.count()).select_from(ScrapeJob).where(*conditions))
        ).scalar_one()

        result = await self.session.execute(
            select(ScrapeJob)
            .where(*conditions)
            .order_by(ScrapeJob.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total
