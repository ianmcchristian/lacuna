"""Find empty shelf space from product boxes.

1. Group boxes into shelf rows by vertical overlap.
2. Walk each row left to right. Any horizontal hole wider than
   min_gap_ratio x the row's median product width is a gap. One missing
   product leaves a hole ~1.1-1.2x wide; normal spacing is ~0.1x, so the
   default of 0.8 catches a single out without flagging spacing. The row's
   ends are checked against the full shelf span too, so an empty spot at
   the edge still counts.
3. Drop any gap that's more than max_covered covered by product boxes, from
   any row. A hole is empty space. On real aisle photos, rows from two bays
   at different shelf heights can chain into one, and the "gaps" along it
   run straight through products. On 7 hand-labeled store photos this cut
   false gaps by more than half without losing a real hole (README).
4. Occupancy = 1 - gap width / shelf width, over every row we could check.

Skipped rows: fewer than min_row_size products (noise), or mostly cut off
by the top or bottom of the photo. A shelf you can only half see has no
reliable holes; without this, a sliver of the next shelf down shows up
as one long gap.

Limits: a row with no products at all has nothing to detect, so it won't
show up.
"""

import itertools
from dataclasses import dataclass
from statistics import median

from lacuna.vision.types import Box

DEFAULT_MIN_GAP_RATIO = 0.8
DEFAULT_MAX_COVERED = 0.2  # 0.1-0.2 all scored about the same; 0.25+ lets bands back in
EDGE_MARGIN = 0.01  # a box this close to the top or bottom of the frame is cut off


@dataclass(frozen=True, slots=True)
class Gap:
    """An empty stretch of shelf."""

    row: int
    x1: float
    y1: float
    x2: float
    y2: float
    width_ratio: float  # gap width / median product width in the row


@dataclass(frozen=True, slots=True)
class ShelfAnalysis:
    rows: list[list[Box]]
    gaps: list[Gap]
    occupancy: float | None  # None when no row had enough products to judge


def group_rows(boxes: list[Box], min_overlap: float = 0.5) -> list[list[Box]]:
    """Cluster boxes into rows, top to bottom. Each row is sorted left to right."""
    rows: list[list[Box]] = []
    bands: list[tuple[float, float]] = []  # running mean top/bottom of each row

    for box in sorted(boxes, key=lambda b: b.cy):
        if rows:
            top, bottom = bands[-1]
            overlap = min(bottom, box.y2) - max(top, box.y1)
            if overlap >= min_overlap * min(box.height, bottom - top):
                rows[-1].append(box)
                n = len(rows[-1])
                bands[-1] = (top + (box.y1 - top) / n, bottom + (box.y2 - bottom) / n)
                continue
        rows.append([box])
        bands.append((box.y1, box.y2))

    return [sorted(row, key=lambda b: b.x1) for row in rows]


def row_gaps(
    row: list[Box], index: int, left: float, right: float, min_gap_ratio: float
) -> list[Gap]:
    """Gaps in one row, including at either end of the shelf span."""
    product_width = median(b.width for b in row)
    top = median(b.y1 for b in row)
    bottom = median(b.y2 for b in row)
    min_width = min_gap_ratio * product_width

    gaps: list[Gap] = []
    cursor = left
    for box in [*row, Box(right, top, right, bottom)]:  # sentinel closes the row
        if box.x1 - cursor >= min_width:
            ratio = (box.x1 - cursor) / product_width
            gaps.append(Gap(index, cursor, top, box.x1, bottom, round(ratio, 2)))
        cursor = max(cursor, box.x2)
    return gaps


def union_length(spans: list[tuple[float, float]]) -> float:
    """Total length covered by a set of intervals, overlaps counted once."""
    total, reach = 0.0, float("-inf")
    for lo, hi in sorted(spans):
        lo = max(lo, reach)
        if hi > lo:
            total += hi - lo
            reach = hi
    return total


def covered_fraction(gap: Gap, boxes: list[Box]) -> float:
    """Share of the gap's area covered by product boxes. Exact: sweeps the vertical
    slabs between box edges and adds up the covered height in each."""
    area = (gap.x2 - gap.x1) * (gap.y2 - gap.y1)
    if area <= 0:
        return 1.0
    clipped = [
        (max(b.x1, gap.x1), max(b.y1, gap.y1), min(b.x2, gap.x2), min(b.y2, gap.y2)) for b in boxes
    ]
    clipped = [c for c in clipped if c[0] < c[2] and c[1] < c[3]]
    edges = sorted({x for c in clipped for x in (c[0], c[2])})
    covered = sum(
        (right - left)
        * union_length([(c[1], c[3]) for c in clipped if c[0] <= left and c[2] >= right])
        for left, right in itertools.pairwise(edges)
    )
    return covered / area


def is_cut_off(row: list[Box], image_height: float) -> bool:
    """True if most of the row runs off the top or bottom of the photo."""
    margin = EDGE_MARGIN * image_height
    clipped = sum(b.y1 <= margin or b.y2 >= image_height - margin for b in row)
    return clipped > len(row) / 2


def analyze_shelf(
    boxes: list[Box],
    min_gap_ratio: float = DEFAULT_MIN_GAP_RATIO,
    min_row_size: int = 2,
    image_height: float | None = None,
    max_covered: float = DEFAULT_MAX_COVERED,
) -> ShelfAnalysis:
    """Rows, gaps, and an occupancy estimate for one shelf photo.

    Pass image_height to skip rows cut off by the frame.
    """
    if not boxes:
        return ShelfAnalysis(rows=[], gaps=[], occupancy=None)

    left = min(b.x1 for b in boxes)
    right = max(b.x2 for b in boxes)
    rows = group_rows(boxes)

    gaps: list[Gap] = []
    checked_rows = 0
    for index, row in enumerate(rows):
        if len(row) < min_row_size:
            continue
        if image_height is not None and is_cut_off(row, image_height):
            continue
        checked_rows += 1
        found = row_gaps(row, index, left, right, min_gap_ratio)
        gaps.extend(g for g in found if covered_fraction(g, boxes) <= max_covered)

    if not checked_rows or right <= left:
        return ShelfAnalysis(rows=rows, gaps=gaps, occupancy=None)

    empty = sum(g.x2 - g.x1 for g in gaps)
    occupancy = 1 - empty / ((right - left) * checked_rows)
    return ShelfAnalysis(rows=rows, gaps=gaps, occupancy=round(occupancy, 4))
