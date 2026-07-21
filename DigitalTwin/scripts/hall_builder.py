"""
Guardian AI – Exam Hall Builder v3
Blender Python Script (bpy)

CHANGES FROM v2:
- Front section ceiling height = 2.78m (above teacher desk + whiteboard)
- Single camera placed at front-center ceiling (2.78m height)
- Camera points toward students (down the hall)

How to use:
1. Open Blender
2. Go to Scripting tab
3. Delete old script
4. Paste this entire script
5. Click Run Script
"""

import bpy
import json
import os
import math

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
config = {
    "hall": {
        "X": 12.2,   # width  (left to right)
        "Y": 17.8,   # length (front to back)
        "Z":  4.0    # main hall height
    },
    "front_ceiling_height": 2.78,   # ceiling above teacher area
    "front_section_depth":  2.80,   # how deep the front section is (Y=0 to Y=2.80)
    "rows": 11,
    "left_students":   2,
    "center_students": 5,
    "right_students":  2,
    "left_bench_width":   2.12,
    "center_bench_width": 5.87,
    "right_bench_width":  2.12,
    "aisle_width":    1.065,
    "row_pitch":      1.20,
    "bench_depth":    0.75,
    "bench_height":   0.45,
    "wall_thickness": 0.20,
    "windows":        5,
    "window_width":   2.05,
    "window_height":  1.50,
    "window_sill":    1.00,
    "door_width":     1.00,
    "door_height":    2.20,
    "rf_nodes":       4,
    # update this path if your local clone is elsewhere
    "output_path": r"D:\Projects\Ai guardian\Shared\seat_map.json"
}

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)

def new_collection(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col

def make_box(name, loc, dims, collection):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.dimensions = dims
    bpy.ops.object.transform_apply(scale=True)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    collection.objects.link(obj)
    return obj

def make_material(name, color):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
    return mat

def assign_mat(obj, mat):
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

# ─────────────────────────────────────────────
# MATERIALS
# ─────────────────────────────────────────────

def create_materials():
    return {
        "wall":        make_material("M_Wall",        (0.80, 0.75, 0.68, 1.0)),
        "floor":       make_material("M_Floor",       (0.85, 0.82, 0.78, 1.0)),
        "ceiling":     make_material("M_Ceiling",     (0.95, 0.95, 0.95, 1.0)),
        "ceiling_low": make_material("M_Ceiling_Low", (0.88, 0.88, 0.88, 1.0)),
        "bench":       make_material("M_Bench",       (0.45, 0.28, 0.12, 1.0)),
        "window":      make_material("M_Window",      (0.60, 0.80, 1.00, 0.3)),
        "door":        make_material("M_Door",        (0.35, 0.22, 0.10, 1.0)),
        "whiteboard":  make_material("M_Whiteboard",  (0.98, 0.98, 0.98, 1.0)),
        "camera":      make_material("M_Camera",      (0.05, 0.05, 0.05, 1.0)),
        "rf_node":     make_material("M_RFNode",      (0.00, 0.50, 1.00, 1.0)),
        "teacher":     make_material("M_Teacher",     (0.30, 0.18, 0.08, 1.0)),
        "step_wall":   make_material("M_StepWall",    (0.75, 0.70, 0.63, 1.0)),
    }

# ─────────────────────────────────────────────
# STRUCTURE
# ─────────────────────────────────────────────

def build_structure(cfg, cols, mats):
    X   = cfg["hall"]["X"]         # 12.2
    Y   = cfg["hall"]["Y"]         # 17.8
    Z   = cfg["hall"]["Z"]         # 4.0
    ZL  = cfg["front_ceiling_height"]  # 2.78
    FD  = cfg["front_section_depth"]   # 2.80
    WT  = cfg["wall_thickness"]

    # ── FLOOR ──
    obj = make_box("Floor", (X/2, Y/2, -WT/2), (X, Y, WT), cols["Structure"])
    assign_mat(obj, mats["floor"])

    # ── MAIN CEILING (from Y=FD to Y=17.8) ──
    main_ceiling_length = Y - FD
    obj = make_box("Ceiling_Main",
        (X/2, FD + main_ceiling_length/2, Z + WT/2),
        (X, main_ceiling_length, WT),
        cols["Structure"])
    assign_mat(obj, mats["ceiling"])

    # ── FRONT LOW CEILING (from Y=0 to Y=FD, height=2.78m) ──
    obj = make_box("Ceiling_Front",
        (X/2, FD/2, ZL + WT/2),
        (X, FD, WT),
        cols["Structure"])
    assign_mat(obj, mats["ceiling_low"])

    # ── STEP WALL (vertical drop from Z=4.0 to Z=2.78 at Y=FD) ──
    step_height = Z - ZL   # 4.0 - 2.78 = 1.22m
    obj = make_box("Ceiling_Step_Wall",
        (X/2, FD, Z - step_height/2),
        (X, WT, step_height),
        cols["Structure"])
    assign_mat(obj, mats["step_wall"])

    # ── FRONT WALL (Y=0, whiteboard side) ──
    obj = make_box("Wall_Front", (X/2, -WT/2, ZL/2), (X, WT, ZL), cols["Structure"])
    assign_mat(obj, mats["wall"])

    # ── BACK WALL (Y=17.8) ──
    obj = make_box("Wall_Back", (X/2, Y+WT/2, Z/2), (X, WT, Z), cols["Structure"])
    assign_mat(obj, mats["wall"])

    # ── LEFT WALL (X=0, windows side) ──
    obj = make_box("Wall_Left", (-WT/2, Y/2, Z/2), (WT, Y, Z), cols["Structure"])
    assign_mat(obj, mats["wall"])

    # ── RIGHT WALL (X=12.2, door side) ──
    obj = make_box("Wall_Right", (X+WT/2, Y/2, Z/2), (WT, Y, Z), cols["Structure"])
    assign_mat(obj, mats["wall"])

    print("✅ Structure built (front ceiling 2.78m / main ceiling 4.0m)")

# ─────────────────────────────────────────────
# WINDOWS — left wall (X=0), along Y axis
# ─────────────────────────────────────────────

def build_windows(cfg, cols, mats):
    Y  = cfg["hall"]["Y"]
    WT = cfg["wall_thickness"]
    n  = cfg["windows"]
    ww = cfg["window_width"]
    wh = cfg["window_height"]
    ws = cfg["window_sill"]

    first_y   = 1.02
    total     = n * ww
    remaining = Y - first_y - total
    gap       = remaining / (n - 1) if n > 1 else 0

    for i in range(n):
        y_center = first_y + i * (ww + gap) + ww / 2
        z_center = ws + wh / 2
        obj = make_box(
            f"Window_{i+1:02d}",
            (-WT/2, y_center, z_center),
            (WT + 0.05, ww, wh),
            cols["Windows"]
        )
        assign_mat(obj, mats["window"])

    print(f"✅ {n} windows on left wall")

# ─────────────────────────────────────────────
# DOOR — front-right corner
# ─────────────────────────────────────────────

def build_door(cfg, cols, mats):
    X  = cfg["hall"]["X"]
    WT = cfg["wall_thickness"]
    dw = cfg["door_width"]
    dh = cfg["door_height"]

    obj = make_box("Door",
        (X + WT/2, dw/2 + 0.30, dh/2),
        (WT + 0.05, dw, dh),
        cols["Structure"])
    assign_mat(obj, mats["door"])
    print("✅ Door at front-right corner")

# ─────────────────────────────────────────────
# TEACHER AREA
# ─────────────────────────────────────────────

def build_teacher_area(cfg, cols, mats):
    X = cfg["hall"]["X"]

    obj = make_box("Whiteboard",   (X/2, 0.05, 1.50), (4.0, 0.05, 1.20), cols["Furniture"])
    assign_mat(obj, mats["whiteboard"])

    obj = make_box("Teacher_Desk", (X/2, 1.20, 0.40), (1.50, 0.60, 0.80), cols["Furniture"])
    assign_mat(obj, mats["teacher"])

    print("✅ Teacher area built")

# ─────────────────────────────────────────────
# BENCHES + SEAT MAP
# ─────────────────────────────────────────────

def build_benches(cfg, cols, mats):
    rows = cfg["rows"]
    lbw  = cfg["left_bench_width"]
    cbw  = cfg["center_bench_width"]
    rbw  = cfg["right_bench_width"]
    aw   = cfg["aisle_width"]
    rp   = cfg["row_pitch"]
    bd   = cfg["bench_depth"]
    bh   = cfg["bench_height"]
    ls   = cfg["left_students"]
    cs   = cfg["center_students"]
    rs   = cfg["right_students"]

    left_x   = 0.0
    center_x = lbw + aw
    right_x  = lbw + aw + cbw + aw
    start_y  = 2.80

    seat_map = []

    for row in range(1, rows + 1):
        y = start_y + (row - 1) * rp

        obj = make_box(f"Bench_R{row:02d}_Left",
            (left_x + lbw/2, y, bh/2), (lbw, bd, bh), cols["Benches"])
        assign_mat(obj, mats["bench"])

        obj = make_box(f"Bench_R{row:02d}_Center",
            (center_x + cbw/2, y, bh/2), (cbw, bd, bh), cols["Benches"])
        assign_mat(obj, mats["bench"])

        obj = make_box(f"Bench_R{row:02d}_Right",
            (right_x + rbw/2, y, bh/2), (rbw, bd, bh), cols["Benches"])
        assign_mat(obj, mats["bench"])

        swl = lbw / ls
        swc = cbw / cs
        swr = rbw / rs

        for s in range(1, ls + 1):
            seat_map.append({
                "seat_id": f"R{row:02d}-L{s:02d}",
                "row": row, "section": "Left", "seat_number": s,
                "x": round(left_x + (s - 0.5) * swl, 3),
                "y": round(y, 3), "z": round(bh, 3),
                "occupancy": "empty", "student_id": None
            })

        for s in range(1, cs + 1):
            seat_map.append({
                "seat_id": f"R{row:02d}-C{s:02d}",
                "row": row, "section": "Center", "seat_number": s,
                "x": round(center_x + (s - 0.5) * swc, 3),
                "y": round(y, 3), "z": round(bh, 3),
                "occupancy": "empty", "student_id": None
            })

        for s in range(1, rs + 1):
            seat_map.append({
                "seat_id": f"R{row:02d}-R{s:02d}",
                "row": row, "section": "Right", "seat_number": s,
                "x": round(right_x + (s - 0.5) * swr, 3),
                "y": round(y, 3), "z": round(bh, 3),
                "occupancy": "empty", "student_id": None
            })

    print(f"✅ {rows} rows — {len(seat_map)} seats")
    return seat_map

# ─────────────────────────────────────────────
# SINGLE CAMERA — front center at 2.78m ceiling
# Points down the hall toward all students
# ─────────────────────────────────────────────

def build_camera(cfg, cols, mats):
    X  = cfg["hall"]["X"]
    ZL = cfg["front_ceiling_height"]  # 2.78m
    FD = cfg["front_section_depth"]   # 2.80m

    # Center of hall width, at front ceiling, just before step wall
    cam_x = X / 2        # 6.1m (center)
    cam_y = FD - 0.20    # 2.60m (just before ceiling step)
    cam_z = ZL - 0.05    # 2.73m (just below front ceiling)

    obj = make_box("CAM_01_Front_Center",
        (cam_x, cam_y, cam_z),
        (0.12, 0.12, 0.08),
        cols["Cameras"])
    assign_mat(obj, mats["camera"])

    camera_data = [{
        "camera_id": "CAM_01_Front_Center",
        "position": {"x": round(cam_x, 3), "y": round(cam_y, 3), "z": round(cam_z, 3)},
        "ceiling_height": ZL,
        "fov_degrees": 110,
        "resolution": "1920x1080",
        "fps": 25,
        "direction": "pointing toward students (positive Y)",
        "covers": "all 11 rows, all 99 seats"
    }]

    print(f"✅ Single camera at ({cam_x}, {cam_y}, {cam_z})")
    return camera_data

# ─────────────────────────────────────────────
# RF NODES — 4 ceiling corners (main ceiling 4.0m)
# ─────────────────────────────────────────────

def build_rf_nodes(cfg, cols, mats):
    X = cfg["hall"]["X"]
    Y = cfg["hall"]["Y"]
    Z = cfg["hall"]["Z"]

    positions = [
        (1.0,     1.0,     Z - 0.15, "RF_NODE_01_FrontLeft"),
        (X - 1.0, 1.0,     Z - 0.15, "RF_NODE_02_FrontRight"),
        (1.0,     Y - 1.0, Z - 0.15, "RF_NODE_03_BackLeft"),
        (X - 1.0, Y - 1.0, Z - 0.15, "RF_NODE_04_BackRight"),
    ]

    rf_data = []
    for x, y, z, name in positions:
        obj = make_box(name, (x, y, z), (0.08, 0.08, 0.04), cols["RF_Nodes"])
        assign_mat(obj, mats["rf_node"])
        rf_data.append({
            "node_id": name,
            "x": round(x, 3), "y": round(y, 3), "z": round(z, 3),
            "frequency_bands": ["2.4GHz"],
            "coverage_radius_m": 15
        })

    print(f"✅ {len(positions)} RF nodes placed")
    return rf_data

# ─────────────────────────────────────────────
# LIGHTING
# ─────────────────────────────────────────────

def build_lighting(cfg, cols):
    X  = cfg["hall"]["X"]
    Y  = cfg["hall"]["Y"]
    Z  = cfg["hall"]["Z"]
    ZL = cfg["front_ceiling_height"]
    FD = cfg["front_section_depth"]

    # Front section light (lower ceiling)
    bpy.ops.object.light_add(type='AREA', location=(X/2, FD/2, ZL - 0.2))
    light = bpy.context.active_object
    light.name = "Light_Front"
    light.data.energy = 400
    light.data.size = 1.0
    light.rotation_euler = (math.pi, 0, 0)
    for c in list(light.users_collection):
        c.objects.unlink(light)
    cols["Lighting"].objects.link(light)

    # Main hall lights
    main_positions = [
        (X*0.25, FD + (Y-FD)*0.20, Z - 0.3),
        (X*0.75, FD + (Y-FD)*0.20, Z - 0.3),
        (X*0.25, FD + (Y-FD)*0.50, Z - 0.3),
        (X*0.75, FD + (Y-FD)*0.50, Z - 0.3),
        (X*0.25, FD + (Y-FD)*0.80, Z - 0.3),
        (X*0.75, FD + (Y-FD)*0.80, Z - 0.3),
    ]

    for i, (x, y, z) in enumerate(main_positions):
        bpy.ops.object.light_add(type='AREA', location=(x, y, z))
        light = bpy.context.active_object
        light.name = f"CeilingLight_{i+1:02d}"
        light.data.energy = 800
        light.data.size = 1.5
        light.rotation_euler = (math.pi, 0, 0)
        for c in list(light.users_collection):
            c.objects.unlink(light)
        cols["Lighting"].objects.link(light)

    # Sunlight from windows
    bpy.ops.object.light_add(type='SUN', location=(0, Y/2, Z/2))
    sun = bpy.context.active_object
    sun.name = "Sunlight_Windows"
    sun.data.energy = 2.0
    sun.rotation_euler = (math.pi/4, 0, math.pi/2)
    for c in list(sun.users_collection):
        c.objects.unlink(sun)
    cols["Lighting"].objects.link(sun)

    print("✅ Lighting built")

# ─────────────────────────────────────────────
# EXPORT
# ─────────────────────────────────────────────

def export_seat_map(cfg, seat_map, camera_data, rf_data):
    output = {
        "project": "Guardian AI",
        "version": "3.0",
        "coordinate_system": {
            "origin": "front_left_corner (0,0,0)",
            "X": "hall width  12.2m",
            "Y": "hall length 17.8m",
            "Z": "height — front section 2.78m / main hall 4.0m",
            "units": "meters"
        },
        "hall": cfg["hall"],
        "front_ceiling_height": cfg["front_ceiling_height"],
        "front_section_depth": cfg["front_section_depth"],
        "total_seats": len(seat_map),
        "seats": seat_map,
        "cameras": camera_data,
        "rf_nodes": rf_data
    }
    path = cfg["output_path"]
    with open(path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"✅ seat_map.json saved → {path}")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("\n🚀 Guardian AI Hall Builder v3 starting...\n")

    cfg = config
    clear_scene()

    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.length_unit = 'METERS'
    bpy.context.scene.unit_settings.scale_length = 1.0

    cols = {
        "Structure": new_collection("Structure"),
        "Windows":   new_collection("Windows"),
        "Furniture": new_collection("Furniture"),
        "Benches":   new_collection("Benches"),
        "Cameras":   new_collection("Cameras"),
        "RF_Nodes":  new_collection("RF_Nodes"),
        "Lighting":  new_collection("Lighting"),
    }

    mats = create_materials()

    build_structure(cfg, cols, mats)
    build_windows(cfg, cols, mats)
    build_door(cfg, cols, mats)
    build_teacher_area(cfg, cols, mats)
    seat_map    = build_benches(cfg, cols, mats)
    camera_data = build_camera(cfg, cols, mats)
    rf_data     = build_rf_nodes(cfg, cols, mats)
    build_lighting(cfg, cols)
    export_seat_map(cfg, seat_map, camera_data, rf_data)

    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'MATERIAL'

    print("\n✅ Guardian AI Exam Hall v3 complete!")
    print(f"   Hall:           {cfg['hall']['X']}m x {cfg['hall']['Y']}m")
    print(f"   Front ceiling:  {cfg['front_ceiling_height']}m")
    print(f"   Main ceiling:   {cfg['hall']['Z']}m")
    print(f"   Seats:          {len(seat_map)}")
    print(f"   Camera:         1 (front center at 2.78m)")
    print(f"   RF Nodes:       4 (ceiling corners)")
    print(f"   seat_map.json → {cfg['output_path']}")

main()
