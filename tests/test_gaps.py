import pytest

from lacuna.vision import Box, analyze_shelf
from lacuna.vision.gaps import group_rows
from tests.conftest import FULL_ROW, GAPPY_ROW, shelf_row


def test_no_boxes_means_unknown_occupancy() -> None:
    result = analyze_shelf([])
    assert result.gaps == []
    assert result.occupancy is None


def test_full_row_has_no_gaps() -> None:
    result = analyze_shelf(shelf_row(0, FULL_ROW))
    assert result.gaps == []
    assert result.occupancy == 1.0


def test_missing_products_in_middle() -> None:
    result = analyze_shelf(shelf_row(0, GAPPY_ROW) + shelf_row(200, FULL_ROW))
    assert len(result.gaps) == 1
    gap = result.gaps[0]
    assert gap.row == 0
    # slot 3 ends at 240, slot 6 starts at 370
    assert (gap.x1, gap.x2) == (240, 370)
    assert gap.width_ratio == pytest.approx(2.6)
    assert result.occupancy is not None and result.occupancy < 1.0


def test_gap_at_end_of_row_uses_shelf_span() -> None:
    short_row = FULL_ROW[:6]  # last 4 slots empty, span set by the full row below
    result = analyze_shelf(shelf_row(0, short_row) + shelf_row(200, FULL_ROW))
    assert [(g.row, g.x1, g.x2) for g in result.gaps] == [(0, 360, 600)]


def test_small_spacing_is_not_a_gap() -> None:
    # 60 px slots with 50 px products: 10 px spacing everywhere
    xs = [*FULL_ROW[:5], FULL_ROW[5] + 20, *FULL_ROW[6:]]  # one product nudged: 30 px hole
    assert analyze_shelf(shelf_row(0, xs)).gaps == []


def test_single_missing_product_is_a_gap() -> None:
    xs = [x for i, x in enumerate(FULL_ROW) if i != 4]  # one slot missing: 70 px hole
    (gap,) = analyze_shelf(shelf_row(0, xs)).gaps
    assert gap.width_ratio == pytest.approx(1.4)


def test_threshold_is_configurable() -> None:
    xs = [x for i, x in enumerate(FULL_ROW) if i != 4]
    assert analyze_shelf(shelf_row(0, xs), min_gap_ratio=1.5).gaps == []
    assert len(analyze_shelf(shelf_row(0, xs), min_gap_ratio=1.2).gaps) == 1


def test_row_cut_off_by_the_frame_is_skipped() -> None:
    # a sliver of the next shelf down, clipped by the bottom of a 400 px photo
    sliver = [Box(x, 380, x + 50, 400) for x in (0, 60, 500, 560)]
    boxes = [*shelf_row(50, FULL_ROW), *sliver]
    assert len(analyze_shelf(boxes).gaps) == 1  # without the height, it looks like a hole
    result = analyze_shelf(boxes, image_height=400)
    assert result.gaps == []
    assert result.occupancy == 1.0


def test_row_near_but_inside_the_frame_still_counts() -> None:
    boxes = shelf_row(10, GAPPY_ROW) + shelf_row(250, FULL_ROW)  # 10 px from the top and bottom
    assert len(analyze_shelf(boxes, image_height=380).gaps) == 1


def test_lone_box_rows_are_skipped() -> None:
    boxes = [*shelf_row(0, FULL_ROW), Box(500, 300, 550, 420)]
    result = analyze_shelf(boxes)
    assert len(result.rows) == 2
    assert result.gaps == []


def test_rows_group_mixed_heights() -> None:
    # tall and short products on the same shelf share a bottom edge
    boxes = [Box(0, 0, 50, 120), Box(60, 40, 110, 120), Box(120, 10, 170, 120)]
    boxes += [Box(0, 200, 50, 320), Box(60, 210, 110, 320)]
    rows = group_rows(boxes)
    assert [len(r) for r in rows] == [3, 2]
    assert [b.x1 for b in rows[0]] == [0, 60, 120]
