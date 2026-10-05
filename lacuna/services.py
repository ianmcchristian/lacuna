"""Business logic. Routes stay thin and call into here."""

import time

import numpy as np
from numpy.typing import NDArray
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from lacuna.db.models import DetectionRecord, GapRecord, ImageBlob, ImageRecord, Scan, Shelf
from lacuna.imaging import ALLOWED_TYPES, MAX_STORED_SIDE, decode_image, encode_jpeg, fit_within
from lacuna.observability import GAPS_FOUND, INFERENCE_SECONDS
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

    # boxes are in the stored image's pixels, so width/height describe that copy
    stored = fit_within(image, MAX_STORED_SIDE)
    height, width = stored.shape[:2]
    record = ImageRecord(
        filename=filename[:255],
        content_type=content_type,
        size_bytes=len(data),
        width=width,
        height=height,
        shelf=get_or_create_shelf(session, shelf_code) if shelf_code else None,
    )
    session.add(record)
    session.flush()  # assigns the id
    session.add(ImageBlob(image_id=record.id, data=encode_jpeg(stored, quality=90)))
    session.commit()
    return record


def load_pixels(session: Session, image_id: str) -> NDArray[np.uint8]:
    blob = session.get(ImageBlob, image_id)
    image = decode_image(blob.data) if blob else None
    if image is None:
        raise NotFoundError(f"image {image_id} not found")
    return image


def run_scan(
    session: Session,
    detector: Detector,
    image_id: str,
    min_gap_ratio: float,
) -> Scan:
    image = load_pixels(session, image_id)

    start = time.perf_counter()
    boxes = detector.detect(image)
    elapsed = time.perf_counter() - start
    INFERENCE_SECONDS.observe(elapsed)

    result = analyze_shelf(boxes, min_gap_ratio, image_height=image.shape[0])
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


def delete_shelf(session: Session, code: str) -> int:
    """Delete a shelf with every image and scan saved under it. Returns the scan count.

    Child rows go first, explicitly, so it doesn't lean on FK cascades
    (SQLite leaves them off unless asked).
    """
    shelf = get_shelf(session, code)
    image_ids = select(ImageRecord.id).where(ImageRecord.shelf_id == shelf.id)
    scan_ids = select(Scan.id).where(Scan.image_id.in_(image_ids))
    scans = session.scalar(select(func.count()).select_from(Scan).where(Scan.id.in_(scan_ids)))
    for statement in (
        delete(DetectionRecord).where(DetectionRecord.scan_id.in_(scan_ids)),
        delete(GapRecord).where(GapRecord.scan_id.in_(scan_ids)),
        delete(Scan).where(Scan.image_id.in_(image_ids)),
        delete(ImageBlob).where(ImageBlob.image_id.in_(image_ids)),
        delete(ImageRecord).where(ImageRecord.shelf_id == shelf.id),
        delete(Shelf).where(Shelf.id == shelf.id),
    ):
        session.execute(statement.execution_options(synchronize_session=False))
    session.commit()
    return scans or 0
