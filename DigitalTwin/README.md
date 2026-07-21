# Digital Twin — Phase 2 (Complete)

3D model of the exam hall, seat map, and RF node placement simulation. This is the
foundation every other track (RF, Vision, Fusion) builds on.

## What was built

- Full 3D exam hall: 12.2m (width) x 17.8m (length) x 4.0m (height), with a lower
  front section (2.78m ceiling) above the first ~2.8m of depth.
- All 99 seats mapped with exact coordinates — canonical copy at
  [`Shared/seat_map.json`](../Shared/seat_map.json).
- RF propagation simulated from 4 candidate node layouts (7 configurations tested)
  to all 99 seats — 39,600 RSSI samples generated.
- Best RF node placement confirmed: **4 corners**.

## Coordinate system (binding for every module)

- Origin: front-left corner of the hall = (0, 0, 0)
- X axis: hall width — 0 to 12.2m (left to right)
- Y axis: hall length — 0 to 17.8m (front to back)
- Z axis: height — 0 to 4.0m
- Units: meters
- Seat ID format: `R[row]-[L/C/R][seat number]`, e.g. `R06-C03` = Row 6, Center
  section, seat 3.

This differs slightly from the `Row-Seat` shorthand in the root `CLAUDE.md` — use
the `R[row]-[section][num]` form above, since it's what `Shared/seat_map.json`
actually encodes (row + section + seat number, disambiguating the three seating
blocks per row).

## Confirmed RF node positions

Simulation swept 7 layouts (corners, wall midpoints, diamond, 2x2 grid, front-heavy,
optimal-spread, Y-spread). 4 Corners won on correct-seat rate while keeping a
100% correct-bench rate and 0.0m median error:

| Node | X (m) | Y (m) | Z (m) | Location |
|---|---|---|---|---|
| N1 | 1.0 | 1.0 | 3.85 | Front-left ceiling corner |
| N2 | 11.2 | 1.0 | 3.85 | Front-right ceiling corner |
| N3 | 1.0 | 16.8 | 3.85 | Back-left ceiling corner |
| N4 | 11.2 | 16.8 | 3.85 | Back-right ceiling corner |

Full comparison across all 7 configurations: [`rf_simulation/node_placement_report.txt`](rf_simulation/node_placement_report.txt).
Place real RF hardware at these positions once it arrives.

## Camera position (for Vision track)

- X=6.1m, Y=2.60m, Z=2.73m, pointing toward the students (+Y direction), 110°
  FOV, covering all 11 rows / 99 seats. Also recorded in `Shared/seat_map.json`
  under `cameras`.

## Files in this handoff

| File | Consumer | Purpose |
|---|---|---|
| [`Shared/seat_map.json`](../Shared/seat_map.json) | Everyone | Canonical seat IDs, coordinates, camera + RF node positions |
| [`AI/training_data/rssi_dataset.csv`](../AI/training_data/rssi_dataset.csv) | AI track | 39,600 rows — train the localization model on this |
| [`AI/training_data/rssi_fingerprint.json`](../AI/training_data/rssi_fingerprint.json) | AI track | Mean RSSI per seat — for nearest-neighbor localization |
| [`rf_simulation/best_node_placement.json`](rf_simulation/best_node_placement.json) | Everyone | Confirmed 4-corner node positions (machine-readable) |
| [`rf_simulation/node_placement_analysis.png`](rf_simulation/node_placement_analysis.png) | Everyone | Hall map + node positions + per-seat error heatmap |
| [`rf_simulation/configuration_comparison.png`](rf_simulation/configuration_comparison.png) | Everyone | Median error / correct-bench rate across all 7 layouts tested |
| [`rf_simulation/simulation_report.txt`](rf_simulation/simulation_report.txt) | Everyone | Simulation parameters (path loss exponent 2.8, TX power 0 dBm, noise σ 3.0 dB, 100 samples/seat) |

All of the above are generated, not hand-written — the source scripts live in
[`scripts/`](scripts/): `hall_builder.py` (Blender, produces `seat_map.json`),
`node_placement_optimizer.py` (produces the `rf_simulation/` outputs), and
`rf_propagation_simulator.py` (produces the `AI/training_data/` outputs). Rerun them to
regenerate any of the above.

## Next steps by track

**AI (localization):**
1. Train a k-NN or MLP on `AI/training_data/rssi_dataset.csv` — input: 4 RSSI
   values, output: (x, y) seat position.
2. Target: median error under 2m, correct-bench rate over 80% (both already met
   in simulation at 0.0m / 100%).
3. Fine-tune on real RSSI data once RF hardware capture is available.

**Vision:**
1. Set up YOLOv8 person detection.
2. Implement homography: camera pixel position → (x, y) hall coordinate, using
   the camera position above.
3. Map each detected person to a seat ID via `Shared/seat_map.json`.

**RF (Phase 3, in progress):** capturing real RSSI data with USRP B210 + GNU
Radio to replace/validate the simulated dataset above.
