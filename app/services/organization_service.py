from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.organization import Organization
from app.models.user import User
from app.repositories.postgres.organization_repository import OrganizationRepository


class OrganizationService:
    def __init__(self, session: AsyncSession) -> None:
        self.organizations = OrganizationRepository(session)

    async def get_current(self, user: User) -> Organization:
        organization = await self.organizations.get_by_id(user.organization_id)
        if organization is None:
            raise NotFoundError("Organization not found")
        return organization
