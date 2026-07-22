"""Evaluate the vision pipeline's geometry against the synthetic dataset.

Usage:
    python Vision/perception/train.py

Requires Vision/synthetic_data/ground_truth.json, produced by running
DigitalTwin/scripts/render_vision_dataset.py inside Blender first.

Named train.py to match AI/localization/train.py's role as the track's entry point,
though nothing is trained here — the detector is a stock pretrained YOLOv8 and this
script only measures the geometry chain (see evaluate.py / report.py docstrings).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from perception import evaluate
from perception import report
from perception.data import load_ground_truth
from perception.seat_mapping import load_seats

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def main():
    ground_truth = load_ground_truth()
    seats = load_seats()
    calibration = ground_truth["camera_calibration"]

    homography_matrix = evaluate.fit_calibration_homography(ground_truth)
    coverage = evaluate.coverage_metrics(ground_truth)
    results = evaluate.evaluate_all_scenes(ground_truth, homography_matrix, seats)
    overall = results["overall"]

    print(f"Calibration points: {len(calibration['correspondences'])}")
    print(
        f"Frame coverage:     {coverage['in_frame_seats']}/{coverage['total_seats']} seats "
        f"({coverage['frame_coverage_rate'] * 100:.1f}%) - reported, not asserted: this is "
        "a fixed-camera limitation, not a software one.\n"
    )
    print("Geometry accuracy (ground-truth pixels, no detection):")
    print(f"  people scored:  {overall['n']}")
    print(f"  correct seat:   {overall['correct_seat_rate'] * 100:.1f}%")
    print(f"  median error:   {overall['median_position_error_m']:.3f} m")
    print(f"  mean error:     {overall['mean_position_error_m']:.3f} m")
    print(f"  single / multi: {results['single']['correct_seat_rate'] * 100:.1f}% / "
          f"{results['multi']['correct_seat_rate'] * 100:.1f}%\n")

    report.save_metrics_json(
        results, coverage, calibration, os.path.join(RESULTS_DIR, "metrics.json")
    )
    report.save_csv(results["per_person"], os.path.join(RESULTS_DIR, "per_person_results.csv"))
    report.generate_text_report(
        results, coverage, calibration, os.path.join(RESULTS_DIR, "report.txt")
    )
    report.plot_seat_coverage_map(
        ground_truth["seat_visibility"], seats, calibration["position"],
        os.path.join(RESULTS_DIR, "seat_coverage_map.png"),
    )
    report.plot_seat_recovery_map(
        results["per_person"], seats, os.path.join(RESULTS_DIR, "seat_recovery_map.png")
    )
    report.plot_position_error_histogram(
        results["per_person"], os.path.join(RESULTS_DIR, "position_error_histogram.png")
    )
    print(f"Saved results package to {RESULTS_DIR}")

    assert overall["correct_seat_rate"] >= report.TARGET_GEOMETRY_SEAT_ACCURACY, (
        f"geometry-only seat accuracy {overall['correct_seat_rate']:.1%} is below the "
        f"{report.TARGET_GEOMETRY_SEAT_ACCURACY:.0%} proxy target. NOTE: this is NOT "
        "CLAUDE.md's vision seat accuracy metric — that one also includes detection error."
    )
    print("\nGeometry-only accuracy target met (detection error NOT included).")


if __name__ == "__main__":
    main()
