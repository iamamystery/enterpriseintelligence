from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401 - registers all ORM models with SQLAlchemy's mapper registry
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import ErrorHandlingMiddleware, RequestIDMiddleware, RequestLoggingMiddleware
from app.tasks.scheduler import shutdown_scheduler, start_scheduler

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)

# Starlette wraps middleware in reverse add-order (last added = outermost),
# so this list runs, on the way in: CORS -> RequestID -> RequestLogging ->
# ErrorHandling -> router, and unwinds in reverse on the way out. CORS stays
# outermost so its headers land on every response, including error ones.
# ErrorHandling sits innermost (closest to the router) so it only ever sees
# exceptions that ETIPError's own handler didn't already convert to a
# response - see app/core/exception_handlers.py.
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
