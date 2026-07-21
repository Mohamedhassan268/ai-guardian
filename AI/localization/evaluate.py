"""Train/test split and success-metric evaluation for localization models.

Metrics mirror the frozen targets in CLAUDE.md / status.md:
  - localization median error < 2 m
  - correct-bench rate > 80%   (bench == matching row + section)
  - correct-seat rate          (informational; exact seat_id match)
"""

import numpy as np


def split_train_test(wide_df, test_size=0.2, seed=0):
    """Stratified split by seat_id so every seat's fingerprint is learned from train only."""
    rng = np.random.default_rng(seed)
    train_parts, test_parts = [], []
    for _, group in wide_df.groupby("seat_id"):
        idx = rng.permutation(len(group))
        n_test = max(1, int(round(len(group) * test_size)))
        test_idx, train_idx = idx[:n_test], idx[n_test:]
        test_parts.append(group.iloc[test_idx])
        train_parts.append(group.iloc[train_idx])
    train_df = _concat(train_parts).reset_index(drop=True)
    test_df = _concat(test_parts).reset_index(drop=True)
    return train_df, test_df


def _concat(parts):
    import pandas as pd

    return pd.concat(parts, ignore_index=True)


def evaluate(model, test_df, feature_cols):
    """Compute median error (m), correct-bench rate, correct-seat rate for a fitted model."""
    X = test_df[feature_cols].to_numpy()
    pred_xy = np.asarray(model.predict_xy(X))
    pred_seat = model.predict_seat(X)

    true_xy = test_df[["true_x", "true_y"]].to_numpy()
    errors = np.linalg.norm(pred_xy - true_xy, axis=1)

    pred_row = [s.split("-")[0] for s in pred_seat]
    true_row = test_df["seat_id"].str.split("-").str[0]
    pred_section = [s.split("-")[1][0] for s in pred_seat]  # 'L'/'C'/'R' prefix
    true_section = test_df["section"].str[0]

    correct_bench = [
        (pr == tr) and (ps == ts)
        for pr, tr, ps, ts in zip(pred_row, true_row, pred_section, true_section)
    ]
    correct_seat = [ps == ts for ps, ts in zip(pred_seat, test_df["seat_id"])]

    return {
        "median_error_m": float(np.median(errors)),
        "mean_error_m": float(np.mean(errors)),
        "max_error_m": float(np.max(errors)),
        "correct_bench_rate": float(np.mean(correct_bench)),
        "correct_seat_rate": float(np.mean(correct_seat)),
        "n_test": len(test_df),
    }
