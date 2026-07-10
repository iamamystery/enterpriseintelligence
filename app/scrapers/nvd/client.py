from typing import Any

from app.scrapers.base.base_client import BaseAPIClient
from app.scrapers.nvd.config import NVD_BASE_URL, NVD_RESULTS_PER_PAGE, nvd_headers


class NVDClient(BaseAPIClient):
    def __init__(self) -> None:
        super().__init__(base_url=NVD_BASE_URL, headers=nvd_headers())

    async def fetch_recent_cves(
        self, results_per_page: int = NVD_RESULTS_PER_PAGE, start_index: int = 0
    ) -> dict[str, Any]:
        params = {"resultsPerPage": results_per_page, "startIndex": start_index}
        return await self.get(params=params)
