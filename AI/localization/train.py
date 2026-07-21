"""Train and evaluate localization models on the simulated RSSI dataset.

Usage:
    python AI/localization/train.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localization.data import DATA_CSV, FEATURE_COLS, load_rf_nodes, load_seat_map, load_wide
from localization.evaluate import evaluate, split_train_test
from localization.events import make_position_estimate
from localization.models import FingerprintKNN, RegressorKNN
from localization import report

FINGERPRINT_JSON = os.path.join(
    os.path.dirname(__file__), "..", "training_data", "rssi_fingerprint.json"
)
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")


WINDOW_SIZE = 40  # consecutive raw samples averaged per localization observation.
# A single instantaneous RSSI reading (noise std 3 dB) is not reliably separable from
# a neighboring seat (~1-2 dB apart) — see AI/localization/data.py:load_wide docstring.
# Real deployments always integrate multiple readings before localizing; the sweep in
# results/window_size_sweep.png shows 40 as the accuracy sweet spot (K=50 dips again
# from too few aggregated queries).


def main():
    seat_map = load_seat_map()
    wide = load_wide(seat_map=seat_map, window_size=WINDOW_SIZE)
    train_df, test_df = split_train_test(wide, test_size=0.2, seed=0)

    fingerprint_model = FingerprintKNN.from_fingerprint_file(FINGERPRINT_JSON, seat_map)
    regressor_model = RegressorKNN(seat_map, n_neighbors=5).fit(
        train_df[FEATURE_COLS].to_numpy(), train_df[["true_x", "true_y"]].to_numpy()
    )

    print(f"Test set: {len(test_df)} samples\n")

    results = {}
    for name, model in [("FingerprintKNN", fingerprint_model), ("RegressorKNN", regressor_model)]:
        metrics = evaluate(model, test_df, FEATURE_COLS)
        results[name] = (model, metrics)
        print(f"{name}:")
        print(f"  median error:      {metrics['median_error_m']:.3f} m")
        print(f"  mean error:        {metrics['mean_error_m']:.3f} m")
        print(f"  max error:         {metrics['max_error_m']:.3f} m")
        print(f"  correct-bench:     {metrics['correct_bench_rate'] * 100:.1f}%")
        print(f"  correct-seat:      {metrics['correct_seat_rate'] * 100:.1f}%")
        print()

    best_name = min(results, key=lambda n: results[n][1]["median_error_m"])
    best_model, best_metrics = results[best_name]
    print(f"Best model: {best_name}")

    report.save_metrics_json(
        {name: m for name, (_, m) in results.items()},
        window_size=WINDOW_SIZE,
        n_test=len(test_df),
        out_path=os.path.join(RESULTS_DIR, "metrics.json"),
    )
    report.plot_model_comparison(
        {name: m for name, (_, m) in results.items()},
        os.path.join(RESULTS_DIR, "model_comparison.png"),
    )
    seat_errors = report.per_seat_median_error(best_model, test_df, FEATURE_COLS)
    report.plot_error_heatmap(
        seat_errors, seat_map, os.path.join(RESULTS_DIR, "error_heatmap.png")
    )
    best_errors = report.all_errors(best_model, test_df, FEATURE_COLS)
    report.plot_error_histogram(
        best_errors, os.path.join(RESULTS_DIR, "error_histogram.png")
    )
    report.plot_error_cdf(best_errors, os.path.join(RESULTS_DIR, "error_cdf.png"))

    rf_nodes = load_rf_nodes()
    report.plot_predicted_vs_true(
        best_model,
        test_df,
        FEATURE_COLS,
        rf_nodes,
        os.path.join(RESULTS_DIR, "predicted_vs_true.png"),
    )
    report.plot_rssi_vs_distance(
        DATA_CSV, os.path.join(RESULTS_DIR, "rssi_vs_distance.png")
    )

    per_seat_df = report.per_seat_breakdown(best_model, test_df, FEATURE_COLS, seat_map)
    report.save_csv(per_seat_df, os.path.join(RESULTS_DIR, "per_seat_errors.csv"))

    print("Running window-size sweep (this evaluates several K values, a few seconds)...")
    sweep_df = report.window_size_sweep(
        DATA_CSV, seat_map, FINGERPRINT_JSON, window_sizes=[1, 5, 10, 15, 20, 25, 30, 40, 50]
    )
    report.save_csv(sweep_df, os.path.join(RESULTS_DIR, "window_size_sweep.csv"))
    report.plot_window_sweep(sweep_df, os.path.join(RESULTS_DIR, "window_size_sweep.png"))

    report.generate_text_report(
        {name: m for name, (_, m) in results.items()},
        best_name,
        WINDOW_SIZE,
        len(test_df),
        per_seat_df,
        os.path.join(RESULTS_DIR, "report.txt"),
    )
    report.save_model(best_model, os.path.join(RESULTS_DIR, "best_model.pkl"))

    print(f"\nSaved full results package (report, csvs, figures, model) to {RESULTS_DIR}")

    print("\nSample position_estimate events (best model, first 3 test rows):")
    sample = test_df.head(3)
    X_sample = sample[FEATURE_COLS].to_numpy()
    pred_xy = best_model.predict_xy(X_sample)
    pred_seat = best_model.predict_seat(X_sample)
    for (x, y), seat, (_, true_row) in zip(pred_xy, pred_seat, sample.iterrows()):
        true_xy = (true_row["true_x"], true_row["true_y"])
        error = ((x - true_xy[0]) ** 2 + (y - true_xy[1]) ** 2) ** 0.5
        confidence = max(0.0, 1.0 - error / 2.0)
        event = make_position_estimate(x, y, seat, error, confidence)
        print(event)

    assert best_metrics["median_error_m"] < 2.0, "median error target (<2m) not met"
    assert best_metrics["correct_bench_rate"] > 0.80, "correct-bench target (>80%) not met"
    print("\nBoth success-metric targets met.")


if __name__ == "__main__":
    main()
