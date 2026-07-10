import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.role import Role
from app.repositories.postgres.role_repository import RoleRepository
from app.schemas.role import RoleCreate


class RoleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.roles = RoleRepository(session)

    async def create_role(self, data: RoleCreate) -> Role:
        if await self.roles.get_by_name(data.name) is not None:
            raise AlreadyExistsError(f"A role named '{data.name}' already exists")

        role = await self.roles.create(Role(name=data.name, permissions=data.permissions))
        await self.session.commit()
        return role

    async def list_all(self) -> list[Role]:
        return await self.roles.list_all()

    async def get_by_id(self, role_id: uuid.UUID) -> Role:
        role = await self.roles.get_by_id(role_id)
        if role is None:
            raise NotFoundError(f"Role '{role_id}' not found")
        return role
