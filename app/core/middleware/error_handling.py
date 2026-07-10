import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("app.error")


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Catch-all for exceptions that reach here unhandled.

    ETIPError and HTTPException are already converted to responses by
    Starlette's ExceptionMiddleware (registered via
    app.core.exception_handlers) before they ever reach this layer, so
    only genuinely unexpected exceptions are caught here.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except Exception:
            request_id = getattr(request.state, "request_id", "-")
            logger.exception(
                "Unhandled exception processing %s %s request_id=%s",
                request.method,
                request.url.path,
                request_id,
            )
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})
