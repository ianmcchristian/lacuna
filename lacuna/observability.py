"""Structured JSON logs and Prometheus metrics."""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from prometheus_client import Counter, Histogram

REQUEST_SECONDS = Histogram(
    "lacuna_request_duration_seconds",
    "HTTP request latency",
    ["method", "route", "status"],
)
INFERENCE_SECONDS = Histogram(
    "lacuna_inference_duration_seconds",
    "Model inference latency",
    buckets=(0.025, 0.05, 0.075, 0.1, 0.15, 0.25, 0.5, 1.0, 2.5),
)
GAPS_FOUND = Counter("lacuna_gaps_found_total", "Shelf gaps found across all scans")

QUIET_ROUTES = frozenset({"/health", "/ready", "/metrics"})  # probes, no access log

log = structlog.get_logger()


def configure_logging(json_logs: bool) -> None:
    renderer = structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )


async def observe_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Request id, latency histogram, and one access log line per request."""
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    start = time.perf_counter()

    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        log.exception("unhandled error", path=request.url.path)
        raise
    finally:
        elapsed = time.perf_counter() - start
        route = request.scope.get("route")
        template = getattr(route, "path", "unmatched")  # template keeps label count bounded
        REQUEST_SECONDS.labels(request.method, template, str(status)).observe(elapsed)
        if template not in QUIET_ROUTES:
            log.info(
                "request",
                method=request.method,
                path=request.url.path,
                status=status,
                duration_ms=round(elapsed * 1000, 2),
            )

    response.headers["x-request-id"] = request_id
    return response
