from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.postgres.advisory_repository import AdvisoryRepository
from app.repositories.postgres.asset_repository import AssetRepository
from app.repositories.postgres.vulnerability_repository import VulnerabilityRepository

SEARCHABLE_TYPES = {"vulnerability", "advisory", "asset"}


class SearchService:
    def __init__(self, session: AsyncSession) -> None:
        self.vulnerabilities = VulnerabilityRepository(session)
        self.advisories = AdvisoryRepository(session)
        self.assets = AssetRepository(session)

    async def search(
        self,
        requesting_user: User,
        *,
        query: str,
        types: set[str] | None = None,
        limit: int = 10,
    ) -> dict[str, tuple[list[Any], int]]:
        active_types = SEARCHABLE_TYPES if types is None else types & SEARCHABLE_TYPES

        results: dict[str, tuple[list[Any], int]] = {
            "vulnerabilities": ([], 0),
            "advisories": ([], 0),
            "assets": ([], 0),
        }

        if "vulnerability" in active_types:
            results["vulnerabilities"] = await self.vulnerabilities.search(keyword=query, limit=limit)
        if "advisory" in active_types:
            results["advisories"] = await self.advisories.search(keyword=query, limit=limit)
        if "asset" in active_types:
            results["assets"] = await self.assets.search(
                requesting_user.organization_id, keyword=query, limit=limit
            )

        return results
