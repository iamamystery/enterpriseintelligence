import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset


class AssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, asset_id: uuid.UUID) -> Asset | None:
        return await self.session.get(Asset, asset_id)

    async def list_for_organization(
        self, organization_id: uuid.UUID, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[Asset], int]:
        total = (
            await self.session.execute(
                select(func.count())
                .select_from(Asset)
                .where(Asset.organization_id == organization_id)
            )
        ).scalar_one()

        result = await self.session.execute(
            select(Asset)
            .where(Asset.organization_id == organization_id)
            .order_by(Asset.name)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def create(self, asset: Asset) -> Asset:
        self.session.add(asset)
        await self.session.flush()
        await self.session.refresh(asset)
        return asset

    async def list_matching_vendor_product(
        self,
        organization_id: uuid.UUID,
        *,
        vendor: str,
        product: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Asset], int]:
        conditions = (
            Asset.organization_id == organization_id,
            func.lower(Asset.vendor) == vendor.lower(),
            func.lower(Asset.product) == product.lower(),
        )

        total = (
            await self.session.execute(select(func.count()).select_from(Asset).where(*conditions))
        ).scalar_one()

        result = await self.session.execute(
            select(Asset).where(*conditions).order_by(Asset.name).limit(limit).offset(offset)
        )
        return list(result.scalars().all()), total

    async def search(
        self, organization_id: uuid.UUID, *, keyword: str, limit: int = 20, offset: int = 0
    ) -> tuple[list[Asset], int]:
        pattern = f"%{keyword}%"
        conditions = (
            Asset.organization_id == organization_id,
            or_(
                Asset.name.ilike(pattern),
                Asset.vendor.ilike(pattern),
                Asset.product.ilike(pattern),
            ),
        )

        total = (
            await self.session.execute(select(func.count()).select_from(Asset).where(*conditions))
        ).scalar_one()

        result = await self.session.execute(
            select(Asset).where(*conditions).order_by(Asset.name).limit(limit).offset(offset)
        )
        return list(result.scalars().all()), total
