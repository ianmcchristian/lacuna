"""Make an INT8 copy of the detector with static quantization.

Usage: uv run python scripts/quantize.py [models/sku110k-yolo11-s640.onnx]
Writes <name>-int8.onnx next to the input.

Two choices that matter, both found by testing (numbers in the README):
- The box decode at the end of the head stays float. It concatenates pixel
  coords (0-640) with scores (0-1) into one tensor, and one INT8 scale over
  both rounds every score to 0: the model finds nothing.
- Calibration uses the three hard-case shelves. They're not regression tests,
  so the photos INT8 is graded on were never used to calibrate it, and their
  bare shelves and odd angles cover more of the activation range. Calibrating
  on the demo shelves instead passed 5-7 of 8 tests; these pass 8 of 8.
"""

import sys
import tempfile
from pathlib import Path

import numpy as np
import onnx
from numpy.typing import NDArray
from onnxruntime.quantization import (
    CalibrationDataReader,
    CalibrationMethod,
    QuantFormat,
    QuantType,
    quantize_static,
)
from onnxruntime.quantization.shape_inference import quant_pre_process

from lacuna.imaging import read_image
from lacuna.vision.detector import letterbox
from lacuna.vision.evaluate import HARD_CASES

ROOT = Path(__file__).resolve().parent.parent
HEAD = "/model.23/"  # detection head; its conv branches start with /model.23/cv


class ShelfPhotos(CalibrationDataReader):  # type: ignore[misc]
    def __init__(self, input_name: str, size: int) -> None:
        feeds = []
        for name in HARD_CASES:
            image = read_image(ROOT / "docs" / f"{name}.jpg")
            if image is None:
                raise SystemExit(f"missing calibration photo docs/{name}.jpg")
            feeds.append({input_name: letterbox(image, size)[0]})
        self._feeds = iter(feeds)

    def get_next(self) -> dict[str, NDArray[np.float32]] | None:
        return next(self._feeds, None)


def decode_nodes(model: onnx.ModelProto) -> list[str]:
    """Head nodes after the conv branches: reshape, DFL, sigmoid, concat."""
    return [
        n.name
        for n in model.graph.node
        if n.name.startswith(HEAD) and not n.name.startswith(f"{HEAD}cv")
    ]


def main(source: str = "models/sku110k-yolo11-s640.onnx") -> None:
    src = Path(source)
    out = src.with_name(f"{src.stem}-int8.onnx")
    model = onnx.load(src)
    model_input = model.graph.input[0]
    size = model_input.type.tensor_type.shape.dim[2].dim_value

    with tempfile.TemporaryDirectory() as tmp:
        prepped = Path(tmp) / "prepped.onnx"
        quant_pre_process(src, prepped, skip_symbolic_shape=True)  # shapes are already fixed
        quantize_static(
            prepped,
            out,
            ShelfPhotos(model_input.name, size),
            quant_format=QuantFormat.QDQ,
            activation_type=QuantType.QUInt8,
            weight_type=QuantType.QInt8,
            per_channel=True,
            calibrate_method=CalibrationMethod.MinMax,
            nodes_to_exclude=decode_nodes(model),
        )
    print(f"ok: {out} ({src.stat().st_size / 1e6:.1f} MB -> {out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main(*sys.argv[1:])
