"""Real models on real-looking shelves. Skipped if the weights aren't there (CI has them).

Every check runs on the float model and its INT8 copy (scripts/quantize.py).
"""

from pathlib import Path

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from lacuna.imaging import read_image
from lacuna.vision import OnnxDetector, analyze_shelf
from lacuna.vision.evaluate import EXPECTED_GAPS, gaps_match
from tests.conftest import MODELS_DIR

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
WEIGHTS = {
    "fp32": (MODELS_DIR / "sku110k-yolo11-s640.onnx", "run scripts/download_weights.py s"),
    "int8": (MODELS_DIR / "sku110k-yolo11-s640-int8.onnx", "run scripts/quantize.py"),
}

pytestmark = pytest.mark.model


@pytest.fixture(scope="module", params=sorted(WEIGHTS))
def detector(request: pytest.FixtureRequest) -> OnnxDetector:
    path, how = WEIGHTS[request.param]
    if not path.exists():
        pytest.skip(how)
    return OnnxDetector(path)


def photo(name: str) -> NDArray[np.uint8]:
    image = read_image(DOCS_DIR / f"{name}.jpg")
    assert image is not None
    return image


def test_blank_image_finds_nothing(detector: OnnxDetector) -> None:
    assert detector.detect(np.full((480, 640, 3), 128, dtype=np.uint8)) == []


@pytest.mark.parametrize("name", sorted(EXPECTED_GAPS))
def test_finds_every_hole_and_nothing_else(detector: OnnxDetector, name: str) -> None:
    image = photo(name)
    gaps = analyze_shelf(detector.detect(image), image_height=image.shape[0]).gaps
    found = [(g.row, round(g.x1), round(g.x2)) for g in gaps]
    assert gaps_match(gaps, EXPECTED_GAPS[name]), f"expected {EXPECTED_GAPS[name]}, got {found}"


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
