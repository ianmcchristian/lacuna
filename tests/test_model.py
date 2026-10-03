"""Real model on real-looking shelves. Skipped if the weights aren't downloaded (CI has them)."""

from pathlib import Path

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from lacuna.imaging import read_image
from lacuna.vision import OnnxDetector, analyze_shelf
from tests.conftest import MODELS_DIR

WEIGHTS = MODELS_DIR / "sku110k-yolo11-s640.onnx"
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"

pytestmark = [
    pytest.mark.model,
    pytest.mark.skipif(not WEIGHTS.exists(), reason="run scripts/download_weights.py s"),
]


@pytest.fixture(scope="module")
def detector() -> OnnxDetector:
    return OnnxDetector(WEIGHTS)


def photo(name: str) -> NDArray[np.uint8]:
    image = read_image(DOCS_DIR / f"{name}.jpg")
    assert image is not None
    return image


def test_blank_image_finds_nothing(detector: OnnxDetector) -> None:
    assert detector.detect(np.full((480, 640, 3), 128, dtype=np.uint8)) == []


# (row, x1, x2) of every hole in each photo, checked by eye against the overlays.
# Scenarios that still fail (angled, messy, empty-row) are documented in the README.
EXPECTED_GAPS = {
    "demo/canned-goods": [(1, 463, 779), (3, 889, 1129)],  # 3 cans mid-row, 2 at the end
    "demo/cereal": [(1, 17, 362), (1, 667, 808)],  # 2 boxes at the start, 1 mid-row
    "demo/bottles": [(1, 382, 833), (2, 106, 206)],  # 4 bottles mid-row, 1 near the start
    "scenarios/fully-stocked": [],
    "scenarios/depleted": [
        (0, 214, 541),
        (0, 699, 1016),
        (1, 219, 556),
        (1, 743, 1057),
        (2, 188, 549),
        (2, 725, 1018),
    ],
    "scenarios/mixed-sizes": [(0, 1070, 1249), (1, 499, 712)],  # cans next to 2 L bottles
    "scenarios/cooler-glare": [(1, 335, 527)],
    "scenarios/low-light": [(0, 214, 458)],
}


@pytest.mark.parametrize("name", sorted(EXPECTED_GAPS))
def test_finds_every_hole_and_nothing_else(detector: OnnxDetector, name: str) -> None:
    image = photo(name)
    gaps = analyze_shelf(detector.detect(image), image_height=image.shape[0]).gaps
    found = [(g.row, g.x1, g.x2) for g in gaps]
    assert len(found) == len(EXPECTED_GAPS[name]), found
    for (row, x1, x2), (exp_row, exp_x1, exp_x2) in zip(found, EXPECTED_GAPS[name], strict=True):
        assert row == exp_row
        assert x1 == pytest.approx(exp_x1, abs=25)
        assert x2 == pytest.approx(exp_x2, abs=25)


def test_inpainted_hole_is_found(detector: OnnxDetector) -> None:
    """Paint one bottle out of the full top row and check a gap shows up right there.

    Inpainting, not a solid fill: a flat dark rectangle the size of a can
    still looks like a can to the model.
    """
    image = photo("demo/bottles")
    before = analyze_shelf(detector.detect(image))
    assert not [g for g in before.gaps if g.row == 0]  # top row starts full
    top = before.rows[0]
    target = top[len(top) // 2]

    mask = np.zeros(image.shape[:2], dtype=np.uint8)
    x1, y1, x2, y2 = (int(v) for v in (target.x1, target.y1, target.x2, target.y2))
    mask[y1:y2, x1:x2] = 255
    cut = np.asarray(cv2.inpaint(image, mask, 5, cv2.INPAINT_TELEA), dtype=np.uint8)

    after = analyze_shelf(detector.detect(cut))
    hits = [g for g in after.gaps if g.row == 0 and g.x1 <= x1 + 10 and g.x2 >= x2 - 10]
    assert hits, f"no gap over the removed bottle, gaps={after.gaps}"
