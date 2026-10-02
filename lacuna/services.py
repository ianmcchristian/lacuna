"""Business logic. Routes stay thin and call into here."""

import time

import numpy as np
from numpy.typing import NDArray
from sqlalchemy import select
from sqlalchemy.orm import Session

from lacuna.db.models import DetectionRecord, GapRecord, ImageRecord, Scan, Shelf
from lacuna.imaging import ALLOWED_TYPES, decode_image
from lacuna.observability import GAPS_FOUND, INFERENCE_SECONDS
from lacuna.storage import ImageStore
from lacuna.vision import Detector, analyze_shelf


class NotFoundError(LookupError):
    pass


class UploadRejected(ValueError):
    """Bad upload. status_code is the HTTP status the API should return."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def get_or_create_shelf(session: Session, code: str) -> Shelf:
    shelf = session.scalar(select(Shelf).where(Shelf.code == code))
    if shelf is None:
        shelf = Shelf(code=code)
        session.add(shelf)
        session.flush()
    return shelf


def save_upload(
    session: Session,
    store: ImageStore,
    *,
    data: bytes,
    filename: str,
    content_type: str,
    max_bytes: int,
    shelf_code: str | None,
) -> ImageRecord:
    if content_type not in ALLOWED_TYPES:
        raise UploadRejected(415, f"unsupported type {content_type!r}, use jpeg, png, or webp")
    if len(data) > max_bytes:
        raise UploadRejected(413, f"file is over the {max_bytes // (1024 * 1024)} MB limit")
    image = decode_image(data)
    if image is None:
        raise UploadRejected(422, "file is empty or not a readable image")

    height, width = image.shape[:2]
    record = ImageRecord(
        filename=filename[:255],
        content_type=content_type,
        size_bytes=len(data),
        width=width,
        height=height,
        shelf=get_or_create_shelf(session, shelf_code) if shelf_code else None,
    )
    session.add(record)
    session.flush()  # assigns the id before the file write
    store.save(record.id, data)
    session.commit()
    return record


def load_pixels(store: ImageStore, image_id: str) -> NDArray[np.uint8]:
    try:
        image = decode_image(store.load(image_id))
    except FileNotFoundError:
        image = None
    if image is None:
        raise NotFoundError(f"image {image_id} is missing from storage")
    return image


def run_scan(
    session: Session,
    store: ImageStore,
    detector: Detector,
    image_id: str,
    min_gap_ratio: float,
) -> Scan:
    if session.get(ImageRecord, image_id) is None:
        raise NotFoundError(f"image {image_id} not found")
    image = load_pixels(store, image_id)

    start = time.perf_counter()
    boxes = detector.detect(image)
    elapsed = time.perf_counter() - start
    INFERENCE_SECONDS.observe(elapsed)

    result = analyze_shelf(boxes, min_gap_ratio)
    GAPS_FOUND.inc(len(result.gaps))

    scan = Scan(
        image_id=image_id,
        model=detector.name,
        product_count=len(boxes),
        gap_count=len(result.gaps),
        occupancy=result.occupancy,
        latency_ms=round(elapsed * 1000, 2),
        detections=[
            DetectionRecord(x1=b.x1, y1=b.y1, x2=b.x2, y2=b.y2, score=b.score) for b in boxes
        ],
        gaps=[
            GapRecord(row=g.row, x1=g.x1, y1=g.y1, x2=g.x2, y2=g.y2, width_ratio=g.width_ratio)
            for g in result.gaps
        ],
    )
    session.add(scan)
    session.commit()
    return scan


def get_scan(session: Session, scan_id: str) -> Scan:
    scan = session.get(Scan, scan_id)
    if scan is None:
        raise NotFoundError(f"scan {scan_id} not found")
    return scan


def get_shelf(session: Session, code: str) -> Shelf:
    shelf = session.scalar(select(Shelf).where(Shelf.code == code))
    if shelf is None:
        raise NotFoundError(f"shelf {code} not found")
    return shelf
