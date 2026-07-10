from collections.abc import Callable, Coroutine
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.api.dependencies.auth import get_current_user
from app.models.user import User


def require_permission(permission: str) -> Callable[..., Coroutine[None, None, User]]:
    async def check(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.is_superuser:
            return current_user

        permissions = current_user.role.permissions or []
        if "*" not in permissions and permission not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission}",
            )
        return current_user

    return check
