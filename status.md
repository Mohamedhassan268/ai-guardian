# Status

_Last updated: 2026-07-25_

Snapshot of where each track stands. See `CLAUDE.md` for architecture/conventions
and `ROADMAP.md` for deferred/out-of-scope ideas.

---

## Team

Two people. Digital Twin, RF Intelligence, Vision AI, and AI/localization are the
same tracks as before — ownership below reflects who currently drives each one,
not a change in scope.

| Track | Owner |
|---|---|
| Digital Twin | Person 1 (RF + Digital Twin) |
| RF Intelligence | Person 1 (RF + Digital Twin) |
| Vision AI | Person 2 (Vision + AI) |
| AI / localization | Person 2 (Vision + AI) |

---

## Phase / track progress

| Phase | Track | Owner | Status |
|---|---|---|---|
| Phase 1 — Scope | (all) | — | Frozen: 2.4 GHz ISM, one room, RSSI localization, BLE + Wi-Fi classification |
| Phase 2 — Digital Twin | Digital Twin | Person 1 | Complete ✅ |
| Phase 3 — RF Intelligence | RF | Person 1 | In progress |
| Phase 4 — Vision AI | Vision | Person 2 | In progress |
| Phase 5 — Fusion & Platform | Fusion/Backend/Dashboard | — | Not started |

---

## Digital Twin (Phase 2) — complete ✅

- Full 3D exam hall modeled (12.2m x 17.8m x 4.0m), all 99 seats mapped with
  coordinates — canonical data in `Shared/seat_map.json`.
- Front section ceiling: 2.78m (above teacher/whiteboard area). Main hall ceiling: 4.0m.
- RF node placement simulated across 7 layouts; 4-corner placement confirmed
  and recorded in `DigitalTwin/rf_simulation/best_node_placement.json`.
- 39,600-row synthetic RSSI dataset generated for AI training —
  `AI/training_data/rssi_dataset.csv`.
- Camera position defined: X=6.1m, Y=2.60m, Z=2.73m (front-center ceiling, FOV=110°).
- The three generator scripts behind all of the above (Blender hall builder, RF
  node-placement optimizer, RF propagation simulator) are now committed under
  `DigitalTwin/scripts/`, with repo-relative paths and a fixed RNG seed so
  reruns are reproducible — previously they existed only as loose local files.
- Full handoff detail: `DigitalTwin/README.md`.

### Deliverables handed to team

| File | Location | Consumer |
|---|---|---|
| seat_map.json | Shared/ | Everyone — canonical seat coordinates |
| rssi_dataset.csv | AI/training_data/ | Person 2 (AI) — localization training |
| rssi_fingerprint.json | AI/training_data/ | Person 2 (AI) — nearest-neighbor localization |
| best_node_placement.json | DigitalTwin/rf_simulation/ | Everyone — confirmed node positions |
| node_placement_analysis.png | DigitalTwin/rf_simulation/ | Everyone — visual heatmap |

---

## RF Intelligence (Phase 3) — in progress

**Owner:** Person 1
**Goal:** Capture real RF data at 2.4 GHz to validate and replace the simulated
dataset from Phase 2.

### Hardware status (UPDATED)

The available USRP covers **50 MHz – 2.2 GHz only** — it cannot reach 2.4 GHz.
This changes the capture strategy for Phase 3:

| Task | Tool | Status |
|---|---|---|
| 2.4 GHz RSSI collection (BLE + Wi-Fi) | ESP32 x4 (built-in 2.4 GHz radio) | To order |
| Wideband spectrum capture below 2.2 GHz | USRP + GNU Radio | Ready |
| 2.4 GHz IQ capture (optional) | RTL-SDR + upconverter OR HackRF | To decide |

### Revised approach

**Primary 2.4 GHz data collection → ESP32 nodes**
- ESP32 has native 2.4 GHz radio (BLE + Wi-Fi)
- Each node reports RSSI of detected devices over serial/WiFi
- 4 nodes placed at confirmed corner positions
- No USRP needed for RSSI localization

**USRP → used for sub-2.2 GHz monitoring and signal analysis**
- Validates energy detection and classification pipeline
- Used for ISM sub-GHz devices (433 MHz, 868 MHz, 915 MHz)
- Useful for future protocol expansion (LoRa, ISM remotes)

### Immediate tasks

1. Order 4x ESP32 boards (~$5 each)
2. Flash ESP32 firmware: BLE + Wi-Fi RSSI scanner
3. Flash 1x ESP32 as BLE advertising beacon (test transmitter)
4. Deploy 3 ESP32 RSSI nodes at confirmed corner positions
5. Collect real RSSI fingerprint data at 20+ seat positions
6. Compare real vs simulated RSSI — validate Digital Twin accuracy
7. Build Python energy detector using ESP32 RSSI stream → JSON events
8. Build rule-based classifier (BLE / Wi-Fi / Unknown)

### Current blockers

- ESP32 boards not yet ordered
- USRP cannot reach 2.4 GHz (frequency limitation confirmed)
- Need decision: buy HackRF/RTL-SDR for IQ capture or rely on ESP32 RSSI only

### Next milestone

4 ESP32 nodes deployed → real RSSI collected at all 99 seats →
compared against simulated fingerprint → localization accuracy validated on real hardware.

### Expected deliverables

| Deliverable | Consumer |
|---|---|
| Real RSSI fingerprint dataset (20+ positions) | Person 2 (AI) — validates simulation |
| ESP32 RSSI scanner firmware | RF/firmware/ |
| ESP32 BLE beacon firmware | RF/firmware/ |
| Energy detector script (RSSI stream → JSON event) | Phase 5 fusion engine |
| Rule-based classifier (BLE / Wi-Fi / Unknown) | Phase 5 fusion engine |
| Real vs simulated RSSI comparison report | Everyone |

---

## Vision AI (Phase 4) — in progress

**Owner:** Person 2

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

### Next steps

1. Set up ByteTrack multi-frame tracking (named in `CLAUDE.md`'s stack) once a
   live frame stream exists — out of scope for the current single-frame pipeline.
2. Calibrate from real pixel<->world correspondences once real/rendered footage
   exists — see the blind-spot finding above first, since it affects placement.
3. Run the pretrained YOLOv8 detector on real frames — swap
   `evaluate._GroundTruthDetector` for `detection.PersonDetector` — to get a
   true end-to-end number comparable to the `CLAUDE.md` target.
4. Output behavior events (head-down duration, hand-under-desk) as JSON, once
   detection is validated on real footage.

**Waiting on:** IP camera purchase (see Hardware below); resolution of the
15-seat blind spot (second camera or reposition).

---

## Fusion & Platform (Phase 5) — not started

- Real-time RF service over MQTT/ZeroMQ.
- Fusion engine: spatial + temporal correlation (signal-to-person matching by
  timing, not position alone).
- Backend/dashboard: FastAPI + PostgreSQL + React + Docker.
- Evidence packaging: video clip + RF snapshot + timestamp.
- Can proceed now against the shared event schema using synthetic events from
  both `AI/localization` and `Vision/perception` — not blocked on hardware.

---

## Hardware

| Item | Status | Purpose |
|---|---|---|
| USRP (50 MHz – 2.2 GHz) | Owned — cannot reach 2.4 GHz | Sub-2.2 GHz spectrum capture only |
| ESP32 x4 | To order (~$20 total) | 3x RSSI nodes + 1x BLE beacon — primary 2.4 GHz capture |
| HackRF / RTL-SDR | To decide | Optional: 2.4 GHz IQ capture if needed |
| IP Camera x1 | To buy (Phase 4) | Vision AI — Hikvision/Dahua 4MP PoE; placement should account for the 15-seat blind spot above |
| Laptop (Quadro M1200, Ubuntu 24) | Ready — driver updated | Development machine |

---

## Success metrics (from CLAUDE.md)

| Metric | Target | Current | Measured in |
|---|---|---|---|
| Detection rate | >90% | Not yet measured | Phase 3 |
| Classification rate | >90% | Not yet measured | Phase 3 |
| Localization median error | <2 m | 0.0 m (sim, FingerprintKNN, window=40) | Phase 3 real hardware |
| Correct-bench rate | >80% | 94.9% (sim, FingerprintKNN) | Phase 3 real hardware |
| Vision seat accuracy | >90% | Not yet measured end-to-end. Geometry-only proxy: 100% on synthetic data (no detection error included) — see Vision AI section | Phase 4 real footage |
| Alert latency | <5 s | Not yet measured | Phase 5 |
| False alerts | <1/hr | Not yet measured | Phase 5 |

---

## Open items

- ESP32 boards not yet ordered (Phase 3 blocker — primary 2.4 GHz capture tool).
- USRP frequency limitation: max 2.2 GHz — decision needed on HackRF/RTL-SDR for IQ capture.
- `DigitalTwin/README.md` exists ✅ but needs a link update to reflect the ESP32 strategy.
- Privacy/retention policy for captured signals must exist before any pilot
  deployment (passive sensing only, no demodulation) — not yet drafted.
- Real RF hardware capture (Phase 3) is the current blocker for validating
  Digital Twin's simulated localization numbers.
- Real or rendered camera frames (Phase 4) are the current blocker for
  measuring end-to-end Vision detection/seat-accuracy numbers.
- 15 of 99 seats are outside the documented camera's field of view — needs a
  second camera or repositioning decision before real capture (see Vision AI
  section); `seat_map.json`'s coverage claim should be corrected to match.

---

## Repo

- Public: https://github.com/Mohamedhassan268/ai-guardian
- Latest commit: `a641192` — project progress report covering Phases 1-4.
