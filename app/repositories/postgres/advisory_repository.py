import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.advisory import Advisory


class AdvisoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, advisory_pk: uuid.UUID) -> Advisory | None:
        return await self.session.get(Advisory, advisory_pk)

    async def get_by_advisory_id(self, advisory_id: str) -> Advisory | None:
        result = await self.session.execute(
            select(Advisory).where(Advisory.advisory_id == advisory_id)
        )
        return result.scalar_one_or_none()

    async def list_recent(
        self,
        *,
        source_id: uuid.UUID | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Advisory], int]:
        conditions = []
        if source_id is not None:
            conditions.append(Advisory.source_id == source_id)

        total = (
            await self.session.execute(select(func.count()).select_from(Advisory).where(*conditions))
        ).scalar_one()

        result = await self.session.execute(
            select(Advisory)
            .where(*conditions)
            .order_by(Advisory.published_date.desc().nulls_last())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def create(self, advisory: Advisory) -> Advisory:
        self.session.add(advisory)
        await self.session.flush()
        await self.session.refresh(advisory)
        return advisory

    async def search(
        self, *, keyword: str, limit: int = 20, offset: int = 0
    ) -> tuple[list[Advisory], int]:
        pattern = f"%{keyword}%"
        conditions = (
            or_(
                Advisory.advisory_id.ilike(pattern),
                Advisory.title.ilike(pattern),
                Advisory.summary.ilike(pattern),
            ),
        )

        total = (
            await self.session.execute(select(func.count()).select_from(Advisory).where(*conditions))
        ).scalar_one()

        result = await self.session.execute(
            select(Advisory)
            .where(*conditions)
            .order_by(Advisory.published_date.desc().nulls_last())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total
