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


def textured(seed: int = 0, size: tuple[int, int] = (480, 640)) -> NDArray[np.uint8]:
    """Busy, repeatable picture with lots of corners, so photos can be lined up."""
    rng = np.random.default_rng(seed)
    image = np.full((*size, 3), 235, dtype=np.uint8)
    for _ in range(160):
        x, y = int(rng.integers(0, size[1])), int(rng.integers(0, size[0]))
        w, h = int(rng.integers(8, 60)), int(rng.integers(8, 60))
        color = tuple(int(c) for c in rng.integers(0, 255, 3))
        cv2.rectangle(image, (x, y), (x + w, y + h), color, -1)
    for i in range(12):
        org = (int(rng.integers(0, size[1] - 120)), int(rng.integers(20, size[0])))
        cv2.putText(image, f"SKU{seed}{i}", org, cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 2)
    return image


def textured_bytes(seed: int = 0) -> bytes:
    ok, buf = cv2.imencode(".jpg", textured(seed), [cv2.IMWRITE_JPEG_QUALITY, 90])
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

    def _upload(shelf: str | None = None, photo: bytes | None = None) -> str:
        data = {"shelf": shelf} if shelf else {}
        photo = image_bytes() if photo is None else photo
        resp = client.post("/images", files={"file": ("shelf.jpg", photo, "image/jpeg")}, data=data)
        assert resp.status_code == 201, resp.text
        return str(resp.json()["id"])

    return _upload
