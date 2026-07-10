from fastapi import APIRouter, Depends, status

from app.api.dependencies.database import DBSession
from app.api.dependencies.rate_limit import auth_rate_limit
from app.schemas.auth import RefreshTokenRequest, TokenResponse, UserLogin, UserRegister
from app.schemas.user import UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(auth_rate_limit)])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, session: DBSession) -> UserRead:
    user = await AuthService(session).register(data)
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, session: DBSession) -> TokenResponse:
    return await AuthService(session).login(data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshTokenRequest, session: DBSession) -> TokenResponse:
    return await AuthService(session).refresh(data.refresh_token)
