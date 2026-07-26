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
| Fusion & Platform | Both |

---

## Phase / track progress

| Phase | Track | Owner | Status |
|---|---|---|---|
| Phase 1 — Scope | (all) | — | Frozen: 2.4 GHz ISM, one room, RSSI localization, BLE + Wi-Fi classification |
| Phase 2 — Digital Twin | Digital Twin | Person 1 | Complete ✅ |
| Phase 3 — RF Intelligence | RF | Person 1 | Deferred — simulation first |
| Phase 4 — Vision AI | Vision | Person 2 | In progress |
| Phase 5 — Fusion & Platform | Fusion/Backend/Dashboard | Both | In progress 🔄 |
| Phase 6 — Real Hardware | RF + Vision | Both | Not started |

---

## Strategy Decision — Simulation First

**Decision (2026-07-26):** Complete the full end-to-end system in simulation
before acquiring any real hardware. Real hardware (ESP32, IP camera, HackRF)
is added only after the simulation demo is validated and working.

### Rationale
- Both AI/localization and Vision/perception already produce synthetic JSON
  events in the shared schema — Phase 5 can consume them immediately.
- Validating the fusion logic, backend, and dashboard on synthetic data is
  faster and cheaper than waiting for hardware.
- When real hardware arrives, it replaces synthetic event sources with no
  change to the fusion engine or dashboard.

### Order of work

```
Phase 5: Full simulation demo (current priority)
      ↓
Phase 4 completion: YOLO on real camera footage
      ↓
Phase 6: Replace synthetic RF with real ESP32 RSSI data
      ↓
Phase 6: Replace synthetic Vision with real camera footage
      ↓
Full real-hardware validated system
```

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
- Generator scripts committed under `DigitalTwin/scripts/` with repo-relative
  paths and fixed RNG seed — reruns are deterministic.
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

## RF Intelligence (Phase 3) — deferred

**Decision:** Real RF capture deferred until Phase 5 simulation demo is
complete and validated. No hardware needed until then.

**What exists now:**
- Synthetic RSSI dataset (39,600 samples) ✅
- FingerprintKNN localization model trained and passing targets ✅
- Energy detector and classifier: to be built in Phase 5 against synthetic events

**What is deferred to Phase 6:**
- ESP32 hardware purchase (~$20 for 4 boards)
- Real RSSI fingerprint collection
- USRP spectrum capture (note: available USRP covers 50 MHz–2.2 GHz only)
- HackRF/RTL-SDR decision for 2.4 GHz IQ capture

---

## Vision AI (Phase 4) — in progress

**Owner:** Person 2

- Pipeline scaffolded in `Vision/perception/`: detection, homography,
  seat mapping, event emission, tests.
- 30 pytest tests passing.
- Synthetic geometry results validated.

### Camera position — confirmed ✅

| Parameter | Value |
|---|---|
| Position | X=6.1m, Y=2.60m, Z=3.80m |
| FOV | 110° horizontal |
| Coverage | 93/99 seats (93.9%) — validated by project_vision_dataset.py |
| Blind spots | 6 front-edge seats — accepted (teacher presence covers them) |
| Second camera | Deferred to Phase 6 |

### Synthetic geometry results ✅

| Metric | Result |
|---|---|
| Frame coverage | 93/99 seats (93.9%) |
| Correct seat (geometry only) | 100.0% over 220 people |
| Median position error | 0.194 m |
| Single / multi occupancy | 100% / 100% |

Full results: `Vision/perception/results/`

**What is deferred to Phase 6:**
- IP camera purchase
- Real footage capture
- YOLOv8 fine-tuning on real frames
- ByteTrack multi-frame tracking
- Behavior event detection (head-down, hand-under-desk)

---

## Fusion & Platform (Phase 5) — in progress 🔄

**Owner:** Both
**Goal:** Full end-to-end simulation demo — looks and behaves like the real system.

### What is built

| Component | Status | Location |
|---|---|---|
| FastAPI backend | ✅ Built | `Backend/app/main.py` |
| SQLite database | ✅ Built | `Backend/guardian_ai.db` (auto-created) |
| Event ingestion API | ✅ Built | `Backend/app/api/events.py` |
| Alerts API | ✅ Built | `Backend/app/api/alerts.py` |
| Sessions API | ✅ Built | `Backend/app/api/sessions.py` |
| Fusion engine | ✅ Built | `Backend/app/core/fusion.py` |
| Scenario simulator | ✅ Built | `Backend/app/api/simulator.py` |
| WebSocket live feed | ✅ Built | `Backend/app/api/ws.py` |
| React dashboard | ✅ Built | `Dashboard/guardian_dashboard_v2.html` |

### How to run

```bash
cd Backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then open `Dashboard/guardian_dashboard_v2.html` in browser.
API docs at `http://localhost:8000/docs`.

### Demo scenario

```
T=0s:   99 students seated — all seats green
T=2s:   BLE burst detected near R04-C03 → seat yellow
T=5s:   Vision confirms person at R04-C03
T=9s:   Fusion: confidence 89%
T=11s:  ALERT fired → R04-C03 red → 94% confidence
T=13s:  Second BLE burst near R07-R01
T=17s:  Second ALERT fired → R07-R01 red → 87% confidence
```

### Fusion engine logic

Matches RF and Vision events by **timing** (within 30s window) not position
alone — a BLE signal that appears when a hand moves under the desk is the
real evidence. Confidence threshold for alert: 70%.

### What remains for Phase 5

- [ ] Connect dashboard WebSocket to backend for true real-time push
- [ ] PostgreSQL migration (currently SQLite) — needs Docker
- [ ] Docker-compose to run full system with one command
- [ ] Evidence packaging (screenshot + RF snapshot + timestamp)
- [ ] React rebuild of dashboard (currently vanilla HTML)

---

## Hardware — all deferred to Phase 6

| Item | Status | When needed |
|---|---|---|
| USRP (50 MHz–2.2 GHz) | Owned — cannot reach 2.4 GHz | Phase 6 sub-GHz only |
| ESP32 x4 | To order when Phase 6 starts (~$20) | Phase 6 real RSSI |
| HackRF / RTL-SDR | Decision deferred | Phase 6 optional IQ capture |
| IP Camera x1 | To buy when Phase 6 starts | Phase 6 real footage |
| Laptop (Quadro M1200, Windows 10) | Ready — driver 582.70 | Development machine |

---

## Success metrics (from CLAUDE.md)

| Metric | Target | Current | Measured in |
|---|---|---|---|
| Detection rate | >90% | Not yet measured | Phase 6 real hardware |
| Classification rate | >90% | Not yet measured | Phase 6 real hardware |
| Localization median error | <2 m | 0.0 m (sim) ✅ | Phase 6 real hardware |
| Correct-bench rate | >80% | 94.9% (sim) ✅ | Phase 6 real hardware |
| Vision seat accuracy | >90% | Geometry proxy 100% (sim) | Phase 6 real footage |
| Alert latency | <5 s | Not yet measured | Phase 5 demo |
| False alerts | <1/hr | Not yet measured | Phase 5 demo |

---

## Open items

- Phase 5 WebSocket real-time push not yet connected to dashboard.
- Docker not yet installed — PostgreSQL migration blocked.
- Privacy/retention policy not yet drafted — required before any real pilot.
- `DigitalTwin/README.md` needs update to reflect simulation-first strategy.
- All hardware deferred to Phase 6.

---

## Repo

- Public: https://github.com/Mohamedhassan268/ai-guardian
- Latest: Phase 5 in progress — Backend + Dashboard built, simulation demo working.
