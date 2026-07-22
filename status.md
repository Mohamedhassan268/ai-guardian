# Status

_Last updated: 2026-07-21_

Snapshot of where each track stands. See `CLAUDE.md` for architecture/conventions
and `ROADMAP.md` for deferred/out-of-scope ideas.

## Phase / track progress

| Phase | Track | Owner | Status |
|---|---|---|---|
| Phase 1 — Scope | (all) | — | Frozen: 2.4 GHz ISM, one room, RSSI localization, BLE + Wi-Fi classification |
| Phase 2 — Digital Twin | Digital Twin | Person 1 | Complete |
| Phase 3 — RF Intelligence | RF | Person 2 | In progress |
| Phase 4 — Vision AI | Vision | Person 3 | In progress |
| Phase 5 — Fusion & Platform | Fusion/Backend/Dashboard | — | Not started |

## Digital Twin (Phase 2) — complete

- Full 3D exam hall modeled (12.2m x 17.8m x 4.0m), all 99 seats mapped with
  coordinates — canonical data in `Shared/seat_map.json`.
- RF node placement simulated across 7 layouts; 4-corner placement confirmed
  and recorded in `DigitalTwin/rf_simulation/best_node_placement.json`.
- 39,600-row synthetic RSSI dataset generated for AI training —
  `AI/training_data/rssi_dataset.csv`.
- Camera position defined for the Vision track (in `Shared/seat_map.json`).
- Full handoff detail: `DigitalTwin/README.md`.

## RF Intelligence (Phase 3) — in progress

- Goal: capture real RSSI data with USRP B210 + GNU Radio to validate/replace
  the simulated dataset above.
- Blocked/pending: no real-hardware results yet — all localization numbers
  below are simulation-only.

## Vision AI (Phase 4) — in progress

- Pipeline scaffolded in `Vision/perception/`: person detection, pixel→hall
  homography, nearest-seat mapping, and shared-schema event emission
  (`person_detected`), mirroring `AI/localization/`'s structure and tests.
- Model: stock pretrained YOLOv8 (`yolov8n.pt` via `ultralytics`), filtered to
  the COCO "person" class. Not trained or fine-tuned on any exam-hall-specific
  data — this is an off-the-shelf detector, unlike the AI/localization model,
  which is trained on Guardian AI's own simulated RSSI data.
- 30 pytest tests pass, validating pipeline *logic* (homography math,
  seat-mapping, event-schema shape, detection filtering) against synthetic
  coordinates.

### Synthetic dataset + geometry results

`DigitalTwin/scripts/project_vision_dataset.py` generates a synthetic dataset
without Blender (pure pinhole projection): per-seat visibility, ground-truth
pixel bounding boxes, and camera calibration correspondences.
`render_vision_dataset.py` is the Blender twin that additionally renders PNGs,
for whoever has Blender when real imagery is needed.

Measured by `python Vision/perception/train.py` (full package in
`Vision/perception/results/`):

| Metric | Result |
|---|---|
| Frame coverage | 84/99 seats (84.8%) |
| Correct seat (geometry only) | 100.0% over 201 people |
| Median position error | 0.160 m |
| Single / multi occupancy | 100% / 100% |

**Read these carefully — they are geometry-only.** They measure the
homography -> seat-mapping chain given *perfect* ground-truth pixel input. They
include **no detection error**, so they are NOT the `>90% vision seat accuracy`
target below. The 0.160 m residual is bounding-box geometry (it equals the
placeholder's body radius), not calibration drift.

Two real findings, both measured rather than assumed:
- **15 of 99 seats are a permanent blind spot.** The front rows sit almost
  directly beneath the ceiling camera. `seat_map.json`'s
  `"covers": "all 11 rows, all 99 seats"` is optimistic and should be corrected.
  Fixing it needs a second camera or a moved/re-aimed one — a Digital Twin
  decision, not a software one. See `results/seat_coverage_map.png`.
- **The homography must be calibrated on the bench plane (z=0.45), not the
  floor.** Feet rest on the bench surface; calibrating on the floor pushes every
  point ~20% of its distance away from the camera (~2.4 m at row 11, i.e. two
  rows wrong). Both generators now use the bench plane.

- Next steps once real footage exists:
  1. Calibrate from real pixel<->world correspondences in the actual hall.
  2. Run the pretrained YOLOv8 detector on real frames — swap
     `evaluate._GroundTruthDetector` for `detection.PersonDetector` — to get a
     true end-to-end number comparable to the `CLAUDE.md` target.
  3. `ByteTrack` multi-frame tracking (in `CLAUDE.md`'s stack, out of scope
     until there's a live frame stream).

## Fusion & Platform (Phase 5) — not started

- Real-time RF service over MQTT/ZeroMQ.
- Fusion engine: spatial + temporal correlation (signal-to-person matching by
  timing, not position alone).
- Backend/dashboard: FastAPI + PostgreSQL + React + Docker.

## Success metrics (from CLAUDE.md)

| Metric | Target | Current |
|---|---|---|
| Detection rate | >90% | Not yet measured |
| Classification rate | >90% | Not yet measured |
| Localization median error | <2 m | 0.0 m (simulated, 4-corner config) — not yet validated on real hardware |
| Correct-bench rate | >80% | 100% (simulated) — not yet validated on real hardware |
| Vision seat accuracy | >90% | Not yet measured end-to-end. Geometry-only proxy: 100% on synthetic data (no detection error included) — see Vision AI section |
| Alert latency | <5 s | Not yet measured |
| False alerts | <1/hr | Not yet measured |

## Open items

- Privacy/retention policy for captured signals must exist before any pilot
  deployment (passive sensing only, no demodulation) — not yet drafted.
- Real RF hardware capture (Phase 3) is the current blocker for validating
  Digital Twin's simulated localization numbers.
- Real or rendered camera frames (Phase 4) are the current blocker for
  measuring any Vision detection/seat-accuracy numbers — no visual data of
  any kind exists in this repo yet.

## Repo

- Public: https://github.com/Mohamedhassan268/ai-guardian
- Latest commit: `4496524` — Phase 2 scripts integrated into
  `DigitalTwin/scripts/` (source of the seat map, RF simulation, and training
  data artifacts).
