"""Make test photos from a real one: products sold out, or the shelf shot again.

Inpainting, not a solid fill: a flat dark rectangle the size of a can still
looks like a can to the model.
"""

from collections.abc import Iterable

import cv2
import numpy as np
from numpy.typing import NDArray

from lacuna.vision.types import Rect


def paint_out(image: NDArray[np.uint8], products: Iterable[Rect]) -> NDArray[np.uint8]:
    """The photo with these products removed."""
    mask = np.zeros(image.shape[:2], dtype=np.uint8)
    for b in products:
        mask[int(b.y1) : int(b.y2), int(b.x1) : int(b.x2)] = 255
    return np.asarray(cv2.inpaint(image, mask, 5, cv2.INPAINT_TELEA), dtype=np.uint8)


def retake(
    image: NDArray[np.uint8],
    angle: float,
    scale: float,
    shift: tuple[float, float],
    tilt: float = 0,
) -> NDArray[np.uint8]:
    """The same shelf shot again: rotated (degrees), zoomed, shifted (px), and
    tilted (px the right edge's corners move toward the middle, like turning
    the phone sideways)."""
    height, width = image.shape[:2]
    corners = np.array([[0, 0], [width, 0], [width, height], [0, height]], dtype=np.float32)
    center = np.array([width / 2, height / 2], dtype=np.float32)
    turn = np.deg2rad(angle)
    rotate = np.array([[np.cos(turn), -np.sin(turn)], [np.sin(turn), np.cos(turn)]]) * scale
    moved = (corners - center) @ rotate.T + center + np.array(shift)
    moved[1, 1] += tilt
    moved[2, 1] -= tilt
    warp = cv2.getPerspectiveTransform(corners, moved.astype(np.float32))
    shot = cv2.warpPerspective(image, warp, (width, height), borderMode=cv2.BORDER_REPLICATE)
    return np.asarray(shot, dtype=np.uint8)
