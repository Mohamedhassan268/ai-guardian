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
- 17 pytest tests pass, but they validate the pipeline's *logic* (homography
  math, seat-mapping, event-schema shape, detection filtering) against
  synthetic coordinates — not real detection accuracy.
- **Blocked, same shape as RF's hardware blocker**: unlike RF, Digital Twin
  never produced synthetic *visual* data (no rendered frames, no images) —
  only JSON specs (seat map, camera position). There is currently no real or
  rendered camera frame anywhere in this repo, so no detection/seat-accuracy
  metrics exist yet, and none can be computed until one exists.
- Next steps once visual data (real or rendered) is available:
  1. Real camera calibration — capture pixel↔world point correspondences to
     fit a real homography (`compute_homography`), replacing the synthetic
     points used in tests.
  2. Run the pretrained YOLOv8 detector against real/rendered frames and
     measure actual detection + vision seat accuracy against the `CLAUDE.md`
     targets below.
  3. `ByteTrack` multi-frame tracking (named in `CLAUDE.md`'s Vision stack,
     not yet in scope — meaningless without a live frame stream).

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
| Vision seat accuracy | >90% | Not yet measured — blocked on real/rendered visual data (see Vision AI section) |
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
