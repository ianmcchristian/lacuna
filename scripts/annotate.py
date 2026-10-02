"""Run the detector on a local photo and save an overlay next to it.

Usage: uv run python scripts/annotate.py samples/shelf.jpg [--model models/x.onnx]
"""

import argparse
import time
from pathlib import Path

import cv2

from lacuna.config import Settings
from lacuna.imaging import read_image
from lacuna.vision import OnnxDetector, analyze_shelf
from lacuna.vision.draw import draw_overlay


def main() -> None:
    settings = Settings()
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--model", type=Path, default=settings.model_path)
    parser.add_argument("--min-gap-ratio", type=float, default=settings.min_gap_ratio)
    args = parser.parse_args()

    image = read_image(args.image)
    if image is None:
        raise SystemExit(f"can't read {args.image}")

    detector = OnnxDetector(args.model, settings.conf_threshold, settings.iou_threshold)
    start = time.perf_counter()
    boxes = detector.detect(image)
    elapsed_ms = (time.perf_counter() - start) * 1000
    result = analyze_shelf(boxes, args.min_gap_ratio)

    out_path = args.image.with_name(f"{args.image.stem}.overlay.jpg")
    cv2.imwrite(str(out_path), draw_overlay(image, boxes, result.gaps))

    print(f"{len(boxes)} products, {len(result.rows)} rows, {len(result.gaps)} gaps")
    print(f"occupancy: {result.occupancy}  inference: {elapsed_ms:.0f} ms")
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()
