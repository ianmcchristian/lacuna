"""YOLO11 product detector running on ONNX Runtime.

The SKU-110K export has one class ("object") and outputs [1, 5, N]:
cx, cy, w, h, score per candidate, in letterboxed input pixels. No NMS is
baked in, so it happens here.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np
import onnxruntime as ort
from numpy.typing import NDArray

from lacuna.vision.types import Box

PAD_VALUE = 114  # same gray Ultralytics pads with


class Detector(Protocol):
    """Anything that turns a BGR image into product boxes."""

    @property
    def name(self) -> str: ...

    def detect(self, image: NDArray[np.uint8]) -> list[Box]: ...


@dataclass(frozen=True, slots=True)
class Letterbox:
    """How an image was scaled and padded to fit the model input."""

    scale: float
    pad_x: int
    pad_y: int


def letterbox(image: NDArray[np.uint8], size: int) -> tuple[NDArray[np.float32], Letterbox]:
    """Resize keeping aspect ratio, pad to a square, return an NCHW float blob."""
    h, w = image.shape[:2]
    scale = min(size / h, size / w)
    new_w, new_h = round(w * scale), round(h * scale)
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    pad_x, pad_y = (size - new_w) // 2, (size - new_h) // 2
    canvas = np.full((size, size, 3), PAD_VALUE, dtype=np.uint8)
    canvas[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized

    # BGR -> RGB, HWC -> CHW, add batch dim, scale to 0..1
    blob = canvas[:, :, ::-1].transpose(2, 0, 1)[np.newaxis].astype(np.float32) / 255.0
    return np.ascontiguousarray(blob), Letterbox(scale, pad_x, pad_y)


def nms(boxes: NDArray[np.float32], scores: NDArray[np.float32], iou: float) -> list[int]:
    """Greedy non-max suppression. boxes are xyxy. Returns kept indices, best first."""
    x1, y1, x2, y2 = boxes.T
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep: list[int] = []

    while order.size:
        best, rest = order[0], order[1:]
        keep.append(int(best))
        ix1 = np.maximum(x1[best], x1[rest])
        iy1 = np.maximum(y1[best], y1[rest])
        ix2 = np.minimum(x2[best], x2[rest])
        iy2 = np.minimum(y2[best], y2[rest])
        inter = np.clip(ix2 - ix1, 0, None) * np.clip(iy2 - iy1, 0, None)
        overlap = inter / (areas[best] + areas[rest] - inter + 1e-9)
        order = rest[overlap <= iou]

    return keep


def decode(
    output: NDArray[np.float32],
    lb: Letterbox,
    image_shape: tuple[int, int],
    conf: float,
    iou: float,
    max_det: int,
) -> list[Box]:
    """Turn raw model output into boxes in original image pixels."""
    preds = output[0].T  # (N, 5)
    preds = preds[preds[:, 4] >= conf]
    if not len(preds):
        return []

    cx, cy, w, h, scores = preds.T
    h_img, w_img = image_shape
    xyxy = np.stack(
        [
            np.clip((cx - w / 2 - lb.pad_x) / lb.scale, 0, w_img),
            np.clip((cy - h / 2 - lb.pad_y) / lb.scale, 0, h_img),
            np.clip((cx + w / 2 - lb.pad_x) / lb.scale, 0, w_img),
            np.clip((cy + h / 2 - lb.pad_y) / lb.scale, 0, h_img),
        ],
        axis=1,
    ).astype(np.float32)

    keep = nms(xyxy, scores.astype(np.float32), iou)[:max_det]
    boxes = []
    for i in keep:
        x1, y1, x2, y2 = (float(v) for v in xyxy[i])
        boxes.append(Box(x1, y1, x2, y2, float(scores[i])))
    return boxes


class OnnxDetector:
    """Loads the ONNX model once and runs CPU inference."""

    def __init__(
        self,
        model_path: Path,
        conf: float = 0.25,
        iou: float = 0.45,
        max_det: int = 1000,
    ) -> None:
        self._session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        model_input = self._session.get_inputs()[0]
        self._input_name: str = model_input.name
        self._size = int(model_input.shape[2])
        self._conf, self._iou, self._max_det = conf, iou, max_det
        self._name = model_path.stem

    @property
    def name(self) -> str:
        return self._name

    def detect(self, image: NDArray[np.uint8]) -> list[Box]:
        blob, lb = letterbox(image, self._size)
        (output,) = self._session.run(None, {self._input_name: blob})
        return decode(output, lb, image.shape[:2], self._conf, self._iou, self._max_det)
