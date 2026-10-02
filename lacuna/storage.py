"""Where uploaded image bytes live. Metadata lives in the database."""

from pathlib import Path
from typing import Protocol


class ImageStore(Protocol):
    def save(self, image_id: str, data: bytes) -> None: ...

    def load(self, image_id: str) -> bytes: ...


class LocalImageStore:
    """Files on local disk, one per image id. Fine for dev and a single container."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, image_id: str, data: bytes) -> None:
        (self._root / image_id).write_bytes(data)

    def load(self, image_id: str) -> bytes:
        return (self._root / image_id).read_bytes()
