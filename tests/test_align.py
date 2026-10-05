"""Lining up a baseline photo with a later one."""

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from lacuna.baseline import crop
from lacuna.db.models import DetectionRecord
from lacuna.vision import Box
from lacuna.vision.align import find_homography, inside_fraction, map_rect, was_here
from tests.conftest import textured


def test_same_photo_gives_identity() -> None:
    image = textured(1)
    h = find_homography(image, image)
    assert h is not None
    np.testing.assert_allclose(h / h[2, 2], np.eye(3), atol=0.01)


def test_recovers_a_handheld_retake() -> None:
    """Rotate, zoom, and shift the photo; mapped points land where they moved to."""
    base = textured(2)
    move = cv2.getRotationMatrix2D((320, 240), 4, 0.9)
    move[:, 2] += (25, -15)
    warped = cv2.warpAffine(base, move, (640, 480), borderValue=(235, 235, 235))
    retake = np.asarray(warped, dtype=np.uint8)

    h = find_homography(base, retake)
    assert h is not None
    pts = np.array([[100, 100], [500, 120], [320, 400]], dtype=np.float32)
    expected = cv2.transform(pts.reshape(-1, 1, 2), move).reshape(-1, 2)
    got = cv2.perspectiveTransform(pts.reshape(-1, 1, 2), h).reshape(-1, 2)
    np.testing.assert_allclose(got, expected, atol=3)


@pytest.mark.parametrize(
    "other",
    [textured(4), np.full((480, 640, 3), 128, dtype=np.uint8)],
    ids=["different-shelf", "blank"],
)
def test_unrelated_photos_dont_line_up(other: NDArray[np.uint8]) -> None:
    assert find_homography(textured(3), other) is None


def test_was_here_needs_most_of_the_product_inside_the_gap() -> None:
    gap = Box(100, 0, 220, 100, 1)
    inside = Box(110, 10, 160, 90, 1)
    half_out = Box(190, 10, 250, 90, 1)  # exactly half in
    mostly_out = Box(200, 10, 260, 90, 1)
    assert inside_fraction(half_out, gap) == pytest.approx(0.5)
    assert was_here(np.eye(3), [inside, half_out, mostly_out], gap) == [inside, half_out]


def test_map_rect_moves_with_the_warp() -> None:
    shift = np.array([[1, 0, 30], [0, 1, -10], [0, 0, 1]], dtype=np.float64)
    moved = map_rect(shift, Box(0, 20, 50, 60, 1))
    assert (moved.x1, moved.y1, moved.x2, moved.y2) == pytest.approx((30, 10, 80, 50))


def test_crop_pads_and_stays_inside_the_photo() -> None:
    image = textured(5)
    corner = DetectionRecord(x1=0, y1=0, x2=100, y2=50, score=1)
    assert crop(image, corner).shape[:2] == (55, 109)  # padded right and down only
