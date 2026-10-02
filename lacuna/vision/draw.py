"""Draw detections and gaps on an image."""

from collections.abc import Iterable

import cv2
import numpy as np
from numpy.typing import NDArray

from lacuna.vision.types import Rect

PRODUCT_COLOR = (80, 200, 60)  # BGR green
GAP_COLOR = (40, 40, 230)  # BGR red


def draw_overlay(
    image: NDArray[np.uint8], products: Iterable[Rect], gaps: Iterable[Rect]
) -> NDArray[np.uint8]:
    """Return a copy with thin product boxes and filled, outlined gaps."""
    out = image.copy()
    thickness = max(1, round(min(image.shape[:2]) / 400))

    for b in products:
        cv2.rectangle(out, (int(b.x1), int(b.y1)), (int(b.x2), int(b.y2)), PRODUCT_COLOR, thickness)

    gaps = list(gaps)
    shade = out.copy()
    for g in gaps:
        cv2.rectangle(shade, (int(g.x1), int(g.y1)), (int(g.x2), int(g.y2)), GAP_COLOR, -1)
    out = np.asarray(cv2.addWeighted(shade, 0.35, out, 0.65, 0), dtype=np.uint8)
    for g in gaps:
        cv2.rectangle(out, (int(g.x1), int(g.y1)), (int(g.x2), int(g.y2)), GAP_COLOR, thickness * 2)

    return out
