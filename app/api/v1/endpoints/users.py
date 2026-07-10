from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies.database import DBSession
from app.api.dependencies.permissions import require_permission
from app.api.dependencies.rate_limit import rate_limit
from app.models.user import User
from app.schemas.user import UserCreate, UserRead
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(rate_limit)])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    session: DBSession,
    requesting_user: Annotated[User, Depends(require_permission("users:manage"))],
) -> UserRead:
    user = await UserService(session).create_user(requesting_user, data)
    return UserRead.model_validate(user)
