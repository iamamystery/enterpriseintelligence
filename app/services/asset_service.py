import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.asset import Asset
from app.models.user import User
from app.repositories.postgres.asset_repository import AssetRepository
from app.schemas.asset import AssetCreate


class AssetService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.assets = AssetRepository(session)

    async def create_asset(self, requesting_user: User, data: AssetCreate) -> Asset:
        asset = await self.assets.create(
            Asset(
                name=data.name,
                asset_type=data.asset_type,
                vendor=data.vendor,
                product=data.product,
                version=data.version,
                ip_address=data.ip_address,
                organization_id=requesting_user.organization_id,
            )
        )
        await self.session.commit()
        return asset

    async def list_for_organization(
        self, requesting_user: User, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[Asset], int]:
        return await self.assets.list_for_organization(
            requesting_user.organization_id, limit=limit, offset=offset
        )

    async def get_by_id(self, requesting_user: User, asset_id: uuid.UUID) -> Asset:
        asset = await self.assets.get_by_id(asset_id)
        if asset is None or asset.organization_id != requesting_user.organization_id:
            raise NotFoundError(f"Asset '{asset_id}' not found")
        return asset
