# Status
_Last updated: 2026-07-22_

Snapshot of where each track stands. See `CLAUDE.md` for architecture/conventions
and `ROADMAP.md` for deferred/out-of-scope ideas.

---

## Phase / track progress

| Phase | Track | Owner | Status |
|---|---|---|---|
| Phase 1 — Scope | (all) | — | Frozen: 2.4 GHz ISM, one room, RSSI localization, BLE + Wi-Fi classification |
| Phase 2 — Digital Twin | Digital Twin | Person 1 | Complete ✅ |
| Phase 3 — RF Intelligence | RF | Person 1 | In progress |
| Phase 4 — Vision AI | Vision | Person 2 | Not started |
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
**Goal:** Capture real RF data with USRP B210 + GNU Radio to validate and
replace the simulated dataset from Phase 2.

### Environment
- OS: Windows 10 64-bit
- Hardware: USRP B210 (70 MHz – 6 GHz, covers 2.4 GHz natively)
- Software: GNU Radio, Python 3.x, NumPy, SciPy

### Immediate tasks
1. Install GNU Radio + UHD drivers for B210 on Windows
2. Build capture flowgraph: UHD Source → 20 MHz at 2.437 GHz → Waterfall + File Sink
3. Flash ESP32 as BLE advertising beacon (test transmitter)
4. Confirm BLE bursts visible at 2402 / 2426 / 2480 MHz in waterfall
5. Record IQ datasets: quiet room / BLE on / Wi-Fi on
6. Build Python energy detector (burst → JSON event)
7. Build rule-based classifier (BLE / Wi-Fi / Unknown)
8. Deploy 4 ESP32 RSSI nodes at confirmed positions
9. Collect real RSSI fingerprint data
10. Compare real vs simulated RSSI — validate Digital Twin accuracy

### Current blockers
- GNU Radio not yet installed on Windows
- ESP32 not yet flashed as BLE beacon

### Next milestone
Hidden BLE beacon in room → detected → localized to correct bench → logged as JSON event

### Expected deliverables

| Deliverable | Consumer |
|---|---|
| Real IQ recordings (quiet / BLE / Wi-Fi) | RF/data/ |
| Labeled spectrogram dataset (500+ per class) | Person 2 (AI) — replaces synthetic |
| Real RSSI fingerprint dataset (20+ positions) | Person 2 (AI) — validates simulation |
| Energy detector script (burst → JSON event) | Phase 5 fusion engine |
| Rule-based classifier (BLE / Wi-Fi / Unknown) | Phase 5 fusion engine |
| Real vs simulated RSSI comparison report | Everyone |

---

## Vision AI (Phase 4) — not started

**Owner:** Person 2
**Waiting on:** seat_map.json (delivered ✅), YOLOv8 environment setup

### Next steps
1. Set up YOLOv8 person detection + ByteTrack tracking.
2. Implement homography: camera pixel position → (x, y) hall coordinate.
3. Map detected people to seat IDs via `Shared/seat_map.json`.
4. Output behavior events (head-down duration, hand-under-desk) as JSON.

---

## Fusion & Platform (Phase 5) — not started

- Real-time RF service over MQTT/ZeroMQ.
- Fusion engine: spatial + temporal correlation (signal-to-person matching by
  timing, not position alone).
- Backend/dashboard: FastAPI + PostgreSQL + React + Docker.
- Evidence packaging: video clip + RF snapshot + timestamp.

---

## Hardware

| Item | Status | Purpose |
|---|---|---|
| USRP B210 | Owned and ready | Main spectrum capture — 2.4 GHz, 20 MHz bandwidth |
| ESP32 x4 | To order | 3x RSSI scanner nodes + 1x BLE test beacon |
| IP Camera x1 | To buy (Phase 4) | Vision AI — Hikvision/Dahua 4MP PoE recommended |
| Laptop (Quadro M1200) | Ready — driver updated to 582.70 | Development machine |

---

## Success metrics (from CLAUDE.md)

| Metric | Target | Current | Measured in |
|---|---|---|---|
| Detection rate | >90% | Not yet measured | Phase 3 |
| Classification rate | >90% | Not yet measured | Phase 3 |
| Localization median error | <2 m | 0.0 m (sim only, 4-corner config) | Phase 3 real hardware |
| Correct-bench rate | >80% | 100% (sim only) | Phase 3 real hardware |
| Vision seat accuracy | >90% | Not yet measured | Phase 4 |
| Alert latency | <5 s | Not yet measured | Phase 5 |
| False alerts | <1/hr | Not yet measured | Phase 5 |

---

## Open items

- GNU Radio not yet installed on Windows (Phase 3 blocker).
- ESP32 BLE beacon not yet flashed (Phase 3 blocker).
- `DigitalTwin/README.md` not yet written — referenced above but missing from repo.
- Privacy/retention policy for captured signals must exist before any pilot
  deployment (passive sensing only, no demodulation) — not yet drafted.
- Real RF hardware capture (Phase 3) is the current blocker for validating
  Digital Twin's simulated localization numbers.

---

## Repo

- Public: https://github.com/Mohamedhassan268/ai-guardian
- Latest commit: `f9160a9` — Phase 2 Digital Twin deliverables (seat map, RF simulation, training data).
