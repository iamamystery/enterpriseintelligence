import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

from app.core.config import settings


class InMemoryRateLimiter:
    def __init__(self, requests_per_minute: int) -> None:
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60.0
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> None:
        now = time.monotonic()
        window_start = now - self.window_seconds
        hits = self._hits[key]
        while hits and hits[0] < window_start:
            hits.pop(0)
        if len(hits) >= self.requests_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Try again later.",
            )
        hits.append(now)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


_general_limiter = InMemoryRateLimiter(settings.RATE_LIMIT_PER_MINUTE)
_auth_limiter = InMemoryRateLimiter(settings.AUTH_RATE_LIMIT_PER_MINUTE)


async def rate_limit(request: Request) -> None:
    _general_limiter.check(_client_key(request))


async def auth_rate_limit(request: Request) -> None:
    _auth_limiter.check(_client_key(request))
