from typing import Any

from app.scrapers.base.base_client import BaseAPIClient

MITRE_SOURCE_NAME = "MITRE"
MITRE_BASE_URL = "https://cveawg.mitre.org/api"


class MITREClient(BaseAPIClient):
    def __init__(self) -> None:
        super().__init__(base_url=MITRE_BASE_URL)

    async def fetch_cve(self, cve_id: str) -> dict[str, Any]:
        return await self.get(f"/cve/{cve_id}")
