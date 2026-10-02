"""Download the SKU-110K YOLO11 ONNX weights into models/ and verify the checksum.

Usage: uv run python scripts/download_weights.py [n|s]

The model repo revision and file hashes are pinned here, so a changed upstream
file fails the build instead of silently swapping the model.
"""

import hashlib
import sys
from pathlib import Path

import httpx

REVISION = "ee1b8ac34eb3b68969ffa8165e50c43457fe4e35"
REPO = f"https://huggingface.co/chistopat/sku110k-yolo11-object-detector/resolve/{REVISION}"
SHA256 = {
    "n": "5810269bf9687ca93b0d4e1bc91cb83ac4311cd48d91c4f6091777721ba083c5",
    "s": "e8bc019d4241cf9486c4b6aaf50d51b652b3a0d641fce1189fbba12136794cd1",
}
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


def main(variant: str = "s") -> None:
    if variant not in SHA256:
        raise SystemExit(f"variant must be one of {sorted(SHA256)}")
    filename = f"sku110k-yolo11-{variant}640.onnx"
    target = MODELS_DIR / filename
    MODELS_DIR.mkdir(exist_ok=True)

    if not target.exists():
        print(f"downloading {filename}")
        with (
            httpx.Client(follow_redirects=True, timeout=60) as client,
            client.stream("GET", f"{REPO}/weights/{filename}") as resp,
        ):
            resp.raise_for_status()
            with target.open("wb") as out:
                for chunk in resp.iter_bytes():
                    out.write(chunk)

    if hashlib.sha256(target.read_bytes()).hexdigest() != SHA256[variant]:
        target.unlink()
        raise SystemExit("checksum mismatch, file removed")
    print(f"ok: {target}")


if __name__ == "__main__":
    main(*sys.argv[1:])
