"""Metrics report + figures for localization models.

Mirrors the DigitalTwin/rf_simulation output style (txt/json report + comparison
figures) so these results are directly comparable to the Phase 2 simulation outputs.
"""

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

TARGET_MEDIAN_ERROR_M = 2.0
TARGET_CORRECT_BENCH_RATE = 0.80


def per_seat_median_error(model, test_df, feature_cols):
    """Return {seat_id: median error in meters} over the test set."""
    X = test_df[feature_cols].to_numpy()
    pred_xy = np.asarray(model.predict_xy(X))
    true_xy = test_df[["true_x", "true_y"]].to_numpy()
    errors = np.linalg.norm(pred_xy - true_xy, axis=1)

    by_seat = {}
    for seat_id, err in zip(test_df["seat_id"], errors):
        by_seat.setdefault(seat_id, []).append(err)
    return {seat_id: float(np.median(errs)) for seat_id, errs in by_seat.items()}


def all_errors(model, test_df, feature_cols):
    """Return the raw per-observation error array (meters) for a fitted model."""
    X = test_df[feature_cols].to_numpy()
    pred_xy = np.asarray(model.predict_xy(X))
    true_xy = test_df[["true_x", "true_y"]].to_numpy()
    return np.linalg.norm(pred_xy - true_xy, axis=1)


def save_metrics_json(results, window_size, n_test, out_path):
    """results: {model_name: metrics_dict}."""
    payload = {
        "window_size": window_size,
        "n_test": n_test,
        "targets": {
            "median_error_m": TARGET_MEDIAN_ERROR_M,
            "correct_bench_rate": TARGET_CORRECT_BENCH_RATE,
        },
        "models": results,
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def plot_model_comparison(results, out_path):
    """Bar charts comparing median error and correct-bench rate across models."""
    names = list(results.keys())
    median_err = [results[n]["median_error_m"] for n in names]
    bench = [results[n]["correct_bench_rate"] * 100 for n in names]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    axes[0].bar(names, median_err, color="#4C72B0")
    axes[0].axhline(TARGET_MEDIAN_ERROR_M, color="red", linestyle="--", label="target < 2m")
    axes[0].set_ylabel("Median error (m)")
    axes[0].set_title("Localization error")
    axes[0].legend()

    axes[1].bar(names, bench, color="#55A868")
    axes[1].axhline(
        TARGET_CORRECT_BENCH_RATE * 100, color="red", linestyle="--", label="target > 80%"
    )
    axes[1].set_ylabel("Correct-bench rate (%)")
    axes[1].set_title("Correct-bench rate")
    axes[1].legend()

    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_error_heatmap(seat_errors, seat_map, out_path):
    """Per-seat median error plotted at each seat's hall coordinate."""
    xs = [seat_map[s]["x"] for s in seat_errors]
    ys = [seat_map[s]["y"] for s in seat_errors]
    errs = list(seat_errors.values())

    fig, ax = plt.subplots(figsize=(6, 8))
    sc = ax.scatter(xs, ys, c=errs, cmap="RdYlGn_r", s=110, edgecolors="black", vmin=0)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title("Per-seat median localization error (m) — best model")
    ax.invert_yaxis()  # y=0 at the front of the hall, matches the coordinate convention
    fig.colorbar(sc, ax=ax, label="Median error (m)")
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_error_histogram(errors, out_path):
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(errors, bins=20, color="#4C72B0", edgecolor="black")
    ax.axvline(TARGET_MEDIAN_ERROR_M, color="red", linestyle="--", label="target < 2m")
    ax.set_xlabel("Error (m)")
    ax.set_ylabel("Count")
    ax.set_title("Localization error distribution — best model")
    ax.legend()
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_error_cdf(errors, out_path):
    sorted_errors = np.sort(errors)
    cdf = np.arange(1, len(sorted_errors) + 1) / len(sorted_errors) * 100

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(sorted_errors, cdf, color="#4C72B0")
    ax.axvline(TARGET_MEDIAN_ERROR_M, color="red", linestyle="--", label="target < 2m")
    ax.set_xlabel("Error (m)")
    ax.set_ylabel("Cumulative % of predictions")
    ax.set_title("Cumulative error distribution — best model")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_predicted_vs_true(model, test_df, feature_cols, rf_nodes, out_path):
    """Spatial map: true seat position -> predicted position, connected by a line."""
    X = test_df[feature_cols].to_numpy()
    pred_xy = np.asarray(model.predict_xy(X))
    true_xy = test_df[["true_x", "true_y"]].to_numpy()

    fig, ax = plt.subplots(figsize=(6, 8))
    for (tx, ty), (px, py) in zip(true_xy, pred_xy):
        ax.plot([tx, px], [ty, py], color="gray", linewidth=0.6, alpha=0.6, zorder=1)
    ax.scatter(true_xy[:, 0], true_xy[:, 1], c="#4C72B0", s=40, label="true seat", zorder=2)
    ax.scatter(
        pred_xy[:, 0], pred_xy[:, 1], c="#DD8452", s=40, marker="x", label="predicted", zorder=2
    )
    ax.scatter(
        [n["x"] for n in rf_nodes],
        [n["y"] for n in rf_nodes],
        c="black",
        s=120,
        marker="^",
        label="RF node",
        zorder=3,
    )
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title("Predicted vs. true position — best model")
    ax.invert_yaxis()
    ax.legend(fontsize=8)
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_rssi_vs_distance(csv_path, out_path, sample_n=3000, seed=0):
    """Sanity-check figure: does simulated RSSI actually fall off with distance."""
    df = pd.read_csv(csv_path)
    if len(df) > sample_n:
        df = df.sample(sample_n, random_state=seed)

    fig, ax = plt.subplots(figsize=(7, 5))
    for node_id, group in df.groupby("node_id"):
        ax.scatter(group["distance_m"], group["rssi_dbm"], s=6, alpha=0.4, label=node_id)
    ax.set_xlabel("Distance to node (m)")
    ax.set_ylabel("RSSI (dBm)")
    ax.set_title("RSSI vs. distance (simulated, per node)")
    ax.legend(fontsize=7, markerscale=3)
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def per_seat_breakdown(model, test_df, feature_cols, seat_map):
    """Per-seat error/accuracy breakdown, worst seats first."""
    X = test_df[feature_cols].to_numpy()
    pred_xy = np.asarray(model.predict_xy(X))
    pred_seat = model.predict_seat(X)
    true_xy = test_df[["true_x", "true_y"]].to_numpy()
    errors = np.linalg.norm(pred_xy - true_xy, axis=1)

    rows = []
    for seat_id, idx in test_df.groupby("seat_id").groups.items():
        idx = list(idx)
        s = seat_map[seat_id]
        seat_errors = errors[idx]
        seat_pred = [pred_seat[i] for i in idx]
        correct_seat_rate = sum(1 for p in seat_pred if p == seat_id) / len(idx)
        rows.append(
            {
                "seat_id": seat_id,
                "x": s["x"],
                "y": s["y"],
                "row": s["row"],
                "section": s["section"],
                "n_test": len(idx),
                "median_error_m": float(np.median(seat_errors)),
                "mean_error_m": float(np.mean(seat_errors)),
                "correct_seat_rate": correct_seat_rate,
            }
        )
    return pd.DataFrame(rows).sort_values("median_error_m", ascending=False).reset_index(
        drop=True
    )


def save_csv(df, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_csv(out_path, index=False)


def window_size_sweep(csv_path, seat_map, fingerprint_json, window_sizes):
    """Diagnostic: how accuracy scales with the observation window size.

    Evaluates the fingerprint model against ALL windowed observations (not the
    held-out train/test split used elsewhere) purely to characterize the
    noise-vs-window trade-off found while building this pipeline — not a
    substitute for the headline train/test metrics.
    """
    from .data import FEATURE_COLS, load_wide
    from .evaluate import evaluate
    from .models import FingerprintKNN

    rows = []
    for k in window_sizes:
        wide = load_wide(csv_path, seat_map=seat_map, window_size=k)
        model = FingerprintKNN.from_fingerprint_file(fingerprint_json, seat_map)
        metrics = evaluate(model, wide, FEATURE_COLS)
        rows.append({"window_size": k, "n_queries": len(wide), **metrics})
    return pd.DataFrame(rows)


def plot_window_sweep(df, out_path):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    axes[0].plot(df["window_size"], df["median_error_m"], marker="o", color="#4C72B0")
    axes[0].axhline(TARGET_MEDIAN_ERROR_M, color="red", linestyle="--", label="target < 2m")
    axes[0].set_xlabel("Window size (samples)")
    axes[0].set_ylabel("Median error (m)")
    axes[0].set_title("Error vs. observation window")
    axes[0].legend()

    axes[1].plot(
        df["window_size"], df["correct_bench_rate"] * 100, marker="o", color="#55A868"
    )
    axes[1].axhline(
        TARGET_CORRECT_BENCH_RATE * 100, color="red", linestyle="--", label="target > 80%"
    )
    axes[1].set_xlabel("Window size (samples)")
    axes[1].set_ylabel("Correct-bench rate (%)")
    axes[1].set_title("Correct-bench vs. observation window")
    axes[1].legend()

    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def generate_text_report(results, best_name, window_size, n_test, per_seat_df, out_path):
    lines = [
        "Guardian AI - Localization Model Report",
        "=" * 50,
        "",
        f"Observation window size: {window_size} samples",
        f"Test set size: {n_test}",
        f"Targets: median error < {TARGET_MEDIAN_ERROR_M} m, "
        f"correct-bench > {TARGET_CORRECT_BENCH_RATE * 100:.0f}%",
        "",
        "Model comparison:",
    ]
    for name, m in results.items():
        lines += [
            f"  {name}:",
            f"    median error:   {m['median_error_m']:.3f} m",
            f"    mean error:     {m['mean_error_m']:.3f} m",
            f"    max error:      {m['max_error_m']:.3f} m",
            f"    correct-bench:  {m['correct_bench_rate'] * 100:.1f}%",
            f"    correct-seat:   {m['correct_seat_rate'] * 100:.1f}%",
        ]
    lines += ["", f"Best model: {best_name}", "", "Worst 5 seats by median error (best model):"]
    for _, row in per_seat_df.head(5).iterrows():
        lines.append(
            f"  {row['seat_id']} (row {row['row']}, {row['section']}): "
            f"{row['median_error_m']:.3f} m median error, "
            f"{row['correct_seat_rate'] * 100:.0f}% correct-seat over {row['n_test']} samples"
        )
    lines += [
        "",
        "Note: single-sample RSSI classification is unreliable (noise ~3dB vs ~1-2dB",
        "inter-seat separation) — see window_size_sweep.png. Results here use a",
        "windowed observation (see data.py:load_wide docstring).",
    ]

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def save_model(model, out_path):
    import pickle

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        pickle.dump(model, f)
