"""Seed a simulated shelf history: a full shelf selling down, a restock, then
selling down again in a retaken photo. The first (stocked) scan is the baseline.

Products are painted out a few at a time (OpenCV inpainting, as in
test_inpainted_hole_is_found), and every frame is scanned through the real API,
so the history is the API's own numbers. Only the photos are simulated, and the
shelf code says so. The last frame is rotated, zoomed, and shifted like a
handheld retake, so the baseline compare has to line the photos up.

Usage:
  uv run python scripts/seed_demo_shelf.py --preview /tmp/frames      # local check only
  uv run python scripts/seed_demo_shelf.py --api https://lacuna-mp1n.onrender.com
  ... --api URL --skip 6   # frames 0-5 are already there, add the rest
"""

import argparse
import random
from pathlib import Path

import cv2
import httpx
import numpy as np
from numpy.typing import NDArray

from lacuna.config import Settings
from lacuna.imaging import encode_jpeg, read_image
from lacuna.vision import Box, OnnxDetector, analyze_shelf
from lacuna.vision.align import find_homography, was_here
from lacuna.vision.simulate import paint_out, retake

ROOT = Path(__file__).resolve().parent.parent
PHOTO = ROOT / "docs/scenarios/fully-stocked.jpg"
SHELF = "demo-simulated"
# Products sold between scans; a restock follows. Stops at 14 sold: past that,
# the inpainted smears get big enough that the model starts finding "products"
# in them and occupancy climbs back up. Real empty shelf doesn't do that.
REMOVE_PER_STEP = [0, 3, 3, 4, 4]


def frames(image: NDArray[np.uint8], products: list[Box], seed: int) -> list[NDArray[np.uint8]]:
    """Selling down, one frame per step, the full shelf again, then a retake mid-sell-down."""
    rng = random.Random(seed)
    left = list(products)
    sold: list[Box] = []
    out = []
    for count in REMOVE_PER_STEP:
        # sell next to what already sold, like a real shelf, so holes grow
        for _ in range(count):
            near = sold[-1] if sold else rng.choice(left)

            def distance(b: Box, near: Box = near) -> float:
                return abs(b.y1 - near.y1) * 3 + abs(b.x1 - near.x1) + rng.random() * 40

            pick = min(left, key=distance)
            left.remove(pick)
            sold.append(pick)
        out.append(paint_out(image, sold))
    out.append(image)  # restocked
    out.append(retake(out[3], 2.5, 0.94, (30, -20)))  # selling down again, from a new spot
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--preview", type=Path, help="write frames here and print local scores")
    target.add_argument("--api", help="API base URL to scan through")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--skip", type=int, default=0, help="frames already uploaded")
    args = parser.parse_args()

    detector = OnnxDetector(Settings().model_path)
    image = read_image(PHOTO)
    if image is None:
        raise SystemExit(f"can't read {PHOTO}")
    shots = frames(image, detector.detect(image), args.seed)

    if args.preview:
        args.preview.mkdir(parents=True, exist_ok=True)
        stocked = detector.detect(shots[0])
        for i, shot in enumerate(shots):
            result = analyze_shelf(detector.detect(shot), image_height=shot.shape[0])
            h = find_homography(shots[0], shot)
            sold = sum(len(was_here(h, stocked, g)) for g in result.gaps) if h is not None else None
            cv2.imwrite(str(args.preview / f"frame{i}.jpg"), shot)
            gaps = len(result.gaps)
            print(f"frame {i}: occupancy {result.occupancy}, {gaps} gaps, sold vs baseline {sold}")
        return

    with httpx.Client(base_url=args.api.rstrip("/"), timeout=180) as api:
        for i, shot in list(enumerate(shots))[args.skip :]:
            files = {"file": (f"{SHELF}-{i}.jpg", encode_jpeg(shot, quality=90), "image/jpeg")}
            upload = api.post("/images", files=files, data={"shelf": SHELF}).raise_for_status()
            detect = api.post("/detect", json={"image_id": upload.json()["id"]})
            scan = detect.raise_for_status().json()
            print(f"frame {i}: occupancy {scan['occupancy']}, {scan['gap_count']} gaps")

        history = api.get(f"/shelves/{SHELF}/history", params={"limit": 500}).raise_for_status()
        scans = history.json()["scans"]  # newest first
        baseline = scans[-1]["scan_id"]
        api.post(f"/shelves/{SHELF}/baseline", json={"scan_id": baseline}).raise_for_status()
        missing = api.get(f"/results/{scans[0]['scan_id']}/missing").raise_for_status().json()
        sold = sum(len(g["products"]) for g in missing["gaps"])
        print(f"baseline {baseline}; latest scan aligned={missing['aligned']}, {sold} sold out")


if __name__ == "__main__":
    main()
