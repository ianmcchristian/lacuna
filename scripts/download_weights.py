"""Download the SKU-110K YOLO11 ONNX weights into models/ and verify the checksum.

Usage: uv run python scripts/download_weights.py [n|s]
"""

import hashlib
import sys
from pathlib import Path

import httpx

REPO = "https://huggingface.co/chistopat/sku110k-yolo11-object-detector/resolve/main"
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


def expected_sha256(client: httpx.Client, filename: str) -> str:
    listing = client.get(f"{REPO}/checksums.sha256").raise_for_status().text
    for line in listing.splitlines():
        digest, _, name = line.partition("  ")
        if name.strip().endswith(filename):
            return digest.strip()
    raise SystemExit(f"no checksum listed for {filename}")


def main(variant: str = "n") -> None:
    filename = f"sku110k-yolo11-{variant}640.onnx"
    target = MODELS_DIR / filename
    MODELS_DIR.mkdir(exist_ok=True)

    with httpx.Client(follow_redirects=True, timeout=60) as client:
        if not target.exists():
            print(f"downloading {filename}")
            with client.stream("GET", f"{REPO}/weights/{filename}") as resp:
                resp.raise_for_status()
                with target.open("wb") as out:
                    for chunk in resp.iter_bytes():
                        out.write(chunk)

        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != expected_sha256(client, filename):
            target.unlink()
            raise SystemExit("checksum mismatch, file removed")
    print(f"ok: {target}")


if __name__ == "__main__":
    main(*sys.argv[1:])
