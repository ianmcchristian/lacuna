"""Baseline compare: what used to be where a gap is now.

A shelf can point at one stocked scan as its baseline. For a later scan of
that shelf, the two photos are lined up (vision.align) and the baseline's
products that land inside each new gap are the ones that probably sold out.
"""

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray
from sqlalchemy.orm import Session

from lacuna.db.models import DetectionRecord, GapRecord, Shelf
from lacuna.imaging import encode_jpeg
from lacuna.services import NotFoundError, get_scan, get_shelf, load_pixels
from lacuna.vision.align import find_homography, was_here

CROP_PAD = 0.08  # a little context around a product crop


class WrongShelfError(ValueError):
    pass


@dataclass
class Missing:
    scan_id: str
    baseline_scan_id: str | None = None
    aligned: bool = False
    gaps: list[tuple[GapRecord, list[DetectionRecord]]] = field(default_factory=list)


def set_baseline(session: Session, code: str, scan_id: str) -> Shelf:
    shelf = get_shelf(session, code)
    scan = get_scan(session, scan_id)
    if scan.image.shelf_id != shelf.id:
        raise WrongShelfError(f"scan {scan_id} is not a scan of shelf {code}")
    shelf.baseline_scan_id = scan.id
    session.commit()
    return shelf


def missing_products(session: Session, scan_id: str) -> Missing:
    scan = get_scan(session, scan_id)
    shelf = scan.image.shelf
    baseline_id = shelf.baseline_scan_id if shelf else None
    if baseline_id is None or baseline_id == scan.id:
        return Missing(scan_id=scan.id, baseline_scan_id=baseline_id)

    baseline = get_scan(session, baseline_id)
    h = find_homography(
        load_pixels(session, baseline.image_id), load_pixels(session, scan.image_id)
    )
    if h is None:
        return Missing(scan_id=scan.id, baseline_scan_id=baseline_id)
    return Missing(
        scan_id=scan.id,
        baseline_scan_id=baseline_id,
        aligned=True,
        gaps=[(gap, was_here(h, baseline.detections, gap)) for gap in scan.gaps],
    )


def crop(image: NDArray[np.uint8], box: DetectionRecord) -> NDArray[np.uint8]:
    height, width = image.shape[:2]
    pad_x, pad_y = (box.x2 - box.x1) * CROP_PAD, (box.y2 - box.y1) * CROP_PAD
    x1, y1 = max(0, int(box.x1 - pad_x)), max(0, int(box.y1 - pad_y))
    x2, y2 = min(width, int(box.x2 + pad_x) + 1), min(height, int(box.y2 + pad_y) + 1)
    return image[y1:y2, x1:x2]


def product_crop(session: Session, scan_id: str, detection_id: int) -> bytes:
    """JPEG of one detected product, cut from its scan's photo."""
    scan = get_scan(session, scan_id)
    box = next((d for d in scan.detections if d.id == detection_id), None)
    if box is None:
        raise NotFoundError(f"product {detection_id} not found in scan {scan_id}")
    return encode_jpeg(crop(load_pixels(session, scan.image_id), box), quality=90)
