"""Image decode and encode helpers. The only place raw OpenCV arrays get typed."""

from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

ALLOWED_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


def decode_image(data: bytes) -> NDArray[np.uint8] | None:
    """Bytes to a BGR array, or None if it isn't a readable image. Applies EXIF rotation."""
    if not data:
        return None
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    return None if image is None else np.asarray(image, dtype=np.uint8)


def read_image(path: Path) -> NDArray[np.uint8] | None:
    image = cv2.imread(str(path))
    return None if image is None else np.asarray(image, dtype=np.uint8)


def encode_jpeg(image: NDArray[np.uint8], quality: int = 85) -> bytes:
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("jpeg encode failed")
    return bytes(buf.tobytes())
