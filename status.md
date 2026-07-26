# Status

_Last updated: 2026-07-26_

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
- Camera position confirmed and validated: X=6.1m, Y=2.60m, Z=3.80m
  (front-center ceiling, FOV=110°, 93/99 seats visible).
- The three generator scripts behind all of the above (Blender hall builder, RF
  node-placement optimizer, RF propagation simulator) are now committed under
  `DigitalTwin/scripts/`, with repo-relative paths and a fixed RNG seed so
  reruns are reproducible.
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

### Hardware status

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

4 ESP32 nodes deployed → real RSSI collected at 20+ seat positions →
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
  the COCO "person" class. Not trained or fine-tuned on exam-hall-specific data.
- 30 pytest tests pass, validating pipeline logic against synthetic coordinates.

### Camera position — confirmed and validated ✅

After testing multiple positions, the camera is confirmed at:

| Parameter | Value |
|---|---|
| Position | X=6.1m, Y=2.60m, Z=3.80m |
| FOV | 110° horizontal |
| Coverage | 93/99 seats (93.9%) |
| Blind spots | 6 front-edge seats (rows 1-2 edges) |
| Blind spot decision | Accepted for Phase 1 — teacher presence covers those seats |
| Second camera | Deferred to Phase 6 |

Coverage validated by `DigitalTwin/scripts/project_vision_dataset.py` at 50° pitch.
See `Vision/perception/results/seat_coverage_map.png`.

### Synthetic dataset + geometry results (updated) ✅

| Metric | Result |
|---|---|
| Frame coverage | 93/99 seats (93.9%) — up from 84/99 after camera Z raised to 3.80m |
| Correct seat (geometry only) | 100.0% over 220 people |
| Median position error | 0.194 m |
| Mean position error | 0.207 m |
| Single / multi occupancy | 100% / 100% |

**These are geometry-only results** — homography and seat-mapping chain given
perfect pixel input, no detection error included. Not the >90% vision seat
accuracy target, which requires a real detector on real footage.

The homography is calibrated on the bench plane (z=0.45m), not the floor —
this was a real defect found and fixed during evaluation (floor calibration
causes ~2.4m error at back rows).

Full results package: `Vision/perception/results/`

### Next steps

1. Buy IP camera (see Hardware) — place at confirmed position.
2. Run pretrained YOLOv8 on real frames to get true end-to-end accuracy.
3. Set up ByteTrack multi-frame tracking once live stream exists.
4. Output behavior events (head-down, hand-under-desk) as JSON.

**Waiting on:** IP camera purchase.

---

## Fusion & Platform (Phase 5) — not started

- Real-time RF service over MQTT/ZeroMQ.
- Fusion engine: spatial + temporal correlation (signal-to-person matching by
  timing, not position alone).
- Backend/dashboard: FastAPI + PostgreSQL + React + Docker.
- Evidence packaging: video clip + RF snapshot + timestamp.
- **Can proceed now** against the shared event schema using synthetic events
  from both `AI/localization` and `Vision/perception` — not blocked on hardware.

---

## Hardware

| Item | Status | Purpose |
|---|---|---|
| USRP (50 MHz – 2.2 GHz) | Owned — cannot reach 2.4 GHz | Sub-2.2 GHz spectrum capture only |
| ESP32 x4 | To order (~$20 total) | 3x RSSI nodes + 1x BLE beacon — primary 2.4 GHz capture |
| HackRF / RTL-SDR | To decide | Optional: 2.4 GHz IQ capture if needed |
| IP Camera x1 | To buy | Vision AI — Hikvision/Dahua 4MP PoE, place at (6.1, 2.60, 3.80m) |
| Laptop (Quadro M1200, Windows 10) | Ready — driver updated to 582.70 | Development machine |

---

## Success metrics (from CLAUDE.md)

| Metric | Target | Current | Measured in |
|---|---|---|---|
| Detection rate | >90% | Not yet measured | Phase 3 |
| Classification rate | >90% | Not yet measured | Phase 3 |
| Localization median error | <2 m | 0.0 m (sim, FingerprintKNN, window=40) ✅ | Phase 3 real hardware |
| Correct-bench rate | >80% | 94.9% (sim, FingerprintKNN) ✅ | Phase 3 real hardware |
| Vision seat accuracy | >90% | Geometry-only proxy: 100% (no detection error). End-to-end: not yet measured | Phase 4 real footage |
| Alert latency | <5 s | Not yet measured | Phase 5 |
| False alerts | <1/hr | Not yet measured | Phase 5 |

---

## Open items

- ESP32 boards not yet ordered (Phase 3 blocker — primary 2.4 GHz capture tool).
- USRP frequency limitation: max 2.2 GHz — decision needed on HackRF/RTL-SDR for IQ capture.
- `DigitalTwin/README.md` needs update to reflect ESP32 capture strategy.
- Privacy/retention policy for captured signals not yet drafted — required before any pilot.
- Real RF hardware (Phase 3) is the current blocker for validating simulated localization numbers.
- IP camera not yet purchased (Phase 4 blocker for real footage).
- Phase 5 can start now — not blocked on hardware.

---

## Repo

- Public: https://github.com/Mohamedhassan268/ai-guardian
- Latest commit: Camera confirmed Z=3.80m, 93/99 coverage validated, Vision results updated.
