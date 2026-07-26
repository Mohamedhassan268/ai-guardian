# Status

_Last updated: 2026-07-26_

Snapshot of where each track stands. See `CLAUDE.md` for architecture/conventions
and `ROADMAP.md` for deferred/out-of-scope ideas.

---

## Team

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

- Full 3D exam hall modeled (12.2m x 17.8m x 4.0m), all 99 seats mapped.
- Camera confirmed: X=6.1m, Y=2.60m, Z=3.80m — 93/99 seats (93.9%) visible.
- RF node placement: 4-corner layout confirmed.
- 39,600-row synthetic RSSI dataset generated.
- Generator scripts in `DigitalTwin/scripts/` — deterministic reruns.

### Deliverables

| File | Location | Consumer |
|---|---|---|
| seat_map.json | Shared/ | Everyone |
| rssi_dataset.csv | AI/training_data/ | Person 2 (AI) |
| rssi_fingerprint.json | AI/training_data/ | Person 2 (AI) |
| best_node_placement.json | DigitalTwin/rf_simulation/ | Everyone |

---

## RF Intelligence (Phase 3) — deferred

Real RF capture deferred until Phase 5 simulation demo is complete.

**What exists:**
- Synthetic RSSI dataset (39,600 samples) ✅
- FingerprintKNN localization model — 0.0m median error, 94.9% correct-bench ✅

**Deferred to Phase 6:** ESP32 hardware, real RSSI collection, USRP capture.

---

## Vision AI (Phase 4) — in progress

**Owner:** Person 2

- Pipeline: detection, homography, seat mapping, event emission, 30 tests passing.
- Camera coverage: 93/99 seats (93.9%) validated.
- Geometry results: 100% correct seat, 0.194m median error (220 people).
- Full results: `Vision/perception/results/`

**Deferred to Phase 6:** IP camera, real footage, YOLO fine-tuning, ByteTrack, behavior events.

---

## Fusion & Platform (Phase 5) — in progress 🔄

**Owner:** Both
**Goal:** Full end-to-end simulation demo.

### What is built and validated ✅

| Component | Status | Location |
|---|---|---|
| FastAPI backend | ✅ Running | `Backend/app/main.py` |
| SQLite database | ✅ Auto-created | `Backend/guardian_ai.db` |
| Event ingestion API | ✅ Working | `Backend/app/api/events.py` |
| Alerts API | ✅ Working | `Backend/app/api/alerts.py` |
| Sessions API | ✅ Working | `Backend/app/api/sessions.py` |
| Fusion engine | ✅ Firing alerts | `Backend/app/core/fusion.py` |
| Scenario simulator | ✅ Working | `Backend/app/api/simulator.py` |
| WebSocket live push | ✅ Connected | `Backend/app/api/ws.py` |
| Dashboard v3 | ✅ Live | `Dashboard/guardian_dashboard_v3.html` |

### Validated demo results (2026-07-26)

End-to-end demo run confirmed:
- Backend online + WebSocket live (two green pills in dashboard)
- 99 seats rendered, bigger 26×26px seats with section labels
- BLE signal detected at R04-C03 → fusion → 94% confidence alert
- Second alert at R07-R01 → 87% confidence
- 15 events logged: RF / Vision / Fusion / Alert / System
- All alerts stored in SQLite database
- Real-time push via WebSocket (no polling delay)

### How to run

```bash
cd Backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `Dashboard/guardian_dashboard_v3.html` in Chrome.
API docs: `http://localhost:8000/docs`

### Demo scenario

```
T=0s:   99 students seated — all seats green
T=2s:   BLE burst at R04-C03 → seat yellow
T=5s:   Vision confirms person at R04-C03
T=9s:   Fusion: confidence 89%
T=11s:  ALERT R04-C03 → red → 94% confidence
T=13s:  Second BLE at R07-R01
T=17s:  ALERT R07-R01 → red → 87% confidence
```

### Fusion engine logic

Matches RF and Vision events by timing (30s window) not position alone.
Confidence threshold: 70%. Weights: RF=40%, Vision=30%, Temporal=20%, Duration=10%.

### What remains for Phase 5

- [ ] Docker + PostgreSQL (upgrade from SQLite)
- [ ] docker-compose — one command to run full system
- [ ] Evidence packaging (screenshot + RF snapshot + timestamp)

---

## Hardware — all deferred to Phase 6

| Item | Status | When needed |
|---|---|---|
| USRP (50 MHz–2.2 GHz) | Owned — cannot reach 2.4 GHz | Phase 6 sub-GHz only |
| ESP32 x4 | To order (~$20) | Phase 6 real RSSI |
| HackRF / RTL-SDR | Decision deferred | Phase 6 optional IQ capture |
| IP Camera x1 | To buy | Phase 6 real footage |
| Laptop (Quadro M1200, Windows 10) | Ready — driver 582.70 | Dev machine |

---

## Success metrics

| Metric | Target | Current | Measured in |
|---|---|---|---|
| Detection rate | >90% | Not yet measured | Phase 6 |
| Classification rate | >90% | Not yet measured | Phase 6 |
| Localization median error | <2 m | 0.0 m (sim) ✅ | Phase 6 real hardware |
| Correct-bench rate | >80% | 94.9% (sim) ✅ | Phase 6 real hardware |
| Vision seat accuracy | >90% | 100% geometry proxy (sim) | Phase 6 real footage |
| Alert latency | <5 s | Confirmed in demo ✅ | Phase 5 |
| False alerts | <1/hr | Not yet measured | Phase 5 load test |

---

## Open items

- Docker not yet installed — PostgreSQL migration and docker-compose blocked.
- Privacy/retention policy not yet drafted — required before any real pilot.
- `DigitalTwin/README.md` needs update to reflect simulation-first strategy.
- All hardware deferred to Phase 6.

---

## Repo

- Public: https://github.com/Mohamedhassan268/ai-guardian
- Latest: Phase 5 in progress — end-to-end simulation demo validated 2026-07-26.
