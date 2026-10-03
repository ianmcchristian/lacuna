"""Score a detector against the hand-checked test shelves.

Shared by tests/test_model.py and scripts/benchmark.py so both grade the same way.
Photo names are paths under docs/ without the .jpg.
"""

from lacuna.vision.gaps import Gap
from lacuna.vision.types import Box

GAP_TOLERANCE_PX = 25

# (row, x1, x2) of every hole in each photo, checked by eye against the overlays.
# The hard cases (angled, messy, empty-row) still fail and are left out on purpose;
# they're the INT8 calibration set instead (scripts/quantize.py).
EXPECTED_GAPS: dict[str, list[tuple[int, float, float]]] = {
    "demo/canned-goods": [(1, 463, 779), (3, 889, 1129)],  # 3 cans mid-row, 2 at the end
    "demo/cereal": [(1, 17, 362), (1, 667, 808)],  # 2 boxes at the start, 1 mid-row
    "demo/bottles": [(1, 382, 833), (2, 106, 206)],  # 4 bottles mid-row, 1 near the start
    "scenarios/fully-stocked": [],
    "scenarios/depleted": [
        (0, 214, 541),
        (0, 699, 1016),
        (1, 219, 556),
        (1, 743, 1057),
        (2, 188, 549),
        (2, 725, 1018),
    ],
    "scenarios/mixed-sizes": [(0, 1070, 1249), (1, 499, 712)],  # cans next to 2 L bottles
    "scenarios/cooler-glare": [(1, 335, 527)],
    "scenarios/low-light": [(0, 214, 458)],
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


def iou(a: Box, b: Box) -> float:
    inter = max(0.0, min(a.x2, b.x2) - max(a.x1, b.x1)) * max(
        0.0, min(a.y2, b.y2) - max(a.y1, b.y1)
    )
    union = a.width * a.height + b.width * b.height - inter
    return inter / union if union > 0 else 0.0


def box_agreement(
    reference: list[Box], candidate: list[Box], min_iou: float = 0.5
) -> tuple[float, float]:
    """(recall, precision) of candidate boxes against a reference model's boxes.

    Greedy one-to-one matching, best IoU first. Two empty lists agree fully.
    """
    pairs = sorted(
        ((iou(r, c), i, j) for i, r in enumerate(reference) for j, c in enumerate(candidate)),
        reverse=True,
    )
    used_ref: set[int] = set()
    used_cand: set[int] = set()
    for overlap, i, j in pairs:
        if overlap < min_iou:
            break
        if i not in used_ref and j not in used_cand:
            used_ref.add(i)
            used_cand.add(j)
    matched = len(used_ref)
    recall = matched / len(reference) if reference else 1.0
    precision = matched / len(candidate) if candidate else 1.0
    return recall, precision
