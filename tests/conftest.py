"""Shared fixtures. Set LACUNA_TEST_DATABASE_URL to run against Postgres (CI does)."""

import os
from collections.abc import Iterator, Sequence
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from numpy.typing import NDArray

from lacuna.api.deps import get_detector
from lacuna.config import Settings
from lacuna.db.models import Base
from lacuna.main import create_app
from lacuna.vision import Box

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def shelf_row(y: float, xs: Sequence[float], width: float = 50, height: float = 120) -> list[Box]:
    return [Box(x, y, x + width, y + height, 0.9) for x in xs]


# 10 slots per row, 60 px apart. Top row is missing slots 4 and 5.
FULL_ROW = [10 + 60 * i for i in range(10)]
GAPPY_ROW = [x for i, x in enumerate(FULL_ROW) if i not in (4, 5)]
FAKE_BOXES = shelf_row(20, GAPPY_ROW) + shelf_row(200, FULL_ROW)


class FakeDetector:
    def __init__(self, boxes: list[Box]) -> None:
        self.boxes = boxes

    @property
    def name(self) -> str:
        return "fake"

    def detect(self, image: NDArray[np.uint8]) -> list[Box]:
        return self.boxes


def image_bytes(ext: str = ".jpg", size: tuple[int, int] = (480, 640)) -> bytes:
    ok, buf = cv2.imencode(ext, np.full((*size, 3), 128, dtype=np.uint8))
    assert ok
    return bytes(buf.tobytes())


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=os.environ.get("LACUNA_TEST_DATABASE_URL", f"sqlite:///{tmp_path}/test.db"),
        model_path=tmp_path / "no-model.onnx",
        max_upload_bytes=200_000,
        log_json=False,
    )


@pytest.fixture
def fake_detector() -> FakeDetector:
    return FakeDetector(FAKE_BOXES)


@pytest.fixture
def client(settings: Settings, fake_detector: FakeDetector) -> Iterator[TestClient]:
    app = create_app(settings)
    Base.metadata.drop_all(app.state.engine)
    Base.metadata.create_all(app.state.engine)
    app.dependency_overrides[get_detector] = lambda: fake_detector
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(app.state.engine)


@pytest.fixture
def upload(client: TestClient):  # type: ignore[no-untyped-def]
    """Upload a photo and return the image id."""

    def _upload(shelf: str | None = None) -> str:
        data = {"shelf": shelf} if shelf else {}
        resp = client.post(
            "/images", files={"file": ("shelf.jpg", image_bytes(), "image/jpeg")}, data=data
        )
        assert resp.status_code == 201, resp.text
        return str(resp.json()["id"])

    return _upload
