"""Baseline compare endpoints."""

from collections.abc import Callable

import cv2
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import select

from lacuna.db.models import DetectionRecord
from lacuna.services import delete_shelf
from tests.conftest import FULL_ROW, FakeDetector, shelf_row, textured_bytes

FULL_SHELF = shelf_row(20, FULL_ROW) + shelf_row(200, FULL_ROW)
SOLD = (4, 5)  # top row slots that sell out, x 250-300 and 310-360
SOLD_DOWN = shelf_row(20, [x for i, x in enumerate(FULL_ROW) if i not in SOLD]) + shelf_row(
    200, FULL_ROW
)


def scan(
    client: TestClient, upload: Callable[..., str], shelf: str, photo: bytes
) -> dict[str, object]:
    resp = client.post("/detect", json={"image_id": upload(shelf, photo)})
    assert resp.status_code == 201, resp.text
    body: dict[str, object] = resp.json()
    return body


def stocked_then_sold(
    client: TestClient, upload: Callable[..., str], fake_detector: FakeDetector, later: bytes
) -> tuple[str, str]:
    fake_detector.boxes = FULL_SHELF
    stocked = str(scan(client, upload, "a1", textured_bytes(0))["id"])
    fake_detector.boxes = SOLD_DOWN
    sold = str(scan(client, upload, "a1", later)["id"])
    return stocked, sold


def test_names_what_sold_out_of_each_gap(
    client: TestClient, upload: Callable[..., str], fake_detector: FakeDetector
) -> None:
    stocked, sold = stocked_then_sold(client, upload, fake_detector, textured_bytes(0))
    assert client.post("/shelves/a1/baseline", json={"scan_id": stocked}).status_code == 200
    assert client.get("/shelves/a1/history").json()["baseline_scan_id"] == stocked

    body = client.get(f"/results/{sold}/missing").json()
    assert body["aligned"] is True
    assert body["baseline_scan_id"] == stocked
    [gap] = body["gaps"]
    assert [p["x1"] for p in gap["products"]] == [FULL_ROW[i] for i in SOLD]

    crop = client.get(f"/results/{stocked}/products/{gap['products'][0]['id']}/crop")
    assert crop.status_code == 200
    assert crop.headers["content-type"] == "image/jpeg"
    pixels = cv2.imdecode(np.frombuffer(crop.content, np.uint8), cv2.IMREAD_COLOR)
    assert pixels is not None
    assert pixels.shape[:2] == (140, 59)  # 120x50 box plus 8% each side, rounded out


def test_no_baseline_means_no_compare(
    client: TestClient, upload: Callable[..., str], fake_detector: FakeDetector
) -> None:
    stocked, sold = stocked_then_sold(client, upload, fake_detector, textured_bytes(0))
    assert client.get("/shelves/a1/history").json()["baseline_scan_id"] is None
    body = client.get(f"/results/{sold}/missing").json()
    assert body == {"scan_id": sold, "baseline_scan_id": None, "aligned": False, "gaps": []}

    # the baseline compared to itself isn't a compare either
    client.post("/shelves/a1/baseline", json={"scan_id": stocked})
    assert client.get(f"/results/{stocked}/missing").json()["aligned"] is False


def test_photos_that_dont_line_up_say_so(
    client: TestClient, upload: Callable[..., str], fake_detector: FakeDetector
) -> None:
    stocked, sold = stocked_then_sold(client, upload, fake_detector, textured_bytes(9))
    client.post("/shelves/a1/baseline", json={"scan_id": stocked})
    body = client.get(f"/results/{sold}/missing").json()
    assert body["baseline_scan_id"] == stocked
    assert body["aligned"] is False
    assert body["gaps"] == []


def test_baseline_must_be_a_scan_of_that_shelf(
    client: TestClient, upload: Callable[..., str], fake_detector: FakeDetector
) -> None:
    fake_detector.boxes = FULL_SHELF
    other = scan(client, upload, "b2", textured_bytes(0))["id"]
    scan(client, upload, "a1", textured_bytes(0))
    assert client.post("/shelves/a1/baseline", json={"scan_id": other}).status_code == 422
    assert client.post("/shelves/a1/baseline", json={"scan_id": "nope"}).status_code == 404
    assert client.post("/shelves/zz/baseline", json={"scan_id": other}).status_code == 404


def test_missing_and_crop_for_unknown_ids(
    client: TestClient, upload: Callable[..., str], fake_detector: FakeDetector
) -> None:
    fake_detector.boxes = FULL_SHELF
    one = scan(client, upload, "a1", textured_bytes(0))["id"]
    two = scan(client, upload, "a1", textured_bytes(0))["id"]
    assert client.get("/results/nope/missing").status_code == 404
    assert client.get("/results/nope/products/1/crop").status_code == 404

    # a real product id, asked for under the wrong scan
    with client.app.state.sessionmaker() as session:  # type: ignore[attr-defined]
        theirs = session.scalar(select(DetectionRecord.id).where(DetectionRecord.scan_id == two))
    assert client.get(f"/results/{two}/products/{theirs}/crop").status_code == 200
    assert client.get(f"/results/{one}/products/{theirs}/crop").status_code == 404


def test_deleting_a_shelf_clears_its_baseline_first(
    client: TestClient, upload: Callable[..., str], fake_detector: FakeDetector
) -> None:
    stocked, _ = stocked_then_sold(client, upload, fake_detector, textured_bytes(0))
    client.post("/shelves/a1/baseline", json={"scan_id": stocked})
    with client.app.state.sessionmaker() as session:  # type: ignore[attr-defined]
        assert delete_shelf(session, "a1") == 2
    assert client.get("/shelves/a1/history").status_code == 404
