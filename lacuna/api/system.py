"""Liveness, readiness, and metrics."""

import os

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from lacuna import __version__
from lacuna.api.deps import SessionDep
from lacuna.schemas import Health, Ready

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> Health:
    """Liveness. The process is up."""
    # Render sets RENDER_GIT_COMMIT on every deploy
    return Health(status="ok", version=__version__, commit=os.environ.get("RENDER_GIT_COMMIT"))


@router.get("/ready", responses={503: {"model": Ready}})
def ready(request: Request, session: SessionDep) -> JSONResponse:
    """Readiness. Database reachable and model loaded."""
    try:
        session.execute(text("SELECT 1"))
        database = True
    except SQLAlchemyError:
        database = False

    detector = request.app.state.detector
    body = Ready(
        status="ok" if database and detector else "unavailable",
        database=database,
        model=detector.name if detector else None,
    )
    return JSONResponse(body.model_dump(), status_code=200 if body.status == "ok" else 503)


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
