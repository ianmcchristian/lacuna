"""App factory. Run with: uvicorn lacuna.main:create_app --factory"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lacuna import __version__
from lacuna.api import reports, scans, system
from lacuna.config import Settings
from lacuna.db.session import make_engine, make_sessionmaker
from lacuna.observability import configure_logging, observe_requests
from lacuna.vision import Detector, OnnxDetector

log = structlog.get_logger()


def load_detector(settings: Settings) -> Detector | None:
    if not settings.model_path.exists():
        log.warning("model file missing, /detect will return 503", path=str(settings.model_path))
        return None
    detector = OnnxDetector(
        settings.model_path,
        settings.conf_threshold,
        settings.iou_threshold,
        threads=settings.inference_threads,
    )
    log.info("model loaded", model=detector.name)
    return detector


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_json)
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.detector = load_detector(settings)
        yield
        engine.dispose()

    app = FastAPI(
        title="Lacuna",
        version=__version__,
        summary="Finds empty shelf space in retail shelf photos.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = make_sessionmaker(engine)
    app.state.detector = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        expose_headers=["x-request-id"],
    )
    app.middleware("http")(observe_requests)

    app.include_router(system.router)
    app.include_router(scans.router)
    app.include_router(reports.router)
    return app
