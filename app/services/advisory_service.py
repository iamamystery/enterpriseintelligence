import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.advisory import Advisory
from app.repositories.postgres.advisory_repository import AdvisoryRepository
from app.repositories.postgres.source_repository import SourceRepository
from app.schemas.advisory import AdvisoryCreate


class AdvisoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.advisories = AdvisoryRepository(session)
        self.sources = SourceRepository(session)

    async def create_advisory(self, data: AdvisoryCreate) -> Advisory:
        if await self.advisories.get_by_advisory_id(data.advisory_id) is not None:
            raise AlreadyExistsError(f"An advisory with ID '{data.advisory_id}' already exists")

        if await self.sources.get_by_id(data.source_id) is None:
            raise NotFoundError(f"Source '{data.source_id}' not found")

        advisory = await self.advisories.create(
            Advisory(
                advisory_id=data.advisory_id,
                title=data.title,
                summary=data.summary,
                url=data.url,
                published_date=data.published_date,
                cve_ids=data.cve_ids,
                source_id=data.source_id,
            )
        )
        await self.session.commit()
        return advisory

    async def list_recent(
        self, *, source_id: uuid.UUID | None = None, limit: int = 20, offset: int = 0
    ) -> tuple[list[Advisory], int]:
        return await self.advisories.list_recent(source_id=source_id, limit=limit, offset=offset)

    async def get_by_advisory_id(self, advisory_id: str) -> Advisory:
        advisory = await self.advisories.get_by_advisory_id(advisory_id)
        if advisory is None:
            raise NotFoundError(f"Advisory '{advisory_id}' not found")
        return advisory
