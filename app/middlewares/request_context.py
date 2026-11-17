"""Request ID, access logging and global error handling middleware."""

import time
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.exceptions import ResourceNotFoundError, TrafficSystemError
from app.core.logging import get_logger

REQUEST_ID_HEADER = "X-Request-ID"

logger = get_logger("traffic_speed_system.http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request ID, log every request and convert crashes to JSON."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled error | %s %s | request_id=%s",
                request.method,
                request.url.path,
                request_id,
            )
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Internal server error.",
                    "request_id": request_id,
                },
            )

        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers[REQUEST_ID_HEADER] = request_id

        # Status polling is very frequent, keep it out of INFO logs.
        log = logger.debug if request.url.path.endswith("/status") else logger.info
        log(
            "%s %s -> %s (%.1f ms) | request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )

        return response


def register_exception_handlers(app: FastAPI) -> None:
    """Map domain exceptions to clean HTTP responses."""

    @app.exception_handler(ResourceNotFoundError)
    async def handle_not_found(
        request: Request,
        exc: ResourceNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "detail": str(exc) or "Resource not found.",
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(TrafficSystemError)
    async def handle_domain_error(
        request: Request,
        exc: TrafficSystemError,
    ) -> JSONResponse:
        logger.error("Domain error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "detail": str(exc),
                "request_id": getattr(request.state, "request_id", None),
            },
        )
