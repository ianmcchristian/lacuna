"""Image decode and encode helpers. The only place raw OpenCV arrays get typed."""

from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

ALLOWED_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})

# stored copies are capped here; the model only sees 640 px anyway
MAX_STORED_SIDE = 2048


def decode_image(data: bytes) -> NDArray[np.uint8] | None:
    """Bytes to a BGR array, or None if it isn't a readable image. Applies EXIF rotation."""
    if not data:
        return None
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    return None if image is None else np.asarray(image, dtype=np.uint8)


def read_image(path: Path) -> NDArray[np.uint8] | None:
    image = cv2.imread(str(path))
    return None if image is None else np.asarray(image, dtype=np.uint8)


def fit_within(image: NDArray[np.uint8], max_side: int) -> NDArray[np.uint8]:
    """Shrink so the longest side is at most max_side. Never upscales."""
    height, width = image.shape[:2]
    scale = max_side / max(height, width)
    if scale >= 1:
        return image
    size = (round(width * scale), round(height * scale))
    return np.asarray(cv2.resize(image, size, interpolation=cv2.INTER_AREA), dtype=np.uint8)


def encode_jpeg(image: NDArray[np.uint8], quality: int = 85) -> bytes:
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("jpeg encode failed")
    return bytes(buf.tobytes())
