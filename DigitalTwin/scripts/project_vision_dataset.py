"""
Guardian AI – Synthetic Vision Dataset (projection only, no Blender)
Phase 4: Digital Twin -> Vision AI synthetic data

What this does:
Produces the same ground_truth.json as render_vision_dataset.py — camera calibration
correspondences, per-seat visibility, and each placeholder person's exact pixel bounding
box — using plain pinhole-camera math instead of Blender.

Why both exist: the vision evaluation is geometry-only (it never reads a pixel), so the
rendered images aren't needed to produce metrics. This script runs anywhere Python does,
which means it can be tested and verified; render_vision_dataset.py additionally produces
actual PNGs, for when a real detector needs real imagery.

How to run:
    python DigitalTwin/scripts/project_vision_dataset.py

Requirements:
    pip install -r DigitalTwin/scripts/requirements.txt
"""

import json
import math
import os
import random

import numpy as np

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))       # DigitalTwin/scripts
REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))      # repo root

SEAT_MAP_PATH = os.path.join(REPO_ROOT, "Shared", "seat_map.json")
SYNTHETIC_DATA_DIR = os.path.join(REPO_ROOT, "Vision", "synthetic_data")
GROUND_TRUTH_PATH = os.path.join(SYNTHETIC_DATA_DIR, "ground_truth.json")
VISION_SIM_DIR = os.path.join(REPO_ROOT, "DigitalTwin", "vision_simulation")
REPORT_PATH = os.path.join(VISION_SIM_DIR, "generation_report.txt")

RESOLUTION_X = 1920
RESOLUTION_Y = 1080

# seat_map.json records only "fov_degrees": 110 with no horizontal/vertical/diagonal
# qualifier — treated as HORIZONTAL, the usual convention for security-camera specs.
FOV_DEGREES = 110

# No camera pitch/tilt is recorded anywhere — swept and measured instead of guessed.
PITCH_CANDIDATES_DEG = list(range(5, 61, 5))

# Placeholder person dimensions (meters), matching render_vision_dataset.py.
TORSO_RADIUS = 0.16
TORSO_HEIGHT = 0.55
HEAD_RADIUS = 0.11

# The homography is calibrated on the plane where the measured points actually lie.
# A person's bounding box bottom edge — the "foot point" the pipeline uses — sits on the
# bench surface (seat z), NOT the floor. Calibrating on the floor instead would map every
# bench-height point along its view ray down to z=0, pushing it away from the camera by
# ~20% of its distance (metres of error for the back rows).
CALIBRATION_PLANE_Z = 0.45

CALIB_X_STEPS = [0.5, 3.0, 6.1, 9.2, 11.7]
CALIB_Y_STEPS = [3.0, 6.0, 9.0, 12.0, 14.5]

N_MULTI_SCENES = 18
MULTI_MIN_SEATS = 3
MULTI_MAX_SEATS = 12

SEED = 42

# ─────────────────────────────────────────────
# CAMERA MODEL
# ─────────────────────────────────────────────

def camera_basis(pitch_down_deg):
    """World-space (right, up, forward) axes for a camera rotated `pitch_down_deg` below
    horizontal, looking toward +Y. Matches Blender's convention (camera looks down local
    -Z with +Y up, rotated about world X), so both generators agree."""
    angle = math.radians(90 - pitch_down_deg)
    right = np.array([1.0, 0.0, 0.0])
    up = np.array([0.0, math.cos(angle), math.sin(angle)])
    forward = np.array([0.0, math.sin(angle), -math.cos(angle)])
    return right, up, forward


def fov_tangents(fov_degrees=FOV_DEGREES, res_x=RESOLUTION_X, res_y=RESOLUTION_Y):
    """Half-angle tangents for a horizontal-fit sensor."""
    tan_half_x = math.tan(math.radians(fov_degrees) / 2)
    tan_half_y = tan_half_x * (res_y / res_x)
    return tan_half_x, tan_half_y


def project_point(point, cam_pos, basis, tangents):
    """Project a world point to normalized view coordinates.

    Returns (u, v, depth): u/v are 0..1 across the frame with v=0 at the BOTTOM (same
    convention as Blender's world_to_camera_view), depth is metres in front of the
    camera. Points at or behind the camera plane come back as NaN so they fail the
    in-frame test.
    """
    right, up, forward = basis
    tan_half_x, tan_half_y = tangents
    rel = np.asarray(point, dtype=float) - np.asarray(cam_pos, dtype=float)

    depth = float(rel @ forward)
    if depth <= 1e-9:
        return float("nan"), float("nan"), depth

    u = 0.5 + (float(rel @ right) / depth) / (2 * tan_half_x)
    v = 0.5 + (float(rel @ up) / depth) / (2 * tan_half_y)
    return u, v, depth


def to_pixel(u, v, res_x=RESOLUTION_X, res_y=RESOLUTION_Y):
    """Normalized view coords -> image pixels. v=0 is the bottom of the frame but pixel
    row 0 is the top, hence the flip."""
    return u * res_x, (1.0 - v) * res_y


def is_in_frame(u, v, depth):
    return depth > 0 and 0.0 <= u <= 1.0 and 0.0 <= v <= 1.0

# ─────────────────────────────────────────────
# PLACEHOLDER PEOPLE
# ─────────────────────────────────────────────

def person_corners(x, y, seat_z):
    """The 8 corners of a seated placeholder's bounding volume (cylinder torso rising
    from the bench surface, sphere head on top)."""
    radius = max(TORSO_RADIUS, HEAD_RADIUS)
    z_min = seat_z
    z_max = seat_z + TORSO_HEIGHT + 2 * HEAD_RADIUS
    return [
        (x + dx * radius, y + dy * radius, z)
        for dx in (-1, 1)
        for dy in (-1, 1)
        for z in (z_min, z_max)
    ]


def person_bbox_px(x, y, seat_z, cam_pos, basis, tangents):
    """Pixel bounding box for a placeholder at a seat. Returns (bbox_or_None, in_frame)
    where bbox is [x1, y1, x2, y2] with y1 the head edge and y2 the feet edge."""
    projected = []
    for corner in person_corners(x, y, seat_z):
        u, v, depth = project_point(corner, cam_pos, basis, tangents)
        if depth > 0:
            projected.append(to_pixel(u, v))

    if not projected:
        return None, False

    xs = [p[0] for p in projected]
    ys = [p[1] for p in projected]
    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)

    in_frame = x2 > 0 and x1 < RESOLUTION_X and y2 > 0 and y1 < RESOLUTION_Y
    bbox = [
        max(0.0, x1), max(0.0, y1),
        min(float(RESOLUTION_X), x2), min(float(RESOLUTION_Y), y2),
    ]
    return bbox, in_frame

# ─────────────────────────────────────────────
# CAMERA PITCH + CALIBRATION
# ─────────────────────────────────────────────

def select_camera_pitch(seats, cam_pos, tangents):
    """Pick the downward pitch that puts the most seats in frame. No pitch is recorded in
    seat_map.json, so it's measured rather than assumed — same approach
    node_placement_optimizer.py uses to choose the RF node layout."""
    per_pitch = []
    best_pitch, best_count = PITCH_CANDIDATES_DEG[0], -1
    for pitch in PITCH_CANDIDATES_DEG:
        basis = camera_basis(pitch)
        count = 0
        for seat in seats:
            u, v, depth = project_point(
                (seat["x"], seat["y"], seat["z"]), cam_pos, basis, tangents
            )
            if is_in_frame(u, v, depth):
                count += 1
        per_pitch.append((pitch, count))
        if count > best_count:
            best_pitch, best_count = pitch, count
    return best_pitch, best_count, per_pitch


def build_calibration(cam_pos, basis, tangents):
    """Project a grid of points on the bench plane and keep the in-frame ones as
    pixel<->world correspondences for homography fitting."""
    correspondences = []
    for wx in CALIB_X_STEPS:
        for wy in CALIB_Y_STEPS:
            u, v, depth = project_point(
                (wx, wy, CALIBRATION_PLANE_Z), cam_pos, basis, tangents
            )
            if not is_in_frame(u, v, depth):
                continue
            px, py = to_pixel(u, v)
            correspondences.append({"pixel": [px, py], "world": [wx, wy]})
    return correspondences

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def load_seat_map(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    print(f"Loaded seat_map.json - {data['total_seats']} seats")
    return data


def build_scenes(seats, cam_pos, basis, tangents):
    """One scene per seat (single occupancy), then N_MULTI_SCENES random multi-occupancy
    scenes. Scene shape matches render_vision_dataset.py so both feed the same evaluator."""
    seats_by_id = {s["seat_id"]: s for s in seats}
    scenes = []

    for seat in seats:
        bbox, in_frame = person_bbox_px(
            seat["x"], seat["y"], seat["z"], cam_pos, basis, tangents
        )
        scenes.append({
            "scene_id": f"single_{seat['seat_id']}",
            "type": "single",
            "image_path": None,  # projection-only run; no PNG rendered
            "occupied_seats": [seat["seat_id"]],
            "people": [{
                "seat_id": seat["seat_id"],
                "true_x": seat["x"], "true_y": seat["y"], "true_z": seat["z"],
                "bbox_px": bbox, "in_frame": in_frame,
            }],
        })

    all_ids = [s["seat_id"] for s in seats]
    for i in range(N_MULTI_SCENES):
        chosen = random.sample(all_ids, random.randint(MULTI_MIN_SEATS, MULTI_MAX_SEATS))
        people = []
        for seat_id in chosen:
            seat = seats_by_id[seat_id]
            bbox, in_frame = person_bbox_px(
                seat["x"], seat["y"], seat["z"], cam_pos, basis, tangents
            )
            people.append({
                "seat_id": seat_id,
                "true_x": seat["x"], "true_y": seat["y"], "true_z": seat["z"],
                "bbox_px": bbox, "in_frame": in_frame,
            })
        scenes.append({
            "scene_id": f"multi_{i + 1:02d}",
            "type": "multi",
            "image_path": None,
            "occupied_seats": chosen,
            "people": people,
        })
    return scenes


def write_report(seats, best_pitch, best_count, per_pitch, correspondences, n_scenes):
    os.makedirs(VISION_SIM_DIR, exist_ok=True)
    lines = [
        "Guardian AI - Vision Dataset Generation Report (projection only)",
        "=" * 60,
        "",
        "Generator: DigitalTwin/scripts/project_vision_dataset.py (no Blender, no images)",
        f"Camera FOV (horizontal): {FOV_DEGREES} deg",
        f"Resolution: {RESOLUTION_X}x{RESOLUTION_Y}",
        f"Calibration plane z: {CALIBRATION_PLANE_Z} m (bench surface, where feet sit)",
        f"Scenes: {n_scenes} ({len(seats)} single + {N_MULTI_SCENES} multi)",
        f"Calibration points in frame: {len(correspondences)}",
        "",
        f"Camera pitch sweep (downward degrees -> seats in frame of {len(seats)}):",
    ]
    for pitch, count in per_pitch:
        marker = "  <-- chosen" if pitch == best_pitch else ""
        lines.append(f"  {pitch:>3} deg: {count:>3} seats{marker}")
    lines += [
        "",
        f"Chosen pitch: {best_pitch} deg down ({best_count}/{len(seats)} seats in frame)",
        "",
        "Seats out of frame are a real limitation of this single fixed camera at its",
        "documented position - the front rows sit almost directly beneath it. Measured",
        "here, not assumed: seat_map.json's 'covers all 99 seats' is optimistic.",
    ]
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"generation_report.txt -> {REPORT_PATH}")


def main():
    print("\nGuardian AI Vision Dataset Projector starting...\n")
    random.seed(SEED)

    seat_map_data = load_seat_map(SEAT_MAP_PATH)
    seats = seat_map_data["seats"]
    cam_spec = seat_map_data["cameras"][0]
    cam_pos = (cam_spec["position"]["x"], cam_spec["position"]["y"], cam_spec["position"]["z"])

    tangents = fov_tangents()
    best_pitch, best_count, per_pitch = select_camera_pitch(seats, cam_pos, tangents)
    basis = camera_basis(best_pitch)
    print(f"Camera pitch {best_pitch} deg down - {best_count}/{len(seats)} seats in frame")

    seat_visibility = {}
    for seat in seats:
        u, v, depth = project_point(
            (seat["x"], seat["y"], seat["z"]), cam_pos, basis, tangents
        )
        seat_visibility[seat["seat_id"]] = {"in_frame": is_in_frame(u, v, depth)}

    correspondences = build_calibration(cam_pos, basis, tangents)
    print(f"{len(correspondences)} in-frame calibration points")

    scenes = build_scenes(seats, cam_pos, basis, tangents)

    ground_truth = {
        "project": "Guardian AI",
        "description": "Synthetic vision dataset (projection only - no rendered images)",
        "images_rendered": False,
        "camera_calibration": {
            "camera_id": cam_spec["camera_id"],
            "position": cam_spec["position"],
            "fov_degrees_horizontal": FOV_DEGREES,
            "pitch_down_degrees": best_pitch,
            "pitch_selection": "swept 5..60deg / 5deg steps; maximized in-frame seat count",
            "calibration_plane_z": CALIBRATION_PLANE_Z,
            "resolution": [RESOLUTION_X, RESOLUTION_Y],
            "correspondences": correspondences,
        },
        "seat_visibility": seat_visibility,
        "scenes": scenes,
    }
    os.makedirs(SYNTHETIC_DATA_DIR, exist_ok=True)
    with open(GROUND_TRUTH_PATH, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)
    print(f"ground_truth.json -> {GROUND_TRUTH_PATH}")

    write_report(seats, best_pitch, best_count, per_pitch, correspondences, len(scenes))
    print("\nDone. Next step: python Vision/perception/train.py")


if __name__ == "__main__":
    main()
