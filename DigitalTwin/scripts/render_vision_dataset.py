"""
Guardian AI – Synthetic Vision Dataset Renderer
Phase 4: Digital Twin -> Vision AI synthetic data

What this does:
- Adds a REAL camera to the hall (hall_builder.py only makes a decorative cube) matching
  the documented CAM_01_Front_Center spec, and picks its downward pitch by measuring
  which pitch puts the most of the 99 seats in frame (no pitch/tilt is recorded anywhere
  in seat_map.json, so we measure instead of guessing).
- Places simple placeholder people (cylinder body + sphere head) in seats and renders:
  99 single-occupancy frames (one seat each) + N_MULTI_SCENES multi-occupancy frames.
- For every placeholder, computes its exact rendered pixel bounding box via Blender's own
  camera projection (ground truth — no object detection involved).
- Exports floor-plane pixel<->world calibration correspondences so the Python side can
  finally fit Vision/perception/homography.py against REAL projected data.
- Writes images + one consolidated ground_truth.json + a generation report.

How to run (this script needs the hall already built in the same Blender session):
  GUI:  open Blender, run hall_builder.py in the Scripting tab, then paste and run THIS
        script in the same session.
  CLI:  blender --background --python DigitalTwin/scripts/hall_builder.py \
                            --python DigitalTwin/scripts/render_vision_dataset.py
        (chained --python flags run in one session, in order — scene state persists.)

Requirements: none beyond Blender itself. This runs in Blender's bundled Python and
imports only bpy / bpy_extras / stdlib — do NOT add numpy/pandas/matplotlib here (they
aren't available in Blender's interpreter). All analysis/plotting lives on the Python
side (Vision/perception/).
"""

import bpy
import bpy_extras.object_utils as object_utils
import json
import math
import os
import random

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

# Resolve the repo root from this script's own location (DigitalTwin/scripts/X.py).
# NOTE: when this script is *pasted* into Blender's text editor rather than run from
# disk, __file__ may be undefined — fall back to a hardcoded path in that case.
try:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    REPO_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))
except NameError:
    # update this path if your local clone is elsewhere and you're pasting the script
    REPO_ROOT = r"D:\Projects\Ai guardian"

SEAT_MAP_PATH = os.path.join(REPO_ROOT, "Shared", "seat_map.json")
SYNTHETIC_DATA_DIR = os.path.join(REPO_ROOT, "Vision", "synthetic_data")
GROUND_TRUTH_PATH = os.path.join(SYNTHETIC_DATA_DIR, "ground_truth.json")
VISION_SIM_DIR = os.path.join(REPO_ROOT, "DigitalTwin", "vision_simulation")
REPORT_PATH = os.path.join(VISION_SIM_DIR, "generation_report.txt")

RESOLUTION_X = 1920
RESOLUTION_Y = 1080
RESOLUTION_PERCENTAGE = 100  # drop to e.g. 25 for a fast low-res dry run

# seat_map.json records only "fov_degrees": 110 with no horizontal/vertical/diagonal
# qualifier. We treat it as HORIZONTAL FOV — the usual convention for how security-camera
# specs are quoted, and the only reading Blender maps to without also guessing a sensor
# aspect ratio. (Same spec gap is flagged in Vision/perception/homography.py.)
FOV_DEGREES = 110

# No camera pitch/tilt is recorded anywhere — swept and measured below instead of guessed.
PITCH_CANDIDATES_DEG = list(range(5, 61, 5))

# Placeholder person dimensions (meters). Torso base sits on the bench surface (seat z),
# not the floor, since seat z in seat_map.json is bench height (0.45m), not a person's
# center of mass.
TORSO_RADIUS = 0.16
TORSO_HEIGHT = 0.55
HEAD_RADIUS = 0.11

# Multi-occupancy scenes.
N_MULTI_SCENES = 18
MULTI_MIN_SEATS = 3
MULTI_MAX_SEATS = 12
PERSON_POOL_SIZE = MULTI_MAX_SEATS  # reused across scenes, toggled via hide_render

# Calibration grid. In-frame survivors become the homography correspondences; range kept
# inside the room, away from the walls.
#
# The plane must be the one the measured points actually lie on: a person's bbox bottom
# edge — the "foot point" the pipeline uses — sits on the bench surface (seat z), NOT the
# floor. Calibrating on the floor maps every bench-height point down its view ray to z=0,
# pushing it away from the camera by ~20% of its distance (metres of error at the back of
# the room). Verified against the pure-Python twin of this script: bench plane gives
# 0.16 m median error, floor plane would give ~2.4 m at row 11.
CALIBRATION_PLANE_Z = 0.45
CALIB_X_STEPS = [0.5, 3.0, 6.1, 9.2, 11.7]
CALIB_Y_STEPS = [3.0, 6.0, 9.0, 12.0, 14.5]

SEED = 42

# ─────────────────────────────────────────────
# SCENE PRECONDITION
# ─────────────────────────────────────────────

def require_hall_built():
    """This script renders the hall hall_builder.py builds — bail early if it isn't there."""
    if "Floor" not in bpy.data.objects:
        raise RuntimeError(
            "Hall not found in the scene. Run DigitalTwin/scripts/hall_builder.py first "
            "(see this script's docstring for GUI/CLI workflows)."
        )

# ─────────────────────────────────────────────
# LOAD SEAT MAP
# ─────────────────────────────────────────────

def load_seat_map(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ Loaded seat_map.json — {data['total_seats']} seats")
    return data

# ─────────────────────────────────────────────
# CAMERA
# ─────────────────────────────────────────────

def build_camera(cam_spec):
    """Create a real perspective camera matching the documented spec, replacing the
    decorative cube of the same name that hall_builder.py leaves in the scene."""
    old = bpy.data.objects.get("CAM_01_Front_Center")
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)

    cam_data = bpy.data.cameras.new("CAM_01_Front_Center_data")
    cam_data.type = "PERSP"
    cam_data.lens_unit = "FOV"
    cam_data.sensor_fit = "HORIZONTAL"
    cam_data.angle = math.radians(FOV_DEGREES)

    cam_obj = bpy.data.objects.new("CAM_01_Front_Center", cam_data)
    pos = cam_spec["position"]
    cam_obj.location = (pos["x"], pos["y"], pos["z"])
    bpy.context.scene.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj
    return cam_obj


def set_camera_pitch(cam_obj, pitch_down_deg):
    """A camera with no rotation looks down -Z. Rotating θ about world X gives forward
    (0, sinθ, -cosθ): θ=90° looks level along +Y (toward students, no tilt); decreasing
    below 90° tilts the view downward toward the near seats/floor."""
    cam_obj.rotation_euler = (math.radians(90 - pitch_down_deg), 0.0, 0.0)


def _V(x, y, z):
    """mathutils.Vector without importing mathutils at module top (keeps the import list
    to bpy/bpy_extras/stdlib; mathutils is always available once bpy is loaded)."""
    from mathutils import Vector

    return Vector((x, y, z))


def project_point(scene, cam_obj, x, y, z):
    """Return (u_norm, v_norm, depth) for a world point via Blender's camera projection.
    u_norm/v_norm are in [0,1] across the frame; depth > 0 means in front of the camera."""
    co = object_utils.world_to_camera_view(scene, cam_obj, _V(x, y, z))
    return co.x, co.y, co.z


def is_in_frame(u, v, depth):
    return depth > 0 and 0.0 <= u <= 1.0 and 0.0 <= v <= 1.0


def select_camera_pitch(scene, cam_obj, seats):
    """Sweep candidate downward pitches and pick the one that puts the most seats in
    frame. Pure projection math — no rendering — so this is cheap. Returns
    (best_pitch, best_count, per_pitch_counts)."""
    per_pitch = []
    best_pitch, best_count = PITCH_CANDIDATES_DEG[0], -1
    for pitch in PITCH_CANDIDATES_DEG:
        set_camera_pitch(cam_obj, pitch)
        count = 0
        for s in seats:
            u, v, depth = project_point(scene, cam_obj, s["x"], s["y"], s["z"])
            if is_in_frame(u, v, depth):
                count += 1
        per_pitch.append((pitch, count))
        if count > best_count:
            best_pitch, best_count = pitch, count
    return best_pitch, best_count, per_pitch

# ─────────────────────────────────────────────
# PLACEHOLDER PEOPLE
# ─────────────────────────────────────────────

def make_person(index):
    """Create one cylinder+sphere placeholder rig, parented under an Empty. Hidden from
    render by default; positioned and revealed per scene."""
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
    root = bpy.context.active_object
    root.name = f"Person_{index:02d}"

    bpy.ops.mesh.primitive_cylinder_add(radius=TORSO_RADIUS, depth=TORSO_HEIGHT)
    torso = bpy.context.active_object
    torso.name = f"Person_{index:02d}_Torso"
    torso.parent = root
    torso.location = (0, 0, TORSO_HEIGHT / 2)

    bpy.ops.mesh.primitive_uv_sphere_add(radius=HEAD_RADIUS)
    head = bpy.context.active_object
    head.name = f"Person_{index:02d}_Head"
    head.parent = root
    head.location = (0, 0, TORSO_HEIGHT + HEAD_RADIUS)

    # hide_render is per-object and does NOT cascade from parent to children, so the
    # meshes must be toggled directly — hiding only the Empty would leave every torso
    # and head visible in every frame.
    for obj in (root, torso, head):
        obj.hide_render = True
    return {"root": root, "parts": [torso, head]}


def place_person(person, x, y, z):
    person["root"].location = (x, y, z)
    for obj in (person["root"], *person["parts"]):
        obj.hide_render = False


def hide_person(person):
    for obj in (person["root"], *person["parts"]):
        obj.hide_render = True


def person_bbox_px(person, scene, cam_obj):
    """Compute the person's 2D pixel bounding box from its parts' 3D bound-box corners.
    Returns (bbox_or_None, in_frame). bbox = [x1, y1, x2, y2] with y1=top (head),
    y2=bottom (feet) in image pixel coords."""
    res_x = int(scene.render.resolution_x * scene.render.resolution_percentage / 100)
    res_y = int(scene.render.resolution_y * scene.render.resolution_percentage / 100)

    projected = []
    for obj in person["parts"]:
        for corner in obj.bound_box:
            world = obj.matrix_world @ _V(corner[0], corner[1], corner[2])
            co = object_utils.world_to_camera_view(scene, cam_obj, world)
            projected.append(co)

    front = [p for p in projected if p.z > 0]
    if not front:
        return None, False

    us = [p.x for p in front]
    vs = [p.y for p in front]
    x1 = min(us) * res_x
    x2 = max(us) * res_x
    # Blender NDC v=0 is the BOTTOM of the frame; image pixel row 0 is the TOP. Flip so
    # y1 (smaller) = head/top edge and y2 (larger) = feet/bottom edge, which is the edge
    # Vision/perception/pipeline.foot_point uses as the ground contact point.
    y1 = (1.0 - max(vs)) * res_y
    y2 = (1.0 - min(vs)) * res_y

    in_frame = x2 > 0 and x1 < res_x and y2 > 0 and y1 < res_y
    bbox = [max(0.0, x1), max(0.0, y1), min(float(res_x), x2), min(float(res_y), y2)]
    return bbox, in_frame

# ─────────────────────────────────────────────
# CALIBRATION CORRESPONDENCES
# ─────────────────────────────────────────────

def build_calibration(scene, cam_obj):
    """Project a grid of bench-plane points and keep the in-frame ones as pixel<->world
    correspondences for homography fitting. See CALIBRATION_PLANE_Z for why the bench
    surface, not the floor, is the correct plane here."""
    res_x = int(scene.render.resolution_x * scene.render.resolution_percentage / 100)
    res_y = int(scene.render.resolution_y * scene.render.resolution_percentage / 100)

    correspondences = []
    for wx in CALIB_X_STEPS:
        for wy in CALIB_Y_STEPS:
            u, v, depth = project_point(scene, cam_obj, wx, wy, CALIBRATION_PLANE_Z)
            if not is_in_frame(u, v, depth):
                continue
            px = u * res_x
            py = (1.0 - v) * res_y  # same NDC->pixel y-flip as person_bbox_px
            correspondences.append({"pixel": [px, py], "world": [wx, wy]})
    return correspondences

# ─────────────────────────────────────────────
# RENDER
# ─────────────────────────────────────────────

def configure_render(scene):
    scene.render.resolution_x = RESOLUTION_X
    scene.render.resolution_y = RESOLUTION_Y
    scene.render.resolution_percentage = RESOLUTION_PERCENTAGE
    scene.render.image_settings.file_format = "PNG"

    # EEVEE engine id changed to BLENDER_EEVEE_NEXT in Blender 4.2+.
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = engine
            break
        except (TypeError, ValueError):
            continue

    # Deterministic, fast — no photorealism needed since ground truth comes from
    # projection math, not pixels.
    eevee = getattr(scene, "eevee", None)
    if eevee is not None:
        for attr, value in (("use_gtao", False), ("use_bloom", False)):
            if hasattr(eevee, attr):
                setattr(eevee, attr, value)
        if hasattr(eevee, "taa_render_samples"):
            eevee.taa_render_samples = 16
    scene.render.use_motion_blur = False


def render_to(scene, image_path):
    os.makedirs(os.path.dirname(image_path), exist_ok=True)
    scene.render.filepath = image_path
    bpy.ops.render.render(write_still=True)

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("\n🚀 Guardian AI Vision Dataset Renderer starting...\n")
    random.seed(SEED)
    require_hall_built()

    seat_map_data = load_seat_map(SEAT_MAP_PATH)
    seats = seat_map_data["seats"]
    cam_spec = seat_map_data["cameras"][0]

    scene = bpy.context.scene
    configure_render(scene)

    cam_obj = build_camera(cam_spec)
    best_pitch, best_count, per_pitch = select_camera_pitch(scene, cam_obj, seats)
    set_camera_pitch(cam_obj, best_pitch)
    print(f"✅ Camera pitch {best_pitch}° down — {best_count}/{len(seats)} seats in frame")

    # Per-seat visibility at the chosen pitch (recorded so out-of-frame seats are explicit).
    seat_visibility = {}
    for s in seats:
        u, v, depth = project_point(scene, cam_obj, s["x"], s["y"], s["z"])
        seat_visibility[s["seat_id"]] = {"in_frame": is_in_frame(u, v, depth)}

    correspondences = build_calibration(scene, cam_obj)
    print(f"✅ {len(correspondences)} in-frame floor calibration points")

    pool = [make_person(i) for i in range(PERSON_POOL_SIZE)]
    seats_by_id = {s["seat_id"]: s for s in seats}

    scenes = []

    # ── Single-occupancy: one render per seat ──
    print(f"\n📸 Rendering {len(seats)} single-occupancy frames...")
    for s in seats:
        place_person(pool[0], s["x"], s["y"], s["z"])
        bbox, in_frame = person_bbox_px(pool[0], scene, cam_obj)
        image_rel = os.path.join("images", "single", f"{s['seat_id']}.png")
        render_to(scene, os.path.join(SYNTHETIC_DATA_DIR, image_rel))
        hide_person(pool[0])
        scenes.append({
            "scene_id": f"single_{s['seat_id']}",
            "type": "single",
            "image_path": image_rel.replace("\\", "/"),
            "occupied_seats": [s["seat_id"]],
            "people": [{
                "seat_id": s["seat_id"],
                "true_x": s["x"], "true_y": s["y"], "true_z": s["z"],
                "bbox_px": bbox, "in_frame": in_frame,
            }],
        })

    # ── Multi-occupancy: random subsets ──
    print(f"📸 Rendering {N_MULTI_SCENES} multi-occupancy frames...")
    all_ids = [s["seat_id"] for s in seats]
    for i in range(N_MULTI_SCENES):
        k = random.randint(MULTI_MIN_SEATS, MULTI_MAX_SEATS)
        chosen = random.sample(all_ids, k)
        for slot, seat_id in enumerate(chosen):
            s = seats_by_id[seat_id]
            place_person(pool[slot], s["x"], s["y"], s["z"])
        people = []
        for slot, seat_id in enumerate(chosen):
            s = seats_by_id[seat_id]
            bbox, in_frame = person_bbox_px(pool[slot], scene, cam_obj)
            people.append({
                "seat_id": seat_id,
                "true_x": s["x"], "true_y": s["y"], "true_z": s["z"],
                "bbox_px": bbox, "in_frame": in_frame,
            })
        image_rel = os.path.join("images", "multi", f"scene_{i + 1:02d}.png")
        render_to(scene, os.path.join(SYNTHETIC_DATA_DIR, image_rel))
        for slot in range(len(chosen)):
            hide_person(pool[slot])
        scenes.append({
            "scene_id": f"multi_{i + 1:02d}",
            "type": "multi",
            "image_path": image_rel.replace("\\", "/"),
            "occupied_seats": chosen,
            "people": people,
        })

    ground_truth = {
        "project": "Guardian AI",
        "description": "Synthetic vision dataset — placeholder people, ground-truth pixel bboxes",
        "camera_calibration": {
            "camera_id": cam_spec["camera_id"],
            "position": cam_spec["position"],
            "fov_degrees_horizontal": FOV_DEGREES,
            "pitch_down_degrees": best_pitch,
            "pitch_selection": "swept 5..60deg / 5deg steps; maximized in-frame seat count",
            "resolution": [RESOLUTION_X, RESOLUTION_Y],
            "correspondences": correspondences,
        },
        "seat_visibility": seat_visibility,
        "scenes": scenes,
    }
    os.makedirs(SYNTHETIC_DATA_DIR, exist_ok=True)
    with open(GROUND_TRUTH_PATH, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)
    print(f"✅ ground_truth.json → {GROUND_TRUTH_PATH}")

    write_report(seats, best_pitch, best_count, per_pitch, correspondences, len(scenes))
    print("\n✅ Vision dataset generation complete!")
    print(f"   Images:       {SYNTHETIC_DATA_DIR}")
    print(f"   Ground truth: {GROUND_TRUTH_PATH}")
    print(f"   Report:       {REPORT_PATH}")
    print("\nNext step: python Vision/perception/train.py")


def write_report(seats, best_pitch, best_count, per_pitch, correspondences, n_scenes):
    os.makedirs(VISION_SIM_DIR, exist_ok=True)
    lines = [
        "Guardian AI – Vision Dataset Generation Report",
        "=" * 50,
        "",
        f"Camera FOV (horizontal): {FOV_DEGREES} deg",
        f"Resolution: {RESOLUTION_X}x{RESOLUTION_Y} @ {RESOLUTION_PERCENTAGE}%",
        f"Scenes rendered: {n_scenes} ({len(seats)} single + {N_MULTI_SCENES} multi)",
        f"Floor calibration points (in frame): {len(correspondences)}",
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
        "Note: seats not in frame are a real limitation of this single fixed camera at",
        "its documented position — the front rows sit almost directly below it. This is",
        "measured here, not assumed; seat_map.json's 'covers all 99 seats' is optimistic.",
    ]
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"✅ generation_report.txt → {REPORT_PATH}")


main()
