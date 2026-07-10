import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import Source


class SourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, source_id: uuid.UUID) -> Source | None:
        return await self.session.get(Source, source_id)

    async def get_by_name(self, name: str) -> Source | None:
        result = await self.session.execute(select(Source).where(Source.name == name))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Source]:
        result = await self.session.execute(select(Source).order_by(Source.name))
        return list(result.scalars().all())

    async def create(self, source: Source) -> Source:
        self.session.add(source)
        await self.session.flush()
        await self.session.refresh(source)
        return source
