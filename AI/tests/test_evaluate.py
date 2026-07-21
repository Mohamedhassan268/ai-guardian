import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localization.evaluate import evaluate, split_train_test


class _StubModel:
    """Predicts true position + a fixed offset, for deterministic metric checks.

    Note: evaluate() passes RSSI feature columns to predict_xy, never the true
    position — so the stub is given true_xy directly rather than deriving it from X.
    """

    def __init__(self, true_xy, offset=(0.0, 0.0), seat_guess=None):
        self.true_xy = true_xy
        self.offset = offset
        self.seat_guess = seat_guess

    def predict_xy(self, X):
        return [[x + self.offset[0], y + self.offset[1]] for x, y in self.true_xy]

    def predict_seat(self, X):
        return [self.seat_guess] * len(X)


def test_evaluate_perfect_model_has_zero_error_and_full_bench_rate():
    test_df = pd.DataFrame(
        {
            "N1": [-50, -55],
            "N2": [-70, -60],
            "true_x": [1.0, 2.0],
            "true_y": [1.0, 2.0],
            "seat_id": ["R01-L01", "R02-C01"],
            "section": ["Left", "Center"],
        }
    )

    class PerfectModel:
        def predict_xy(self, X):
            return test_df[["true_x", "true_y"]].to_numpy()

        def predict_seat(self, X):
            return list(test_df["seat_id"])

    metrics = evaluate(PerfectModel(), test_df, ["N1", "N2"])
    assert metrics["median_error_m"] == 0.0
    assert metrics["correct_bench_rate"] == 1.0
    assert metrics["correct_seat_rate"] == 1.0


def test_evaluate_known_offset_median_error():
    test_df = pd.DataFrame(
        {
            "N1": [-50, -55],
            "N2": [-70, -60],
            "true_x": [0.0, 0.0],
            "true_y": [0.0, 0.0],
            "seat_id": ["R01-L01", "R02-C01"],
            "section": ["Left", "Center"],
        }
    )
    model = _StubModel(true_xy=test_df[["true_x", "true_y"]].to_numpy(), offset=(3.0, 4.0), seat_guess="R99-C99")
    metrics = evaluate(model, test_df, ["N1", "N2"])

    assert metrics["median_error_m"] == 5.0  # 3-4-5 triangle
    assert metrics["correct_bench_rate"] == 0.0


def test_split_train_test_keeps_all_seats_in_train():
    wide = pd.DataFrame(
        {
            "seat_id": ["R01-L01"] * 10 + ["R02-C01"] * 10,
            "N1": range(20),
        }
    )
    train_df, test_df = split_train_test(wide, test_size=0.2, seed=0)

    assert set(train_df["seat_id"].unique()) == {"R01-L01", "R02-C01"}
    assert len(train_df) + len(test_df) == len(wide)
