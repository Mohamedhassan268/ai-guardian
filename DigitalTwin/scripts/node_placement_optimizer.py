"""
Guardian AI – RF Node Placement Optimizer
Phase 2: Digital Twin → Node Placement Optimization

What this does:
- Reads seat_map.json
- Tests different RF node placement configurations
- For each configuration simulates RSSI and estimates localization error
- Finds the best node placement that minimizes localization error
- Saves results and recommendation report

How to run:
    python node_placement_optimizer.py

Requirements:
    pip install numpy pandas matplotlib
"""

import json
import math
import random
import os
import numpy as np
import itertools
import matplotlib
matplotlib.use('Agg')  # non-interactive backend for saving plots
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))       # DigitalTwin/scripts
REPO_ROOT  = os.path.dirname(os.path.dirname(SCRIPT_DIR))      # repo root
SEAT_MAP_PATH = os.path.join(REPO_ROOT, "Shared", "seat_map.json")
OUTPUT_DIR    = os.path.join(REPO_ROOT, "DigitalTwin", "rf_simulation")

# Hall dimensions
HALL_X = 12.2
HALL_Y = 17.8
HALL_Z =  4.0

# RF model parameters (same as simulator)
FREQ_GHZ       = 2.437
TX_POWER_DBM   = 0.0
PATH_LOSS_EXP  = 2.8
NOISE_STD_DB   = 3.0
SAMPLES        = 30    # samples per seat for optimization (less than simulator for speed)

# Node height (ceiling)
NODE_HEIGHT = 3.85

# Number of nodes to place
N_NODES = 4

# ─────────────────────────────────────────────
# CANDIDATE NODE POSITIONS TO TEST
# Grid of positions across the hall ceiling
# ─────────────────────────────────────────────

def generate_candidate_positions():
    """Generate a grid of candidate node positions on the ceiling."""
    candidates = []
    # Grid: every 2m along X and Y, staying 1m from walls
    x_positions = np.arange(1.0, HALL_X, 2.0)
    y_positions = np.arange(1.0, HALL_Y, 2.0)

    for x in x_positions:
        for y in y_positions:
            candidates.append({
                "x": round(float(x), 2),
                "y": round(float(y), 2),
                "z": NODE_HEIGHT
            })

    print(f"📍 Generated {len(candidates)} candidate positions")
    return candidates

# ─────────────────────────────────────────────
# PATH LOSS MODEL
# ─────────────────────────────────────────────

def compute_pl0():
    freq_hz = FREQ_GHZ * 1e9
    c = 3e8
    return 20 * math.log10((4 * math.pi * freq_hz) / c)

PL0 = compute_pl0()

def distance_3d(p1, p2):
    return math.sqrt(
        (p1["x"] - p2["x"])**2 +
        (p1["y"] - p2["y"])**2 +
        (p1["z"] - p2["z"])**2
    )

def estimate_rssi(node_pos, seat_pos):
    d = max(distance_3d(node_pos, seat_pos), 0.1)
    pl = PL0 + 10 * PATH_LOSS_EXP * math.log10(d)
    return TX_POWER_DBM - pl

def noisy_rssi(node_pos, seat_pos):
    return estimate_rssi(node_pos, seat_pos) + random.gauss(0, NOISE_STD_DB)

# ─────────────────────────────────────────────
# NEAREST NEIGHBOR LOCALIZATION
# Given RSSI vector → find closest seat in fingerprint DB
# ─────────────────────────────────────────────

def build_fingerprint_db(seats, nodes):
    """Build fingerprint DB for a given node configuration."""
    db = []
    for seat in seats:
        seat_pos = {"x": seat["x"], "y": seat["y"], "z": seat["z"]}
        rssi_vec = [estimate_rssi(node, seat_pos) for node in nodes]
        db.append({
            "seat_id": seat["seat_id"],
            "x": seat["x"],
            "y": seat["y"],
            "rssi_vec": rssi_vec
        })
    return db

def nearest_neighbor_localize(measured_rssi, fingerprint_db):
    """Find the seat with closest RSSI vector (Euclidean distance)."""
    best_seat = None
    best_dist = float('inf')

    for entry in fingerprint_db:
        fp_vec = entry["rssi_vec"]
        dist = math.sqrt(sum((m - f)**2 for m, f in zip(measured_rssi, fp_vec)))
        if dist < best_dist:
            best_dist = dist
            best_seat = entry

    return best_seat

# ─────────────────────────────────────────────
# EVALUATE ONE NODE CONFIGURATION
# ─────────────────────────────────────────────

def evaluate_configuration(nodes, seats):
    """
    For a given set of node positions:
    1. Build fingerprint DB
    2. Simulate measurements for each seat
    3. Run nearest-neighbor localization
    4. Calculate localization error
    """
    fingerprint_db = build_fingerprint_db(seats, nodes)

    errors_m       = []
    correct_bench  = 0
    correct_seat   = 0

    for seat in seats:
        seat_pos = {"x": seat["x"], "y": seat["y"], "z": seat["z"]}

        # Simulate multiple noisy measurements and average
        measured = []
        for node in nodes:
            samples = [noisy_rssi(node, seat_pos) for _ in range(SAMPLES)]
            measured.append(np.mean(samples))

        # Localize
        predicted = nearest_neighbor_localize(measured, fingerprint_db)

        # Calculate error
        error_m = math.sqrt(
            (predicted["x"] - seat["x"])**2 +
            (predicted["y"] - seat["y"])**2
        )
        errors_m.append(error_m)

        # Check if correct seat
        if predicted["seat_id"] == seat["seat_id"]:
            correct_seat += 1

        # Check if correct bench row (within 1 row)
        pred_row = int(predicted["seat_id"][1:3])
        true_row = seat["row"]
        if abs(pred_row - true_row) <= 1:
            correct_bench += 1

    median_error   = np.median(errors_m)
    mean_error     = np.mean(errors_m)
    max_error      = np.max(errors_m)
    correct_seat_pct  = correct_seat  / len(seats) * 100
    correct_bench_pct = correct_bench / len(seats) * 100

    return {
        "median_error_m":    round(median_error, 3),
        "mean_error_m":      round(mean_error, 3),
        "max_error_m":       round(max_error, 3),
        "correct_seat_pct":  round(correct_seat_pct, 1),
        "correct_bench_pct": round(correct_bench_pct, 1),
        "errors_m":          errors_m
    }

# ─────────────────────────────────────────────
# PREDEFINED CONFIGURATIONS TO TEST
# ─────────────────────────────────────────────

def get_test_configurations():
    """
    Test several meaningful node placement strategies.
    Returns list of (name, nodes) tuples.
    """
    configs = []

    # Config 1: 4 corners (current default)
    configs.append(("4_Corners", [
        {"x": 1.0,        "y": 1.0,        "z": NODE_HEIGHT},
        {"x": HALL_X-1.0, "y": 1.0,        "z": NODE_HEIGHT},
        {"x": 1.0,        "y": HALL_Y-1.0, "z": NODE_HEIGHT},
        {"x": HALL_X-1.0, "y": HALL_Y-1.0, "z": NODE_HEIGHT},
    ]))

    # Config 2: 4 midpoints of walls
    configs.append(("4_Wall_Midpoints", [
        {"x": HALL_X/2,   "y": 1.0,        "z": NODE_HEIGHT},
        {"x": HALL_X/2,   "y": HALL_Y-1.0, "z": NODE_HEIGHT},
        {"x": 1.0,        "y": HALL_Y/2,   "z": NODE_HEIGHT},
        {"x": HALL_X-1.0, "y": HALL_Y/2,   "z": NODE_HEIGHT},
    ]))

    # Config 3: Diamond pattern (center-biased)
    configs.append(("Diamond", [
        {"x": HALL_X/2,   "y": HALL_Y*0.15, "z": NODE_HEIGHT},
        {"x": HALL_X/2,   "y": HALL_Y*0.85, "z": NODE_HEIGHT},
        {"x": 1.0,        "y": HALL_Y/2,    "z": NODE_HEIGHT},
        {"x": HALL_X-1.0, "y": HALL_Y/2,    "z": NODE_HEIGHT},
    ]))

    # Config 4: 2x2 grid (quarter positions)
    configs.append(("2x2_Grid", [
        {"x": HALL_X*0.25, "y": HALL_Y*0.25, "z": NODE_HEIGHT},
        {"x": HALL_X*0.75, "y": HALL_Y*0.25, "z": NODE_HEIGHT},
        {"x": HALL_X*0.25, "y": HALL_Y*0.75, "z": NODE_HEIGHT},
        {"x": HALL_X*0.75, "y": HALL_Y*0.75, "z": NODE_HEIGHT},
    ]))

    # Config 5: Front-heavy (closer to camera, more coverage near teacher)
    configs.append(("Front_Heavy", [
        {"x": 1.0,        "y": 1.0,        "z": NODE_HEIGHT},
        {"x": HALL_X-1.0, "y": 1.0,        "z": NODE_HEIGHT},
        {"x": HALL_X/4,   "y": HALL_Y*0.6, "z": NODE_HEIGHT},
        {"x": HALL_X*3/4, "y": HALL_Y*0.6, "z": NODE_HEIGHT},
    ]))

    # Config 6: Spread along Y axis (long dimension)
    configs.append(("Y_Spread", [
        {"x": HALL_X/2,   "y": HALL_Y*0.10, "z": NODE_HEIGHT},
        {"x": HALL_X/2,   "y": HALL_Y*0.37, "z": NODE_HEIGHT},
        {"x": HALL_X/2,   "y": HALL_Y*0.63, "z": NODE_HEIGHT},
        {"x": HALL_X/2,   "y": HALL_Y*0.90, "z": NODE_HEIGHT},
    ]))

    # Config 7: Optimal spread (maximizing coverage area)
    configs.append(("Optimal_Spread", [
        {"x": HALL_X*0.20, "y": HALL_Y*0.20, "z": NODE_HEIGHT},
        {"x": HALL_X*0.80, "y": HALL_Y*0.20, "z": NODE_HEIGHT},
        {"x": HALL_X*0.20, "y": HALL_Y*0.80, "z": NODE_HEIGHT},
        {"x": HALL_X*0.80, "y": HALL_Y*0.80, "z": NODE_HEIGHT},
    ]))

    return configs

# ─────────────────────────────────────────────
# VISUALIZE RESULTS
# ─────────────────────────────────────────────

def plot_error_heatmap(best_config_name, best_nodes, seats, output_dir):
    """Plot localization error heatmap for best configuration."""
    fingerprint_db = build_fingerprint_db(seats, best_nodes)

    fig, axes = plt.subplots(1, 2, figsize=(16, 10))

    # ── Left: Hall layout with node positions ──
    ax = axes[0]
    ax.set_xlim(-0.5, HALL_X + 0.5)
    ax.set_ylim(-0.5, HALL_Y + 0.5)
    ax.set_aspect('equal')

    # Hall boundary
    rect = patches.Rectangle((0, 0), HALL_X, HALL_Y,
                               linewidth=2, edgecolor='black', facecolor='#f5f5f5')
    ax.add_patch(rect)

    # Seats
    for seat in seats:
        color = {'Left': '#FFD700', 'Center': '#90EE90', 'Right': '#87CEEB'}[seat['section']]
        ax.plot(seat['x'], seat['y'], 's', color=color, markersize=4, alpha=0.7)

    # RF Nodes
    for i, node in enumerate(best_nodes):
        ax.plot(node['x'], node['y'], '^', color='red', markersize=12, zorder=5)
        ax.annotate(f'N{i+1}', (node['x'], node['y']),
                    textcoords="offset points", xytext=(5, 5), fontsize=8, color='red')

    ax.set_title(f'Best Configuration: {best_config_name}\n(Red = RF Nodes, Colors = Sections)', fontsize=11)
    ax.set_xlabel('Hall Width (m)')
    ax.set_ylabel('Hall Length (m)')
    ax.grid(True, alpha=0.3)

    # Legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='s', color='w', markerfacecolor='#FFD700', markersize=8, label='Left section'),
        Line2D([0], [0], marker='s', color='w', markerfacecolor='#90EE90', markersize=8, label='Center section'),
        Line2D([0], [0], marker='s', color='w', markerfacecolor='#87CEEB', markersize=8, label='Right section'),
        Line2D([0], [0], marker='^', color='w', markerfacecolor='red', markersize=10, label='RF Node'),
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=8)

    # ── Right: Error heatmap ──
    ax2 = axes[1]
    ax2.set_xlim(-0.5, HALL_X + 0.5)
    ax2.set_ylim(-0.5, HALL_Y + 0.5)
    ax2.set_aspect('equal')

    rect2 = patches.Rectangle((0, 0), HALL_X, HALL_Y,
                                linewidth=2, edgecolor='black', facecolor='#f5f5f5')
    ax2.add_patch(rect2)

    # Color each seat by localization error
    errors = []
    for seat in seats:
        seat_pos = {"x": seat["x"], "y": seat["y"], "z": seat["z"]}
        measured = []
        for node in best_nodes:
            s = [noisy_rssi(node, seat_pos) for _ in range(SAMPLES)]
            measured.append(np.mean(s))
        predicted = nearest_neighbor_localize(measured, fingerprint_db)
        error = math.sqrt((predicted["x"]-seat["x"])**2 + (predicted["y"]-seat["y"])**2)
        errors.append(error)

    sc = ax2.scatter(
        [s['x'] for s in seats],
        [s['y'] for s in seats],
        c=errors, cmap='RdYlGn_r', s=60, vmin=0, vmax=3.0, zorder=3
    )
    plt.colorbar(sc, ax=ax2, label='Localization Error (m)')

    for i, node in enumerate(best_nodes):
        ax2.plot(node['x'], node['y'], '^', color='blue', markersize=12, zorder=5)
        ax2.annotate(f'N{i+1}', (node['x'], node['y']),
                     textcoords="offset points", xytext=(5, 5), fontsize=8, color='blue')

    ax2.set_title(f'Localization Error Heatmap\nGreen=Low Error, Red=High Error', fontsize=11)
    ax2.set_xlabel('Hall Width (m)')
    ax2.set_ylabel('Hall Length (m)')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plot_path = os.path.join(output_dir, "node_placement_analysis.png")
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Plot saved -> {plot_path}")

def plot_config_comparison(results, output_dir):
    """Bar chart comparing all configurations."""
    names   = [r['name'] for r in results]
    medians = [r['median_error_m'] for r in results]
    bench   = [r['correct_bench_pct'] for r in results]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    colors = ['#2ecc71' if m == min(medians) else '#3498db' for m in medians]
    bars = ax1.bar(names, medians, color=colors, edgecolor='black', linewidth=0.5)
    ax1.set_ylabel('Median Error (m)', fontsize=11)
    ax1.set_title('Node Placement Comparison — Localization Error\n(Green = Best)', fontsize=12)
    ax1.set_ylim(0, max(medians) * 1.3)
    for bar, val in zip(bars, medians):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                 f'{val:.2f}m', ha='center', va='bottom', fontsize=9)
    ax1.tick_params(axis='x', rotation=30)
    ax1.grid(axis='y', alpha=0.3)

    colors2 = ['#2ecc71' if b == max(bench) else '#e74c3c' for b in bench]
    bars2 = ax2.bar(names, bench, color=colors2, edgecolor='black', linewidth=0.5)
    ax2.set_ylabel('Correct Bench Rate (%)', fontsize=11)
    ax2.set_title('Node Placement Comparison — Correct Bench Rate\n(Green = Best)', fontsize=12)
    ax2.set_ylim(0, 110)
    for bar, val in zip(bars2, bench):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                 f'{val:.1f}%', ha='center', va='bottom', fontsize=9)
    ax2.tick_params(axis='x', rotation=30)
    ax2.grid(axis='y', alpha=0.3)
    ax2.axhline(y=80, color='orange', linestyle='--', alpha=0.7, label='80% target')
    ax2.legend()

    plt.tight_layout()
    plot_path = os.path.join(output_dir, "configuration_comparison.png")
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Comparison plot saved -> {plot_path}")

# ─────────────────────────────────────────────
# SAVE REPORT
# ─────────────────────────────────────────────

def save_report(results, best, output_dir):
    path = os.path.join(output_dir, "node_placement_report.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Guardian AI – Node Placement Optimization Report\n")
        f.write("=" * 55 + "\n\n")
        f.write(f"Hall: {HALL_X}m x {HALL_Y}m x {HALL_Z}m\n")
        f.write(f"Nodes tested: {N_NODES}\n")
        f.write(f"Frequency: {FREQ_GHZ} GHz\n")
        f.write(f"Configurations tested: {len(results)}\n\n")
        f.write("=" * 55 + "\n")
        f.write("RESULTS (sorted by median error)\n")
        f.write("=" * 55 + "\n\n")

        for r in sorted(results, key=lambda x: x['median_error_m']):
            marker = " <-- BEST" if r['name'] == best['name'] else ""
            f.write(f"Config: {r['name']}{marker}\n")
            f.write(f"  Median error:    {r['median_error_m']} m\n")
            f.write(f"  Mean error:      {r['mean_error_m']} m\n")
            f.write(f"  Max error:       {r['max_error_m']} m\n")
            f.write(f"  Correct bench:   {r['correct_bench_pct']}%\n")
            f.write(f"  Correct seat:    {r['correct_seat_pct']}%\n")
            f.write(f"  Node positions:\n")
            for i, node in enumerate(r['nodes']):
                f.write(f"    N{i+1}: ({node['x']}, {node['y']}, {node['z']})\n")
            f.write("\n")

        f.write("=" * 55 + "\n")
        f.write("RECOMMENDATION\n")
        f.write("=" * 55 + "\n\n")
        f.write(f"Best configuration: {best['name']}\n")
        f.write(f"Median localization error: {best['median_error_m']} m\n")
        f.write(f"Correct bench rate: {best['correct_bench_pct']}%\n\n")
        f.write("Place RF nodes at these positions:\n")
        for i, node in enumerate(best['nodes']):
            f.write(f"  Node {i+1}: X={node['x']}m, Y={node['y']}m, Height={node['z']}m\n")

    print(f"✅ Report saved -> {path}")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("\n🚀 Guardian AI Node Placement Optimizer starting...\n")

    random.seed(42)  # fixed seed so reruns are deterministic/diffable

    # Load seat map
    with open(SEAT_MAP_PATH, "r") as f:
        seat_map_data = json.load(f)
    seats = seat_map_data["seats"]
    print(f"✅ Loaded {len(seats)} seats\n")

    # Get configurations to test
    configurations = get_test_configurations()
    print(f"🔍 Testing {len(configurations)} node placement configurations...\n")

    # Evaluate each configuration
    results = []
    for name, nodes in configurations:
        print(f"  Testing: {name}...", end=" ")
        metrics = evaluate_configuration(nodes, seats)
        result = {
            "name":             name,
            "nodes":            nodes,
            "median_error_m":   metrics["median_error_m"],
            "mean_error_m":     metrics["mean_error_m"],
            "max_error_m":      metrics["max_error_m"],
            "correct_seat_pct": metrics["correct_seat_pct"],
            "correct_bench_pct":metrics["correct_bench_pct"],
        }
        results.append(result)
        print(f"median={metrics['median_error_m']}m  bench={metrics['correct_bench_pct']}%")

    # Find best configuration
    best = min(results, key=lambda x: x['median_error_m'])

    print(f"\n{'='*55}")
    print(f"BEST CONFIGURATION: {best['name']}")
    print(f"  Median error:  {best['median_error_m']} m")
    print(f"  Correct bench: {best['correct_bench_pct']}%")
    print(f"  Correct seat:  {best['correct_seat_pct']}%")
    print(f"  Node positions:")
    for i, node in enumerate(best['nodes']):
        print(f"    Node {i+1}: ({node['x']}, {node['y']}, {node['z']})")
    print(f"{'='*55}\n")

    # Save outputs
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    save_report(results, best, OUTPUT_DIR)

    # Generate plots
    print("📊 Generating plots...")
    plot_config_comparison(results, OUTPUT_DIR)
    plot_error_heatmap(best['name'], best['nodes'], seats, OUTPUT_DIR)

    # Save best config as JSON
    best_path = os.path.join(OUTPUT_DIR, "best_node_placement.json")
    with open(best_path, "w", encoding="utf-8") as f:
        json.dump({
            "project": "Guardian AI",
            "best_configuration": best['name'],
            "median_error_m": best['median_error_m'],
            "correct_bench_pct": best['correct_bench_pct'],
            "nodes": best['nodes']
        }, f, indent=2)
    print(f"✅ Best placement saved -> {best_path}")

    print(f"\n✅ Node Placement Optimization complete!")
    print(f"\nOutputs in: {OUTPUT_DIR}")
    print("  node_placement_report.txt     - full results report")
    print("  configuration_comparison.png  - bar chart comparison")
    print("  node_placement_analysis.png   - heatmap of best config")
    print("  best_node_placement.json      - best config for deployment")
    print(f"\nNext step: Place real RF nodes at the recommended positions.")

main()
