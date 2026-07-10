import jwt
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AlreadyExistsError, AuthenticationError
from app.schemas.auth import UserLogin, UserRegister
from app.services.auth_service import AuthService


async def test_register_creates_organization_role_and_user(db_session: AsyncSession):
    data = UserRegister(
        email="newadmin@example.com",
        password="correcthorsebattery",
        full_name="New Admin",
        organization_name="Brand New Org",
    )
    user = await AuthService(db_session).register(data)

    assert user.email == "newadmin@example.com"
    assert user.is_superuser is False
    assert user.organization_id is not None
    assert user.role_id is not None


async def test_register_rejects_duplicate_organization_name(db_session: AsyncSession):
    await AuthService(db_session).register(
        UserRegister(
            email="founder@example.com",
            password="correcthorsebattery",
            full_name="Founder",
            organization_name="Shared Org",
        )
    )

    with pytest.raises(AlreadyExistsError):
        await AuthService(db_session).register(
            UserRegister(
                email="teammate@example.com",
                password="correcthorsebattery",
                full_name="Teammate",
                organization_name="Shared Org",
            )
        )


async def test_register_rejects_organization_name_that_slugifies_to_existing_slug(
    db_session: AsyncSession,
):
    await AuthService(db_session).register(
        UserRegister(
            email="founder2@example.com",
            password="correcthorsebattery",
            full_name="Founder",
            organization_name="Shared Org!!",
        )
    )

    with pytest.raises(AlreadyExistsError):
        await AuthService(db_session).register(
            UserRegister(
                email="impersonator@example.com",
                password="correcthorsebattery",
                full_name="Impersonator",
                organization_name="  shared   org  ",
            )
        )


async def test_register_duplicate_email_raises(db_session: AsyncSession):
    data = UserRegister(
        email="dup@example.com",
        password="correcthorsebattery",
        full_name="First",
        organization_name="Org One",
    )
    await AuthService(db_session).register(data)

    with pytest.raises(AlreadyExistsError):
        await AuthService(db_session).register(
            UserRegister(
                email="dup@example.com",
                password="anotherpassword1",
                full_name="Second",
                organization_name="Org Two",
            )
        )


async def test_login_succeeds_with_correct_password(db_session: AsyncSession):
    await AuthService(db_session).register(
        UserRegister(
            email="loginuser@example.com",
            password="correcthorsebattery",
            full_name="Login User",
            organization_name="Login Org",
        )
    )

    tokens = await AuthService(db_session).login(
        UserLogin(email="loginuser@example.com", password="correcthorsebattery")
    )
    assert tokens.access_token
    assert tokens.refresh_token
    assert tokens.token_type == "bearer"


async def test_login_fails_with_wrong_password(db_session: AsyncSession):
    await AuthService(db_session).register(
        UserRegister(
            email="wrongpass@example.com",
            password="correcthorsebattery",
            full_name="User",
            organization_name="Org",
        )
    )

    with pytest.raises(AuthenticationError):
        await AuthService(db_session).login(UserLogin(email="wrongpass@example.com", password="nope"))


async def test_login_fails_for_unknown_email(db_session: AsyncSession):
    with pytest.raises(AuthenticationError):
        await AuthService(db_session).login(UserLogin(email="ghost@example.com", password="whatever"))


async def test_refresh_issues_new_tokens(db_session: AsyncSession):
    await AuthService(db_session).register(
        UserRegister(
            email="refreshuser@example.com",
            password="correcthorsebattery",
            full_name="User",
            organization_name="Org",
        )
    )
    tokens = await AuthService(db_session).login(
        UserLogin(email="refreshuser@example.com", password="correcthorsebattery")
    )

    new_tokens = await AuthService(db_session).refresh(tokens.refresh_token)
    assert new_tokens.access_token
    assert new_tokens.refresh_token


async def test_refresh_rejects_access_token_used_as_refresh_token(db_session: AsyncSession):
    await AuthService(db_session).register(
        UserRegister(
            email="wrongtype@example.com",
            password="correcthorsebattery",
            full_name="User",
            organization_name="Org",
        )
    )
    tokens = await AuthService(db_session).login(
        UserLogin(email="wrongtype@example.com", password="correcthorsebattery")
    )

    with pytest.raises(AuthenticationError):
        await AuthService(db_session).refresh(tokens.access_token)


async def test_refresh_rejects_garbage_token(db_session: AsyncSession):
    with pytest.raises(AuthenticationError):
        await AuthService(db_session).refresh("not-a-real-jwt")


async def test_refresh_rejects_expired_token(db_session: AsyncSession):
    from datetime import UTC, datetime, timedelta

    from app.core.config import settings

    expired_payload = {
        "sub": "00000000-0000-0000-0000-000000000000",
        "exp": datetime.now(UTC) - timedelta(minutes=1),
        "type": "refresh",
    }
    expired_token = jwt.encode(expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    with pytest.raises(AuthenticationError):
        await AuthService(db_session).refresh(expired_token)
