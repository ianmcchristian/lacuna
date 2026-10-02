"""Find empty shelf space from product boxes.

1. Group boxes into shelf rows by vertical overlap.
2. Walk each row left to right. Any horizontal hole wider than
   min_gap_ratio x the row's median product width is a gap. One missing
   product leaves a hole ~1.1-1.2x wide; normal spacing is ~0.1x, so the
   default of 0.8 catches a single out without flagging spacing. The row's
   ends are checked against the full shelf span too, so an empty spot at
   the edge still counts.
3. Occupancy = 1 - gap width / shelf width, over every row we could check.

Limits: a row with no products at all has nothing to detect, so it won't
show up. Rows with fewer than min_row_size products are skipped as noise.
"""

from dataclasses import dataclass
from statistics import median

from lacuna.vision.types import Box

DEFAULT_MIN_GAP_RATIO = 0.8


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


def analyze_shelf(
    boxes: list[Box], min_gap_ratio: float = DEFAULT_MIN_GAP_RATIO, min_row_size: int = 2
) -> ShelfAnalysis:
    """Rows, gaps, and an occupancy estimate for one shelf photo."""
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
        checked_rows += 1
        gaps.extend(row_gaps(row, index, left, right, min_gap_ratio))

    if not checked_rows or right <= left:
        return ShelfAnalysis(rows=rows, gaps=gaps, occupancy=None)

    empty = sum(g.x2 - g.x1 for g in gaps)
    occupancy = 1 - empty / ((right - left) * checked_rows)
    return ShelfAnalysis(rows=rows, gaps=gaps, occupancy=round(occupancy, 4))
