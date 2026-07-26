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
| Phase 3 — RF Intelligence | RF | Person 1 | Deferred — simulation first |
| Phase 4 — Vision AI | Vision | Person 2 | In progress |
| Phase 5 — Fusion & Platform | Fusion/Backend/Dashboard | Both | Starting now |
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

### New order of work

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

**Decision:** Real RF capture deferred until Phase 5 simulation demo is complete
and validated. No hardware needed until then.

**What exists:**
- Synthetic RSSI dataset (39,600 samples) — used by AI/localization model ✅
- FingerprintKNN localization model trained and passing targets ✅
- Energy detector and classifier: to be built in Phase 5 against synthetic events

**What is deferred:**
- ESP32 hardware purchase
- Real RSSI fingerprint collection
- USRP spectrum capture
- HackRF/RTL-SDR decision

**When Phase 3 resumes (Phase 6):**
1. Order 4x ESP32 (~$20 total)
2. Flash BLE beacon + RSSI scanner firmware
3. Deploy at confirmed corner positions
4. Collect real RSSI — replace synthetic dataset
5. Revalidate FingerprintKNN on real data

---

## Vision AI (Phase 4) — in progress

**Owner:** Person 2

- Pipeline scaffolded in `Vision/perception/`: detection, homography,
  seat mapping, event emission, tests.
- 30 pytest tests passing.
- Synthetic geometry results validated (see below).

### Camera position — confirmed ✅

| Parameter | Value |
|---|---|
| Position | X=6.1m, Y=2.60m, Z=3.80m |
| FOV | 110° horizontal |
| Coverage | 93/99 seats (93.9%) |
| Blind spots | 6 front-edge seats — accepted for Phase 1 (teacher presence covers them) |
| Second camera | Deferred to Phase 6 |

### Synthetic geometry results ✅

| Metric | Result |
|---|---|
| Frame coverage | 93/99 seats (93.9%) |
| Correct seat (geometry only) | 100.0% over 220 people |
| Median position error | 0.194 m |
| Single / multi occupancy | 100% / 100% |

Geometry-only — no detection error included. Full results: `Vision/perception/results/`.

**What is deferred to Phase 6:**
- IP camera purchase
- Real footage capture
- YOLOv8 fine-tuning on real frames
- ByteTrack multi-frame tracking
- Behavior event detection (head-down, hand-under-desk)

---

## Fusion & Platform (Phase 5) — starting now ✅

**Owner:** Both
**Goal:** Build the complete end-to-end system running entirely on synthetic
data — looks and behaves exactly like the real system.

### What the simulation demo will show

```
Synthetic RF events       Synthetic Vision events
(AI/localization)    +    (Vision/perception)
        ↓                        ↓
        └──────  Fusion Engine  ─┘
                     ↓
             Confidence Score
                     ↓
           React Dashboard
    ┌──────────────────────────┐
    │  Live Hall Map           │
    │  ● ● ● ● ● ● ● ● ●      │
    │  ● ● ●[!]● ● ● ● ●      │  ← alert at R04-C03
    │                          │
    │  ALERT: R04-C03          │
    │  Protocol: BLE           │
    │  Confidence: 94%         │
    │  Duration: 18s           │
    └──────────────────────────┘
```

### Components to build

| Component | Owner | Purpose |
|---|---|---|
| Event simulator | Person 1 | Generates synthetic RF + Vision JSON events in real time |
| FastAPI backend | Person 1 | Receives events, stores in DB, exposes API |
| PostgreSQL schema | Person 1 | Events, sessions, alerts, evidence tables |
| Fusion engine | Person 2 | Correlates RF + Vision by time + position → confidence |
| React dashboard | Person 2 | Live hall map, alerts, event log, evidence panel |
| Docker-compose | Both | One command runs the entire system |

### Demo scenario (runs automatically)

```
T=0s:   99 seats shown green (empty)
T=5s:   BLE signal near R04-C03 → seat turns yellow
T=8s:   Vision confirms person at R04-C03
T=12s:  Signal continues → confidence rises to 94%
T=18s:  ALERT fired → seat turns red → evidence saved
```

### Stack

- Backend: Python + FastAPI
- Database: PostgreSQL
- Message bus: ZeroMQ or MQTT
- Frontend: React
- Deployment: Docker + docker-compose
- No Unreal Engine, no Blender, no hardware needed

### Person 1 immediate tasks

1. Install FastAPI + PostgreSQL + Docker
2. Build event simulator (synthetic RF + Vision JSON events)
3. Build FastAPI backend + database schema
4. Expose REST API for fusion engine and dashboard

### Person 2 immediate tasks

1. Build fusion engine (spatial + temporal correlation → confidence)
2. Build React dashboard (hall map + alerts + event log)
3. Wire everything together with docker-compose

---

## Hardware — all deferred to Phase 6

| Item | Status | When needed |
|---|---|---|
| USRP (50 MHz – 2.2 GHz) | Owned — cannot reach 2.4 GHz | Phase 6 sub-GHz only |
| ESP32 x4 | To order when Phase 6 starts | Phase 6 real RSSI |
| HackRF / RTL-SDR | Decision deferred | Phase 6 optional IQ capture |
| IP Camera x1 | To buy when Phase 6 starts | Phase 6 real footage |

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

- Phase 5 not yet started — starting now (highest priority).
- Privacy/retention policy not yet drafted — required before any real pilot.
- `DigitalTwin/README.md` needs update to reflect simulation-first strategy.
- All hardware deferred to Phase 6 — no purchases needed until Phase 5 demo is validated.

---

## Repo

- Public: https://github.com/Mohamedhassan268/ai-guardian
- Latest commit: Camera confirmed Z=3.80m, 93/99 coverage, simulation-first strategy adopted.
