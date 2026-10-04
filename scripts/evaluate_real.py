"""Score gap finding against holes marked by hand in real shelf photos.

Usage: uv run python scripts/evaluate_real.py samples/real

Labels come from scripts/label_gaps.py. Photos go through the same path as the
API (stored copy capped at 2048 px, then detect and find gaps). A found gap
counts if it overlaps a marked hole at IoU >= 0.3, one to one. Hand-drawn boxes
are loose, so 0.3 is lenient on the edges but still fails a gap that spans a
whole shelf to cover one hole. Writes overlays to <folder>/eval/:
yellow = marked hole, green = found it, red = false gap.
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

from lacuna.imaging import MAX_STORED_SIDE, fit_within, read_image
from lacuna.vision import Box, Gap, OnnxDetector, analyze_shelf
from lacuna.vision.evaluate import greedy_match

ROOT = Path(__file__).resolve().parent.parent
MODELS = {
    "fp32": ROOT / "models" / "sku110k-yolo11-s640.onnx",
    "INT8": ROOT / "models" / "sku110k-yolo11-s640-int8.onnx",
}
MIN_IOU = 0.3
YELLOW, GREEN, RED, GRAY = (10, 214, 255), (60, 200, 80), (40, 40, 230), (160, 160, 160)


@dataclass
class Score:
    holes: int = 0
    found: int = 0
    false: int = 0

    def add(self, other: "Score") -> None:
        self.holes += other.holes
        self.found += other.found
        self.false += other.false

    @property
    def recall(self) -> float:
        return self.found / self.holes if self.holes else 1.0

    @property
    def precision(self) -> float:
        predicted = self.found + self.false
        return self.found / predicted if predicted else 1.0


def marked_holes(fractions: list[list[float]], width: int, height: int) -> list[Box]:
    return [Box(x1 * width, y1 * height, x2 * width, y2 * height) for x1, y1, x2, y2 in fractions]


def draw(
    image: NDArray[np.uint8],
    products: list[Box],
    holes: list[Box],
    gaps: list[Gap],
    matched: set[int],
) -> NDArray[np.uint8]:
    out = image.copy()
    t = max(2, round(min(image.shape[:2]) / 400))
    for b in products:
        cv2.rectangle(out, (int(b.x1), int(b.y1)), (int(b.x2), int(b.y2)), GRAY, 1)
    for i, g in enumerate(gaps):
        color = GREEN if i in matched else RED
        cv2.rectangle(out, (int(g.x1), int(g.y1)), (int(g.x2), int(g.y2)), color, t * 2)
    for h in holes:
        cv2.rectangle(out, (int(h.x1), int(h.y1)), (int(h.x2), int(h.y2)), YELLOW, t)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--overlay-model", default="INT8", choices=list(MODELS))
    args = parser.parse_args()

    labels = json.loads((args.folder / "gaps.json").read_text())
    done = sorted(name for name, entry in labels.items() if entry["done"])
    if not done:
        raise SystemExit("no photos marked done yet; run scripts/label_gaps.py first")
    out_dir = args.folder / "eval"
    out_dir.mkdir(exist_ok=True)

    detectors = {
        name: OnnxDetector(path, threads=0) for name, path in MODELS.items() if path.exists()
    }
    totals = {name: Score() for name in detectors}
    rows = []
    for photo in done:
        image = read_image(args.folder / photo)
        if image is None:
            raise SystemExit(f"can't read {photo}")
        image = fit_within(image, MAX_STORED_SIDE)
        height, width = image.shape[:2]
        holes = marked_holes(labels[photo]["gaps"], width, height)
        cells = [photo, str(len(holes))]
        for name, detector in detectors.items():
            products = detector.detect(image)
            gaps = analyze_shelf(products, image_height=height).gaps
            matches = greedy_match(holes, gaps, MIN_IOU)
            score = Score(len(holes), len(matches), len(gaps) - len(matches))
            totals[name].add(score)
            cells.append(f"{score.found} found, {score.false} false")
            if name == args.overlay_model:
                overlay = draw(image, products, holes, gaps, {j for _, j in matches})
                cv2.imwrite(str(out_dir / f"{Path(photo).stem}.jpg"), overlay)
        rows.append(cells)

    print(f"{len(done)} of {len(labels)} labeled photos, IoU >= {MIN_IOU}\n")
    print("| Photo | Holes | " + " | ".join(detectors) + " |")
    print("|---|---|" + "---|" * len(detectors))
    for cells in rows:
        print("| " + " | ".join(cells) + " |")
    print("\n| Model | Holes | Found | False gaps | Recall | Precision |")
    print("|---|---|---|---|---|---|")
    for name, s in totals.items():
        print(
            f"| {name} | {s.holes} | {s.found} | {s.false} | {s.recall:.0%} | {s.precision:.0%} |"
        )
    print(f"\noverlays: {out_dir}/")


if __name__ == "__main__":
    main()
