"""Line a baseline photo up with a later photo of the same shelf.

Phone photos are never taken from exactly the same spot, so baseline boxes
can't be compared to new gaps directly. ORB features matched between the two
photos give a homography (RANSAC drops bad matches) that maps baseline pixels
into the new photo. A shelf front is close to a plane, so one homography fits.
"""

from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

from lacuna.vision.types import Rect

WORK_SIDE = 1024  # match on a smaller copy: faster, and plenty of features
MIN_INLIERS = 30
RATIO = 0.75  # Lowe's ratio test
MIN_OVERLAP = 0.5  # share of a baseline product that must fall inside the gap


@dataclass(frozen=True, slots=True)
class Mapped:
    x1: float
    y1: float
    x2: float
    y2: float


def _gray(image: NDArray[np.uint8]) -> tuple[NDArray[np.uint8], float]:
    scale = min(1.0, WORK_SIDE / max(image.shape[:2]))
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return np.asarray(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), dtype=np.uint8), scale


def _plausible(h: NDArray[np.float64], width: int, height: int) -> bool:
    """Reject warps no handheld retake would produce: flips, big zooms, folds."""
    det = float(np.linalg.det(h[:2, :2]))
    if not 0.25 < det < 4:
        return False
    corners = np.array(
        [[0, 0], [width, 0], [width, height], [0, height]], dtype=np.float32
    ).reshape(-1, 1, 2)
    warped = cv2.perspectiveTransform(corners, h).reshape(-1, 2)
    return bool(cv2.isContourConvex(warped.astype(np.float32)))


def find_homography(
    baseline: NDArray[np.uint8], current: NDArray[np.uint8]
) -> NDArray[np.float64] | None:
    """3x3 map from baseline pixels to current pixels, or None if they don't line up."""
    orb = cv2.ORB.create(nfeatures=4000)
    (base_gray, base_scale), (cur_gray, cur_scale) = _gray(baseline), _gray(current)
    base_kp, base_desc = orb.detectAndCompute(base_gray, None)
    cur_kp, cur_desc = orb.detectAndCompute(cur_gray, None)
    if base_desc is None or cur_desc is None or len(base_kp) < MIN_INLIERS:
        return None

    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(base_desc, cur_desc, k=2)
    good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < RATIO * p[1].distance]
    if len(good) < MIN_INLIERS:
        return None

    src = np.array([base_kp[m.queryIdx].pt for m in good], dtype=np.float32) / base_scale
    dst = np.array([cur_kp[m.trainIdx].pt for m in good], dtype=np.float32) / cur_scale
    found, inliers = cv2.findHomography(src, dst, cv2.RANSAC, 5.0 / cur_scale)
    if found is None or int(inliers.sum()) < MIN_INLIERS:
        return None
    h = np.asarray(found, dtype=np.float64)
    height, width = baseline.shape[:2]
    return h if _plausible(h, width, height) else None


def map_rect(h: NDArray[np.float64], rect: Rect) -> Mapped:
    """Bounding box of a rect after the warp."""
    corners = np.array(
        [[rect.x1, rect.y1], [rect.x2, rect.y1], [rect.x2, rect.y2], [rect.x1, rect.y2]],
        dtype=np.float32,
    ).reshape(-1, 1, 2)
    pts = cv2.perspectiveTransform(corners, h).reshape(-1, 2)
    return Mapped(
        float(pts[:, 0].min()),
        float(pts[:, 1].min()),
        float(pts[:, 0].max()),
        float(pts[:, 1].max()),
    )


def inside_fraction(box: Rect, region: Rect) -> float:
    """Share of box's area that lies inside region."""
    w = max(0.0, min(box.x2, region.x2) - max(box.x1, region.x1))
    h = max(0.0, min(box.y2, region.y2) - max(box.y1, region.y1))
    area = (box.x2 - box.x1) * (box.y2 - box.y1)
    return w * h / area if area > 0 else 0.0


def was_here[T: Rect](
    h: NDArray[np.float64], baseline_products: list[T], gap: Rect, min_overlap: float = MIN_OVERLAP
) -> list[T]:
    """Baseline products that, once mapped into the current photo, sit in this gap."""
    return [b for b in baseline_products if inside_fraction(map_rect(h, b), gap) >= min_overlap]
