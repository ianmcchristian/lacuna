"""API contract and upload edge cases."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from lacuna.api.deps import get_detector
from lacuna.config import Settings
from lacuna.main import create_app
from tests.conftest import FAKE_BOXES, FakeDetector, image_bytes


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert "x-request-id" in resp.headers


def test_ready_without_model_is_503(client: TestClient) -> None:
    resp = client.get("/ready")
    assert resp.status_code == 503
    assert resp.json() == {"status": "unavailable", "database": True, "model": None}


def test_upload_jpeg(client: TestClient) -> None:
    resp = client.post(
        "/images",
        files={"file": ("a.jpg", image_bytes(), "image/jpeg")},
        data={"shelf": "aisle4-bay2"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert (body["width"], body["height"]) == (640, 480)
    assert body["shelf"] == "aisle4-bay2"
    assert body["content_type"] == "image/jpeg"


def test_upload_png_without_shelf(client: TestClient) -> None:
    resp = client.post("/images", files={"file": ("a.png", image_bytes(".png"), "image/png")})
    assert resp.status_code == 201
    assert resp.json()["shelf"] is None


def test_upload_wrong_type(client: TestClient) -> None:
    resp = client.post("/images", files={"file": ("a.pdf", b"%PDF-1.7", "application/pdf")})
    assert resp.status_code == 415


def test_upload_too_large(client: TestClient) -> None:
    big = image_bytes(".png", size=(400, 400)) + b"\0" * 250_000  # limit is 200 KB in tests
    resp = client.post("/images", files={"file": ("a.png", big, "image/png")})
    assert resp.status_code == 413


def test_upload_empty_file(client: TestClient) -> None:
    resp = client.post("/images", files={"file": ("a.jpg", b"", "image/jpeg")})
    assert resp.status_code == 422


def test_upload_corrupt_image(client: TestClient) -> None:
    resp = client.post("/images", files={"file": ("a.jpg", b"not really a jpeg", "image/jpeg")})
    assert resp.status_code == 422


def test_upload_missing_file(client: TestClient) -> None:
    assert client.post("/images").status_code == 422


def test_upload_bad_shelf_code(client: TestClient) -> None:
    resp = client.post(
        "/images",
        files={"file": ("a.jpg", image_bytes(), "image/jpeg")},
        data={"shelf": "drop table;"},
    )
    assert resp.status_code == 422


def test_detect_and_fetch_result(client: TestClient, upload: Callable[..., str]) -> None:
    image_id = upload()
    resp = client.post("/detect", json={"image_id": image_id})
    assert resp.status_code == 201
    scan = resp.json()
    assert scan["product_count"] == len(FAKE_BOXES)
    assert scan["gap_count"] == 1
    assert scan["gaps"][0]["row"] == 0
    assert 0 < scan["occupancy"] < 1
    assert scan["model"] == "fake"

    fetched = client.get(f"/results/{scan['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == scan


def test_upload_survives_restart(
    client: TestClient, upload: Callable[..., str], settings: Settings, fake_detector: FakeDetector
) -> None:
    """Bytes live in the database, so a fresh replica can scan an upload it never saw."""
    image_id = upload()
    other = create_app(settings)
    other.dependency_overrides[get_detector] = lambda: fake_detector
    with TestClient(other) as replica:
        assert replica.post("/detect", json={"image_id": image_id}).status_code == 201


def test_large_upload_stored_smaller(client: TestClient) -> None:
    big = image_bytes(".jpg", size=(1500, 3000))  # 3000 px wide
    resp = client.post("/images", files={"file": ("big.jpg", big, "image/jpeg")})
    assert resp.status_code == 201
    assert (resp.json()["width"], resp.json()["height"]) == (2048, 1024)


def test_detect_unknown_image(client: TestClient) -> None:
    assert client.post("/detect", json={"image_id": "nope"}).status_code == 404


def test_detect_missing_body(client: TestClient) -> None:
    assert client.post("/detect", json={}).status_code == 422


def test_result_not_found(client: TestClient) -> None:
    assert client.get("/results/nope").status_code == 404


def test_overlay_is_jpeg(client: TestClient, upload: Callable[..., str]) -> None:
    scan = client.post("/detect", json={"image_id": upload()}).json()
    resp = client.get(f"/results/{scan['id']}/overlay")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.content[:2] == b"\xff\xd8"


def test_metrics_exposes_latency(client: TestClient) -> None:
    client.get("/health")
    body = client.get("/metrics").text
    assert "lacuna_request_duration_seconds" in body
    assert 'route="/health"' in body


def test_openapi_lists_endpoints(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for path in ("/images", "/detect", "/results/{scan_id}", "/reports/worst-shelves"):
        assert path in paths
