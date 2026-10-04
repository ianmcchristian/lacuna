from lacuna.vision import Box, Gap
from lacuna.vision.evaluate import box_agreement, gaps_match, greedy_match, iou


def test_iou() -> None:
    a = Box(0, 0, 10, 10)
    assert iou(a, a) == 1.0
    assert iou(a, Box(5, 0, 15, 10)) == 50 / 150
    assert iou(a, Box(20, 20, 30, 30)) == 0.0


def test_box_agreement_counts_each_box_once() -> None:
    ref = [Box(0, 0, 10, 10), Box(20, 0, 30, 10)]
    # two candidates on the first box, none on the second, one stray
    cand = [Box(0, 0, 10, 10), Box(1, 0, 11, 10), Box(50, 50, 60, 60)]
    assert box_agreement(ref, cand) == (0.5, 1 / 3)
    assert box_agreement([], []) == (1.0, 1.0)


def test_gaps_match_checks_count_row_and_position() -> None:
    gap = Gap(row=1, x1=100, y1=0, x2=200, y2=50, width_ratio=1.5)
    assert gaps_match([gap], [(1, 110, 190)])
    assert not gaps_match([gap], [(0, 100, 200)])  # wrong row
    assert not gaps_match([gap], [(1, 130, 200)])  # off by 30 px
    assert not gaps_match([gap], [])


def test_greedy_match_pairs_each_hole_once() -> None:
    holes = [Box(0, 0, 100, 50), Box(200, 0, 300, 50)]
    found = [Box(10, 5, 105, 50), Box(0, 0, 400, 50), Box(500, 0, 600, 50)]
    # the shelf-wide gap overlaps both holes but too loosely (IoU 0.25) to count
    assert greedy_match(holes, found, 0.3) == [(0, 0)]
    assert greedy_match([], found, 0.3) == []
