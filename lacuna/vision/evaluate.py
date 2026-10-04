"""Score a detector against the hand-checked test shelves.

Shared by tests/test_model.py and scripts/benchmark.py so both grade the same way.
Only works from a repo checkout: the photos and expected gaps live in docs/.
Photo names are paths under docs/ without the .jpg.
"""

import json
from collections.abc import Sequence
from pathlib import Path

from lacuna.vision.gaps import Gap
from lacuna.vision.types import Box, Rect

GAP_TOLERANCE_PX = 25

# (row, x1, x2) of every hole in each photo, checked by eye against the overlays.
# JSON so the browser parity test in web/e2e reads the same file. The hard cases
# (angled, messy, empty-row) still fail and are left out on purpose; they're the
# INT8 calibration set instead (scripts/quantize.py).
EXPECTED_GAPS_FILE = Path(__file__).resolve().parents[2] / "docs" / "expected_gaps.json"


def load_expected_gaps(
    path: Path = EXPECTED_GAPS_FILE,
) -> dict[str, list[tuple[int, float, float]]]:
    data = json.loads(path.read_text())
    return {
        name: [(int(r), float(a), float(b)) for r, a, b in v["gaps"]] for name, v in data.items()
    }


HARD_CASES = ["scenarios/angled", "scenarios/messy", "scenarios/empty-row"]


def gaps_match(
    found: list[Gap], expected: list[tuple[int, float, float]], tol: float = GAP_TOLERANCE_PX
) -> bool:
    """Same number of gaps, each on the right row and within tol px at both ends."""
    if len(found) != len(expected):
        return False
    return all(
        g.row == row and abs(g.x1 - x1) <= tol and abs(g.x2 - x2) <= tol
        for g, (row, x1, x2) in zip(found, expected, strict=True)
    )


def iou(a: Rect, b: Rect) -> float:
    inter = max(0.0, min(a.x2, b.x2) - max(a.x1, b.x1)) * max(
        0.0, min(a.y2, b.y2) - max(a.y1, b.y1)
    )
    area = (a.x2 - a.x1) * (a.y2 - a.y1) + (b.x2 - b.x1) * (b.y2 - b.y1)
    return inter / (area - inter) if area - inter > 0 else 0.0


def greedy_match(
    reference: Sequence[Rect], candidate: Sequence[Rect], min_iou: float
) -> list[tuple[int, int]]:
    """One-to-one (reference, candidate) index pairs, best IoU first."""
    pairs = sorted(
        ((iou(r, c), i, j) for i, r in enumerate(reference) for j, c in enumerate(candidate)),
        reverse=True,
    )
    used_ref: set[int] = set()
    used_cand: set[int] = set()
    matches = []
    for overlap, i, j in pairs:
        if overlap < min_iou:
            break
        if i not in used_ref and j not in used_cand:
            used_ref.add(i)
            used_cand.add(j)
            matches.append((i, j))
    return matches


def box_agreement(
    reference: list[Box], candidate: list[Box], min_iou: float = 0.5
) -> tuple[float, float]:
    """(recall, precision) of candidate boxes against a reference model's boxes.

    Two empty lists agree fully.
    """
    matched = len(greedy_match(reference, candidate, min_iou))
    recall = matched / len(reference) if reference else 1.0
    precision = matched / len(candidate) if candidate else 1.0
    return recall, precision
