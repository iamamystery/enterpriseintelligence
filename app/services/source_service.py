import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.source import Source
from app.repositories.postgres.source_repository import SourceRepository


class SourceService:
    def __init__(self, session: AsyncSession) -> None:
        self.sources = SourceRepository(session)

    async def list_all(self) -> list[Source]:
        return await self.sources.list_all()

    async def get_by_id(self, source_id: uuid.UUID) -> Source:
        source = await self.sources.get_by_id(source_id)
        if source is None:
            raise NotFoundError(f"Source '{source_id}' not found")
        return source
