# Status

_Last updated: 2026-07-28_

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
before acquiring any real hardware. Real hardware (ESP32, IP camera) is added
only after the simulation demo is validated.

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
  Camera sits in the teacher zone at Y=2.60m, before the first student row (Y=2.80m).
- RF node placement: 4-corner layout confirmed across 7 tested configurations.
- 39,600-row clean synthetic RSSI dataset generated.
- **NEW:** 59,400-row *realistic* RSSI dataset with full impairment model.
- Generator scripts in `DigitalTwin/scripts/` — deterministic reruns (fixed seed).

### Deliverables

| File | Location | Consumer |
|---|---|---|
| seat_map.json | Shared/ | Everyone |
| rssi_dataset.csv (clean) | AI/training_data/ | Person 2 (AI) |
| rssi_fingerprint.json | AI/training_data/ | Person 2 (AI) |
| **rssi_realistic.csv** | AI/training_data/ | Person 2 — retrain on this |
| **rssi_realistic_summary.json** | RF/simulation/ | Simulator reads this |
| best_node_placement.json | DigitalTwin/rf_simulation/ | Everyone |

---

## RF Intelligence (Phase 3) — deferred, but realistic data model complete ✅

Real RF capture deferred until Phase 5 is complete. What exists now:

- Clean synthetic RSSI dataset (39,600 samples) ✅
- FingerprintKNN localization model — 0.0m median error, 94.9% correct-bench ✅
- **Realistic RSSI dataset (59,400 samples)** with a 10-impairment model ✅

### Realistic impairment model

| # | Impairment | Parameters |
|---|---|---|
| 1 | Thermal noise | σ = 3.0 dB |
| 2 | Multipath fading (Rician) | σ = 6.0 dB, K = 2.0 |
| 3 | Shadow fading (log-normal, spatially correlated) | σ = 4.0 dB |
| 4 | Human body blockage | 35% probability, 3–8 dB loss |
| 5 | BLE frequency-hop packet loss | 15% miss rate |
| 6 | Complete packet loss | 8% |
| 7 | Wi-Fi interference bursts | 5% probability, +8 dB |
| 8 | Temporal RSSI drift | σ = 2.0 dB |
| 9 | RSSI quantization | integer dBm (real hardware behaviour) |
| 10 | Saturation / noise floor | −30 dBm max, −95 dBm floor |

Combined noise ≈ 8.3 dB vs 3.0 dB in the clean dataset.
The simulator now draws per-node RSSI from this dataset rather than hardcoded values.

**Predicted degradation on real hardware:** median error 0.5–2.0 m,
correct-bench 70–90% (vs 0.0 m / 94.9% clean). To be confirmed in Phase 6.

**Deferred to Phase 6:** ESP32 hardware, real RSSI collection, USRP sub-GHz capture.

---

## Vision AI (Phase 4) — in progress

**Owner:** Person 2

- Pipeline: detection, homography, seat mapping, event emission, 30 tests passing.
- Camera coverage: 93/99 seats (93.9%) validated by `project_vision_dataset.py`.
- Geometry results: 100% correct seat, 0.194 m median error (220 people).
- Homography calibrated on the **bench plane (z=0.45 m)**, not the floor —
  floor calibration caused ~2.4 m error at the back rows.
- Full results: `Vision/perception/results/`

**These are geometry-only figures.** They assume perfect pixel input and include
no detector error, so they are not the >90% end-to-end target.

**Deferred to Phase 6:** IP camera, real footage, YOLO fine-tuning, ByteTrack,
real behaviour event detection.

---

## Fusion & Platform (Phase 5) — in progress 🔄

**Owner:** Both

### What is built and validated ✅

| Component | Status | Location |
|---|---|---|
| FastAPI backend | ✅ Running | `Backend/app/main.py` |
| SQLite database | ✅ Auto-created | `Backend/guardian_ai.db` |
| Event ingestion API | ✅ Working | `Backend/app/api/events.py` |
| Alerts API | ✅ Working | `Backend/app/api/alerts.py` |
| Sessions API | ✅ Working | `Backend/app/api/sessions.py` |
| **Fusion engine v5** | ✅ Validated | `Backend/app/core/fusion.py` |
| **Simulator v5** (realistic RSSI) | ✅ Validated | `Backend/app/api/simulator.py` |
| WebSocket live push | ✅ Connected | `Backend/app/api/ws.py` |
| Dashboard v3 | ✅ Live | `Dashboard/guardian_dashboard_v3.html` |

### Fusion engine v5 — multi-evidence, behaviour-gated

Eight evidence sources, each contributing to an explainable confidence score.
Every alert stores its full evidence breakdown so a decision can be audited.

| Evidence | Weight | Measures |
|---|---|---|
| RF signal present | 25% | Required — no RF, no alert |
| Localization quality | 15% | RSSI variance across the 4 nodes |
| Vision person at seat | 20% | Scaled 0.35→1.00 by behaviour strength |
| Behaviour evidence | 15% | phone_visible / ear_touch / hand_under_desk / head_down |
| Temporal correlation | 10% | Scaled 0.30→1.00 by behaviour strength |
| Signal duration + burst | 8% | Sustained TX + repeating advertisements |
| Protocol fingerprint | 5% | BLE+WIFI from one source = phone signature |
| Cross-sensor agreement | 7% | Scaled 0.30→1.00 by behaviour strength |

**Proportional behaviour gating (the key design decision).**
A seated person is true of all 99 seats, so presence alone must not raise an alert.
Presence-based weights start at a floor and unlock in proportion to how suspicious
the observed behaviour actually is:

```
vision_factor = 0.35 + 0.65 * behaviour_score
corr_gate     = 0.30 + 0.70 * behaviour_score
```

`head_down` (score 0.5, common during any exam) opens the gate to 0.65.
`phone_visible` (score 1.0) opens it fully. Two earlier iterations were rejected:
v3 alerted at 72% on RF + a seated person; v4 used a binary gate that let a single
`head_down` jump straight to 90%.

Alert thresholds: **70%** normal seats, **55%** blind-spot seats
(the 6 front-edge seats can never get Vision corroboration).

### Validated demo results (2026-07-28)

Graded scenario with two cheaters and three innocent RF sources:

| Stage | Evidence | Gate | R04-C03 | R07-R01 | Result |
|---|---|---|---|---|---|
| Innocent — teacher laptop | RF only | 0.30 | 45% | — | no alert ✅ |
| Innocent — wifi router | RF only | 0.30 | 45% | — | no alert ✅ |
| Innocent — **seated student, phone in bag** | RF + seated | 0.30 | 57% | — | no alert ✅ |
| Stage A | RF + seated | 0.30 | 57% | 48% | no alert ✅ |
| Stage B | + head_down | 0.65 | 79% | 74% | alert |
| Stage C | + hand_under_desk + localization | 0.91 | 96% | 92% | alert |
| Stage D | + phone_visible + ear_touch + WIFI | 1.00 | 99% | 99% | alert |

```
Cheaters detected : 2/2
False positives   : 0/3
PASS — all cheaters caught, no innocent device alerted
```

The third innocent case — a real seated student whose phone emits BLE from a bag —
is the hardest false positive in a real hall and the one this design most needed to
survive. It scored 57%, thirteen points below threshold.

### How to run

```bash
cd Backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `Dashboard/guardian_dashboard_v3.html` in Chrome. API docs at `/docs`.

### What remains for Phase 5

- [ ] Docker + PostgreSQL (upgrade from SQLite)
- [ ] docker-compose — one command to run the full system
- [ ] Evidence packaging (screenshot + RF snapshot + timestamp per alert)
- [ ] Surface the evidence breakdown in the dashboard alert card
- [ ] Sustained false-alert rate test (1-hour quiet-room run)

---

## Known issues / to revisit

- **`score_localization` penalises corner seats.** It reads RSSI variance across
  nodes as position uncertainty, but a seat next to one node legitimately produces
  high variance (R07-R01: −59 to −76 dBm). That seat scored Loc:0.10 vs R04-C03's
  0.15 and tracked 3–5 points lower at every stage. Both still alerted, but on real
  hardware the seats nearest a node will be systematically under-scored — exactly
  where localization should be most confident. Needs rework once real RSSI exists.
- **Fusion constants are provisional.** `BEHAVIOR_SCORES` and the gate floors are
  tuned against synthetic behaviour events that fire cleanly and on cue. Real YOLO
  pose estimation will produce noisy, intermittent, sometimes wrong detections.
  Expect to retune once real footage exists. The structure is sound; the numbers are not final.

---

## Hardware — all deferred to Phase 6

| Item | Qty | Status | When needed |
|---|---|---|---|
| USRP (50 MHz–2.2 GHz) | 1 | Owned — **cannot reach 2.4 GHz** | Phase 6 sub-GHz only |
| ESP32 dev board | 5 | To order (~$25) | 4× RSSI nodes + 1× BLE test beacon |
| IP Camera (Hikvision DS-2CD2143G2-I, 4MP PoE) | 1 | To buy (~$60–80) | Phase 6 real footage |
| PoE switch (4-port) | 1 | To buy (~$25) | Powers camera |
| Cat6 cable (5 m) | 1 | To buy (~$5) | Camera to switch |
| Laptop (Quadro M1200, Windows 10) | 1 | Ready — driver 582.70 | Dev machine |

**Minimum to begin RF testing: ~$25 (ESP32 only).** Full setup ~$115–135.

The USRP's 2.2 GHz ceiling means it cannot be used for 2.4 GHz work. ESP32 boards
replace it for this project — they have a native 2.4 GHz radio and report RSSI
directly, at roughly 1/60th the cost.

---

## Success metrics

| Metric | Target | Current | Measured in |
|---|---|---|---|
| Detection rate | >90% | Not yet measured | Phase 6 |
| Classification rate | >90% | Not yet measured | Phase 6 |
| Localization median error | <2 m | 0.0 m (clean sim) ✅ | Phase 6 real hardware |
| Correct-bench rate | >80% | 94.9% (clean sim) ✅ | Phase 6 real hardware |
| Vision seat accuracy | >90% | 100% geometry proxy (sim) | Phase 6 real footage |
| Alert latency | <5 s | Confirmed in demo ✅ | Phase 5 |
| False alerts | <1/hr | **0/3 in controlled test** ✅ | Phase 5 sustained run + Phase 6 |

Note: localization and correct-bench figures are from the *clean* dataset. The
realistic dataset has not yet been used to retrain the model — that is Person 2's
next task and will produce lower, more honest numbers.

---

## Open items

- **Person 2: retrain FingerprintKNN on `rssi_realistic.csv`** and report the
  degradation vs the clean dataset. This is the most informative outstanding task.
- Docker not yet installed — PostgreSQL migration and docker-compose blocked.
- Privacy/retention policy not yet drafted — required before any real pilot.
- `DigitalTwin/README.md` needs update to reflect the simulation-first strategy.
- Dashboard does not yet display the fusion evidence breakdown.
- All hardware deferred to Phase 6.

---

## Repo

- Public: https://github.com/Mohamedhassan268/ai-guardian
- Latest: Fusion v5 — proportional behaviour gating, validated 2/2 detection
  with 0/3 false positives against a controlled innocent-device set (2026-07-28).
