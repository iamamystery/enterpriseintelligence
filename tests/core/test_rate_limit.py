import pytest
from fastapi import HTTPException

from app.api.dependencies.rate_limit import InMemoryRateLimiter


def test_allows_requests_under_the_limit():
    limiter = InMemoryRateLimiter(requests_per_minute=3)
    for _ in range(3):
        limiter.check("client-a")


def test_blocks_requests_over_the_limit():
    limiter = InMemoryRateLimiter(requests_per_minute=3)
    for _ in range(3):
        limiter.check("client-a")

    with pytest.raises(HTTPException) as exc_info:
        limiter.check("client-a")

    assert exc_info.value.status_code == 429


def test_keys_are_tracked_independently():
    limiter = InMemoryRateLimiter(requests_per_minute=1)
    limiter.check("client-a")

    with pytest.raises(HTTPException):
        limiter.check("client-a")

    limiter.check("client-b")


def test_window_expiry_frees_up_capacity():
    limiter = InMemoryRateLimiter(requests_per_minute=1)
    limiter.check("client-a")

    with pytest.raises(HTTPException):
        limiter.check("client-a")

    limiter._hits["client-a"][0] -= limiter.window_seconds + 1
    limiter.check("client-a")
