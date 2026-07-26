"""Generate the results package for the vision geometry evaluation.

Mirrors AI/localization/report.py's role: metrics.json, a text report, CSV, and figures.

IMPORTANT framing: every number here is GEOMETRY-ONLY. It measures the
homography + seat-mapping chain given perfect (ground-truth) pixel input — it does NOT
include any detection error, because detection can't be exercised against the
placeholder people (see evaluate.py's docstring). Do not report these as CLAUDE.md's
">90% vision seat accuracy" without that caveat.
"""

import csv
import json
import os

import matplotlib

matplotlib.use("Agg")  # no GUI backend — figures are written to disk only
import matplotlib.pyplot as plt

# Proxy for CLAUDE.md's frozen ">90% vision seat accuracy" target. Asserting this checks
# only whether the geometry alone clears the bar with perfect detection input; the real
# target additionally requires a detector that works on real footage.
TARGET_GEOMETRY_SEAT_ACCURACY = 0.90


def save_metrics_json(results, coverage, calibration, out_path):
    """Write the headline metrics (minus the per-person detail) as JSON."""
    _ensure_dir(out_path)
    payload = {
        "evaluation_type": "geometry_only",
        "note": (
            "Ground-truth pixel input, no object detection. Not directly comparable to "
            "CLAUDE.md's vision seat accuracy target, which includes detection error."
        ),
        "camera_pitch_down_degrees": calibration.get("pitch_down_degrees"),
        "calibration_points": len(calibration.get("correspondences", [])),
        "coverage": coverage,
        "overall": results["overall"],
        "single": results["single"],
        "multi": results["multi"],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def save_csv(per_person, out_path):
    """Write the per-person results table."""
    _ensure_dir(out_path)
    fields = [
        "scene_id", "scene_type", "true_seat", "predicted_seat", "correct",
        "position_error_m",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(per_person)


def generate_text_report(results, coverage, calibration, out_path):
    _ensure_dir(out_path)
    overall = results["overall"]
    lines = [
        "Guardian AI – Vision Geometry Evaluation Report",
        "=" * 50,
        "",
        "Evaluation type:     GEOMETRY ONLY (ground-truth pixel input, no detection)",
        f"Camera pitch:        {calibration.get('pitch_down_degrees')} deg down",
        f"Calibration points:  {len(calibration.get('correspondences', []))}",
        "",
        "Frame coverage (a fixed-camera limitation, reported not asserted):",
        f"  Seats in frame:    {coverage['in_frame_seats']}/{coverage['total_seats']}"
        f" ({coverage['frame_coverage_rate'] * 100:.1f}%)",
        "",
        "Geometry accuracy (over in-frame people):",
        f"  People scored:     {overall['n']}",
        f"  Correct seat:      {overall['correct_seat_rate'] * 100:.1f}%",
        f"  Median error:      {overall['median_position_error_m']:.3f} m",
        f"  Mean error:        {overall['mean_position_error_m']:.3f} m",
        f"  Max error:         {overall['max_position_error_m']:.3f} m",
        "",
        "By scene type:",
        f"  single: n={results['single']['n']}, "
        f"correct={results['single']['correct_seat_rate'] * 100:.1f}%, "
        f"median={results['single']['median_position_error_m']:.3f} m",
        f"  multi:  n={results['multi']['n']}, "
        f"correct={results['multi']['correct_seat_rate'] * 100:.1f}%, "
        f"median={results['multi']['median_position_error_m']:.3f} m",
        "",
        "Position error is non-zero by design: the homography is an approximate planar",
        "fit, and placeholder feet sit at bench height (0.45 m) while the calibration",
        "plane is the true floor (0 m) — an expected parallax, not an error in the code.",
    ]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def plot_seat_coverage_map(seat_visibility, seats, camera_position, out_path):
    """All seats plotted at their hall (x, y), colored by whether the camera can see
    them — the figure that shows which seats are a blind spot."""
    _ensure_dir(out_path)
    fig, ax = plt.subplots(figsize=(8, 10))
    for seat in seats:
        visible = seat_visibility.get(seat["seat_id"], {}).get("in_frame", False)
        ax.scatter(
            seat["x"], seat["y"],
            c="tab:green" if visible else "tab:red",
            s=40, edgecolors="black", linewidths=0.3,
        )
    ax.scatter(
        camera_position["x"], camera_position["y"],
        marker="*", s=300, c="tab:blue", edgecolors="black", label="camera",
    )
    in_frame = sum(1 for v in seat_visibility.values() if v["in_frame"])
    ax.set_title(f"Seat coverage — {in_frame}/{len(seat_visibility)} seats in frame\n"
                 "(green = visible, red = out of frame)")
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_seat_recovery_map(per_person, seats, out_path):
    """Seats colored by whether the geometry recovered them correctly."""
    _ensure_dir(out_path)
    seat_xy = {s["seat_id"]: (s["x"], s["y"]) for s in seats}
    correct_by_seat = {}
    for r in per_person:
        correct_by_seat.setdefault(r["true_seat"], []).append(r["correct"])

    fig, ax = plt.subplots(figsize=(8, 10))
    for seat_id, flags in correct_by_seat.items():
        if seat_id not in seat_xy:
            continue
        x, y = seat_xy[seat_id]
        rate = sum(flags) / len(flags)
        ax.scatter(x, y, c=[[1 - rate, rate, 0.2]], s=40, edgecolors="black", linewidths=0.3)
    ax.set_title("Seat recovery (green = always correct, red = never)")
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_position_error_histogram(per_person, out_path):
    _ensure_dir(out_path)
    errors = [r["position_error_m"] for r in per_person]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(errors, bins=30, color="tab:blue", edgecolor="black")
    ax.set_title("Position error (ground-truth pixels -> hall coordinates)")
    ax.set_xlabel("error (m)")
    ax.set_ylabel("people")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def _ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
