"""Score baseline compare on simulated retakes of a stocked shelf.

For each trial, random products are painted out of the fully stocked scenario,
the photo is retaken (rotated, zoomed, shifted, tilted), and the API's logic is
run: line the photos up, find gaps, name the baseline products in each gap.
Named products that really were removed are hits; the rest are false.

A removed product that wasn't named is split by cause: no gap was found there
at all (the gap finder's miss), or a gap was there but the match failed.

Usage: uv run python scripts/evaluate_baseline.py [--model models/...onnx]
"""

import argparse
import random
from pathlib import Path

from lacuna.imaging import read_image
from lacuna.vision import OnnxDetector, analyze_shelf
from lacuna.vision.align import MIN_OVERLAP, find_homography, inside_fraction, map_rect, was_here
from lacuna.vision.simulate import paint_out, retake

ROOT = Path(__file__).resolve().parent.parent
PHOTO = ROOT / "docs/scenarios/fully-stocked.jpg"
SOLD_PER_TRIAL = 8
# angle (deg), zoom, shift (px), tilt (px)
RETAKES = [
    (0, 1.0, (0, 0), 0),
    (3, 0.92, (40, -25), 0),
    (-4, 1.08, (-60, 30), 30),
    (2, 0.85, (80, 40), 50),
    (6, 0.8, (-90, -60), 70),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=ROOT / "models/sku110k-yolo11-s640-int8.onnx")
    parser.add_argument("--seed", type=int, default=3)
    args = parser.parse_args()

    detector = OnnxDetector(args.model)
    stocked = read_image(PHOTO)
    if stocked is None:
        raise SystemExit(f"can't read {PHOTO}")
    products = detector.detect(stocked)
    rng = random.Random(args.seed)

    totals = {"named": 0, "right": 0, "removed": 0, "no_gap": 0, "unmatched": 0, "unaligned": 0}
    print(f"{'retake':<32}{'named':>7}{'right':>7}{'no gap':>8}{'unmatched':>11}")
    for angle, zoom, shift, tilt in RETAKES:
        sold = rng.sample(products, SOLD_PER_TRIAL)
        later = retake(paint_out(stocked, sold), angle, zoom, shift, tilt)
        totals["removed"] += len(sold)
        label = f"{angle:+} deg x{zoom} {shift} tilt {tilt}"

        h = find_homography(stocked, later)
        if h is None:
            totals["unaligned"] += 1
            print(f"{label:<32}  didn't line up")
            continue
        gaps = analyze_shelf(detector.detect(later), image_height=later.shape[0]).gaps
        named = [b for g in gaps for b in was_here(h, products, g)]
        right = sum(1 for b in named if any(b is s for s in sold))
        missed = [s for s in sold if not any(b is s for b in named)]
        no_gap = sum(
            1
            for s in missed
            if max((inside_fraction(map_rect(h, s), g) for g in gaps), default=0) == 0
        )
        print(f"{label:<32}{len(named):>7}{right:>7}{no_gap:>8}{len(missed) - no_gap:>11}")
        totals["named"] += len(named)
        totals["right"] += right
        totals["no_gap"] += no_gap
        totals["unmatched"] += len(missed) - no_gap

    print(
        f"\nnamed {totals['named']}, of which really removed {totals['right']}; "
        f"found {totals['right']} of {totals['removed']} removed. "
        f"Misses: {totals['no_gap']} with no gap found there, "
        f"{totals['unmatched']} in a gap but under {MIN_OVERLAP:.0%} overlap. "
        f"Retakes that didn't line up: {totals['unaligned']}."
    )


if __name__ == "__main__":
    main()
