import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localization.data import FEATURE_COLS, load_seat_map, load_wide


def test_pivot_shape_and_columns():
    seat_map = load_seat_map()
    wide = load_wide(seat_map=seat_map)

    assert len(wide) == 99 * 100
    for col in FEATURE_COLS + ["seat_id", "sample_idx", "true_x", "true_y", "row", "section"]:
        assert col in wide.columns


def test_no_missing_values():
    wide = load_wide()
    assert not wide[FEATURE_COLS].isna().any().any()


def test_node_column_order_is_stable():
    wide = load_wide()
    assert list(wide[FEATURE_COLS].columns) == ["N1", "N2", "N3", "N4"]


def test_true_xy_matches_seat_map():
    seat_map = load_seat_map()
    wide = load_wide(seat_map=seat_map)
    row = wide.iloc[0]
    expected = seat_map[row["seat_id"]]
    assert row["true_x"] == expected["x"]
    assert row["true_y"] == expected["y"]
