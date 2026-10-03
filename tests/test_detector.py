"""Pre/post-processing, no real model needed."""

import numpy as np
import pytest

from lacuna.vision.detector import Letterbox, decode, letterbox, nms


def test_letterbox_pads_to_square_and_keeps_ratio() -> None:
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    blob, lb = letterbox(image, 640)
    assert blob.shape == (1, 3, 640, 640)
    assert blob.dtype == np.float32
    assert lb.scale == 1.0
    assert (lb.pad_x, lb.pad_y) == (0, 80)
    assert blob.max() <= 1.0


def test_nms_drops_overlapping_lower_score() -> None:
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], dtype=np.float32)
    scores = np.array([0.9, 0.8, 0.7], dtype=np.float32)
    assert nms(boxes, scores, iou=0.5) == [0, 2]


def test_decode_maps_back_to_original_pixels() -> None:
    # one box centered at (320, 320) size 100x50 in a 640 input; image was 1280x960
    lb = Letterbox(scale=0.5, pad_x=0, pad_y=80)
    output = np.zeros((1, 5, 3), dtype=np.float32)
    output[0, :, 0] = [320, 320, 100, 50, 0.9]
    output[0, :, 1] = [100, 100, 10, 10, 0.1]  # below conf
    boxes = decode(output, lb, (960, 1280), conf=0.25, iou=0.45, max_det=10)
    assert len(boxes) == 1
    b = boxes[0]
    assert (b.x1, b.y1, b.x2, b.y2) == (540, 430, 740, 530)
    assert b.score == pytest.approx(0.9)


def test_decode_empty() -> None:
    output = np.zeros((1, 5, 8400), dtype=np.float32)
    assert decode(output, Letterbox(1, 0, 0), (640, 640), 0.25, 0.45, 10) == []
