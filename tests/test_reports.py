"""SQL report endpoints."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FULL_ROW, GAPPY_ROW, FakeDetector, shelf_row

FULL_SHELF = shelf_row(20, FULL_ROW) + shelf_row(200, FULL_ROW)
GAPPY_SHELF = shelf_row(20, GAPPY_ROW) + shelf_row(200, FULL_ROW)


def scan(client: TestClient, upload: Callable[..., str], shelf: str) -> dict[str, object]:
    resp = client.post("/detect", json={"image_id": upload(shelf)})
    assert resp.status_code == 201
    body: dict[str, object] = resp.json()
    return body


def test_history_tracks_change(
    client: TestClient, upload: Callable[..., str], fake_detector: FakeDetector
) -> None:
    fake_detector.boxes = FULL_SHELF
    scan(client, upload, "a1")
    fake_detector.boxes = GAPPY_SHELF
    scan(client, upload, "a1")

    resp = client.get("/shelves/a1/history")
    assert resp.status_code == 200
    newest, oldest = resp.json()["scans"]
    assert oldest["occupancy"] == 1.0
    assert oldest["occupancy_change"] is None
    assert newest["occupancy"] < 1.0
    assert newest["occupancy_change"] == pytest.approx(newest["occupancy"] - 1.0)


def test_history_limit_keeps_true_change(
    client: TestClient, upload: Callable[..., str], fake_detector: FakeDetector
) -> None:
    fake_detector.boxes = FULL_SHELF
    scan(client, upload, "a1")
    fake_detector.boxes = GAPPY_SHELF
    scan(client, upload, "a1")

    (only,) = client.get("/shelves/a1/history", params={"limit": 1}).json()["scans"]
    assert only["occupancy_change"] is not None  # LAG sees the row LIMIT dropped


def test_history_unknown_shelf(client: TestClient) -> None:
    assert client.get("/shelves/nope/history").status_code == 404


def test_worst_shelves_ranks_by_latest_scan(
    client: TestClient, upload: Callable[..., str], fake_detector: FakeDetector
) -> None:
    fake_detector.boxes = GAPPY_SHELF
    scan(client, upload, "b2")  # b2 was gappy, then restocked
    fake_detector.boxes = FULL_SHELF
    scan(client, upload, "b2")
    fake_detector.boxes = GAPPY_SHELF
    scan(client, upload, "c3")  # c3 is gappy now
    upload()  # no shelf, ignored

    report = client.get("/reports/worst-shelves").json()
    assert [r["shelf"] for r in report] == ["c3", "b2"]
    c3, b2 = report
    assert c3["latest_gap_count"] == 1
    assert b2["latest_occupancy"] == 1.0
    assert b2["scan_count"] == 2
    assert b2["avg_occupancy"] < 1.0


def test_worst_shelves_empty(client: TestClient) -> None:
    assert client.get("/reports/worst-shelves").json() == []
