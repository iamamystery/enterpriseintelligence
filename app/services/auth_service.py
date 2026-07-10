import uuid

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AlreadyExistsError, AuthenticationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.organization import Organization
from app.models.role import Role
from app.models.user import User
from app.repositories.postgres.organization_repository import OrganizationRepository
from app.repositories.postgres.role_repository import RoleRepository
from app.repositories.postgres.user_repository import UserRepository
from app.schemas.auth import TokenResponse, UserLogin, UserRegister
from app.utils.helpers import slugify

DEFAULT_ADMIN_ROLE_NAME = "admin"
DEFAULT_ADMIN_PERMISSIONS = ["*"]


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.roles = RoleRepository(session)
        self.organizations = OrganizationRepository(session)

    async def register(self, data: UserRegister) -> User:
        if await self.users.get_by_email(data.email) is not None:
            raise AlreadyExistsError(f"A user with email '{data.email}' already exists")

        slug = slugify(data.organization_name)
        organization = await self.organizations.get_by_slug(slug)
        if organization is None:
            organization = await self.organizations.create(
                Organization(name=data.organization_name, slug=slug)
            )

        role = await self.roles.get_by_name(DEFAULT_ADMIN_ROLE_NAME)
        if role is None:
            role = await self.roles.create(
                Role(name=DEFAULT_ADMIN_ROLE_NAME, permissions=DEFAULT_ADMIN_PERMISSIONS)
            )

        user = await self.users.create(
            User(
                email=data.email,
                hashed_password=hash_password(data.password),
                full_name=data.full_name,
                organization_id=organization.id,
                role_id=role.id,
            )
        )
        await self.session.commit()
        return user

    async def login(self, data: UserLogin) -> TokenResponse:
        user = await self.users.get_by_email(data.email)
        if user is None or not verify_password(data.password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")
        if not user.is_active:
            raise AuthenticationError("User account is disabled")

        return TokenResponse(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
        )

    async def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Invalid or expired refresh token") from exc

        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid token type")

        user = await self.users.get_by_id(uuid.UUID(payload["sub"]))
        if user is None or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        return TokenResponse(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
        )
