from typing import Any

from app.scrapers.base.base_client import BaseAPIClient

CISA_KEV_SOURCE_NAME = "CISA-KEV"
CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"


class CISAKEVClient(BaseAPIClient):
    def __init__(self) -> None:
        super().__init__(base_url=CISA_KEV_URL)

    async def fetch_catalog(self) -> dict[str, Any]:
        return await self.get()
