"""Compare models on size, CPU latency, and accuracy. Prints a markdown table.

Usage: uv run python scripts/benchmark.py [--runs 5] [--threads 1]

Latency is detect() end to end (letterbox, inference, decode, NMS), median
over every test shelf. Accuracy has no hand-labelled boxes to compare to, so
it's measured two ways: agreement with the float model's boxes (IoU >= 0.5),
and how many of the 8 regression shelves come back with exactly the right gaps.
"""

import argparse
import time
from pathlib import Path
from statistics import mean, median

from lacuna.imaging import read_image
from lacuna.vision import OnnxDetector, analyze_shelf
from lacuna.vision.evaluate import EXPECTED_GAPS, HARD_CASES, box_agreement, gaps_match

ROOT = Path(__file__).resolve().parent.parent
MODELS = {
    "YOLO11s fp32 (baseline)": "sku110k-yolo11-s640.onnx",
    "YOLO11s INT8": "sku110k-yolo11-s640-int8.onnx",
    "YOLO11n fp32": "sku110k-yolo11-n640.onnx",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--threads", type=int, default=1, help="0 = one per core")
    args = parser.parse_args()

    photos = {}
    for name in [*EXPECTED_GAPS, *HARD_CASES]:
        image = read_image(ROOT / "docs" / f"{name}.jpg")
        if image is None:
            raise SystemExit(f"missing docs/{name}.jpg")
        photos[name] = image

    baseline = None
    print(f"{len(photos)} shelves, {args.runs} runs each, {args.threads or 'all'} thread(s)\n")
    print("| Model | Size | Median latency | Boxes matched (recall / precision) | Gap tests |")
    print("|---|---|---|---|---|")
    for label, filename in MODELS.items():
        path = ROOT / "models" / filename
        if not path.exists():
            print(f"| {label} | missing, skipped | | | |")
            continue
        detector = OnnxDetector(path, threads=args.threads)
        times, boxes = [], {}
        for name, image in photos.items():
            boxes[name] = detector.detect(image)  # warm-up
            for _ in range(args.runs):
                start = time.perf_counter()
                detector.detect(image)
                times.append((time.perf_counter() - start) * 1000)
        baseline = baseline or boxes

        agreement = [box_agreement(baseline[n], boxes[n]) for n in photos]
        passed = sum(
            gaps_match(analyze_shelf(boxes[n], image_height=photos[n].shape[0]).gaps, expected)
            for n, expected in EXPECTED_GAPS.items()
        )
        print(
            f"| {label} | {path.stat().st_size / 1e6:.1f} MB | {median(times):.0f} ms "
            f"| {mean(a[0] for a in agreement):.1%} / {mean(a[1] for a in agreement):.1%} "
            f"| {passed}/{len(EXPECTED_GAPS)} |"
        )


if __name__ == "__main__":
    main()
