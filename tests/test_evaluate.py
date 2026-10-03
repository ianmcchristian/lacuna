from lacuna.vision import Box, Gap
from lacuna.vision.evaluate import box_agreement, gaps_match, iou


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
