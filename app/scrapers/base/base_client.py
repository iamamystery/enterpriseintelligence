import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class BaseAPIClient:
    def __init__(self, base_url: str, timeout: int = 30, headers: dict[str, str] | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = headers or {}

    async def get(self, path: str = "", params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info("GET %s params=%s", url, params)
            response = await client.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            return response.json()
