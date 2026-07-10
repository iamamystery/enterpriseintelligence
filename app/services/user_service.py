from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.core.security import hash_password
from app.models.user import User
from app.repositories.postgres.role_repository import RoleRepository
from app.repositories.postgres.user_repository import UserRepository
from app.schemas.user import UserCreate


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.roles = RoleRepository(session)

    async def create_user(self, requesting_user: User, data: UserCreate) -> User:
        if await self.users.get_by_email(data.email) is not None:
            raise AlreadyExistsError(f"A user with email '{data.email}' already exists")

        role = await self.roles.get_by_name(data.role_name)
        if role is None:
            raise NotFoundError(f"Role '{data.role_name}' not found")

        user = await self.users.create(
            User(
                email=data.email,
                hashed_password=hash_password(data.password),
                full_name=data.full_name,
                organization_id=requesting_user.organization_id,
                role_id=role.id,
                is_superuser=False,
            )
        )
        await self.session.commit()
        return user
