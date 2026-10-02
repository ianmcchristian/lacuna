"""Shared FastAPI dependencies. Everything hangs off app.state, set in main.create_app."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from lacuna.config import Settings
from lacuna.storage import ImageStore
from lacuna.vision import Detector


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.sessionmaker() as session:
        yield session


def get_store(request: Request) -> ImageStore:
    store: ImageStore = request.app.state.store
    return store


def get_detector(request: Request) -> Detector:
    detector: Detector | None = request.app.state.detector
    if detector is None:
        raise HTTPException(503, "model not loaded")
    return detector


SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[Session, Depends(get_session)]
StoreDep = Annotated[ImageStore, Depends(get_store)]
DetectorDep = Annotated[Detector, Depends(get_detector)]
