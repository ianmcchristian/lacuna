"""Shared FastAPI dependencies. Everything hangs off app.state, set in main.create_app."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from lacuna.config import Settings
from lacuna.vision import Detector


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.sessionmaker() as session:
        yield session


def get_detector(request: Request) -> Detector:
    detector: Detector | None = request.app.state.detector
    if detector is None:
        raise HTTPException(503, "model not loaded")
    return detector


SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[Session, Depends(get_session)]
DetectorDep = Annotated[Detector, Depends(get_detector)]
