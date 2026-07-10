from typing import Any

import httpx

from app.scrapers.base.base_client import BaseAPIClient

REDHAT_SOURCE_NAME = "RedHat"
REDHAT_BASE_URL = "https://access.redhat.com/hydra/rest/securitydata"


class RedHatClient(BaseAPIClient):
    def __init__(self) -> None:
        super().__init__(base_url=REDHAT_BASE_URL)

    async def fetch_recent_cves(self, per_page: int = 20) -> list[dict[str, Any]]:
        return await self.get("/cve.json", params={"per_page": per_page})

    async def fetch_cve(self, cve_id: str) -> dict[str, Any] | None:
        try:
            return await self.get(f"/cve/{cve_id}.json")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise
