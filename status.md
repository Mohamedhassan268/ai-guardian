# Status

_Last updated: 2026-07-29_

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
before acquiring any real hardware.

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
  Sits in the teacher zone at Y=2.60m, before the first student row (Y=2.80m).
- RF node placement: 4-corner layout confirmed across 7 tested configurations.
- 39,600-row clean synthetic RSSI dataset.
- 59,400-row *realistic* RSSI dataset with a 10-impairment model.
- Generator scripts in `DigitalTwin/scripts/` — deterministic reruns (fixed seed).

### Deliverables

| File | Location | Consumer |
|---|---|---|
| seat_map.json | Shared/ | Everyone |
| rssi_dataset.csv (clean) | AI/training_data/ | Person 2 (AI) |
| rssi_fingerprint.json | AI/training_data/ | Person 2 (AI) |
| rssi_realistic.csv | AI/training_data/ | Person 2 — retrain on this |
| rssi_realistic_summary.json | RF/simulation/ | Simulator + fusion read this |
| best_node_placement.json | DigitalTwin/rf_simulation/ | Everyone |

---

## RF Intelligence (Phase 3) — deferred, realistic data model complete ✅

- Clean synthetic RSSI dataset (39,600 samples) ✅
- FingerprintKNN localization model — 0.0 m median error, 94.9% correct-bench ✅
- Realistic RSSI dataset (59,400 samples), 10-impairment model ✅

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
| 9 | RSSI quantization | integer dBm |
| 10 | Saturation / noise floor | −30 dBm max, −95 dBm floor |

Combined noise ≈ 8.3 dB vs 3.0 dB clean. The simulator and the fusion engine's
localization scorer both read from this dataset.

**Predicted degradation on real hardware:** median error 0.5–2.0 m,
correct-bench 70–90%. To be confirmed in Phase 6.

**Deferred to Phase 6:** ESP32 hardware, real RSSI collection, USRP sub-GHz capture.

---

## Vision AI (Phase 4) — in progress

**Owner:** Person 2

- Pipeline: detection, homography, seat mapping, event emission, 30 tests passing.
- Camera coverage: 93/99 seats (93.9%).
- Geometry results: 100% correct seat, 0.194 m median error (220 people).
- Homography calibrated on the **bench plane (z=0.45 m)**, not the floor —
  floor calibration caused ~2.4 m error at the back rows.

**These are geometry-only figures** — perfect pixel input, no detector error.
They are not the >90% end-to-end target.

**Deferred to Phase 6:** IP camera, real footage, YOLO fine-tuning, ByteTrack,
real behaviour event detection.

---

## Fusion & Platform (Phase 5) — in progress 🔄

### What is built and validated ✅

| Component | Status | Location |
|---|---|---|
| FastAPI backend | ✅ Running | `Backend/app/main.py` |
| SQLite database | ✅ Auto-created | `Backend/guardian_ai.db` |
| Event ingestion API | ✅ Working | `Backend/app/api/events.py` |
| Alerts API | ✅ Working | `Backend/app/api/alerts.py` |
| Sessions API | ✅ Working | `Backend/app/api/sessions.py` |
| **Fusion engine v7** | ✅ 5/5 tests pass | `Backend/app/core/fusion.py` |
| **Simulator v7** | ✅ 5-check graded test | `Backend/app/api/simulator.py` |
| WebSocket live push | ✅ Connected | `Backend/app/api/ws.py` |
| Dashboard v3 | ✅ Live | `Dashboard/guardian_dashboard_v3.html` |
| RSSI fingerprint data | ✅ Committed | `RF/simulation/rssi_realistic_summary.json` |

### Fusion engine v7 — eight evidence sources

Every alert stores its full evidence breakdown, so a decision is auditable
rather than a bare confidence number.

| Evidence | Weight | Measures |
|---|---|---|
| RF signal present | 25% | Required — no RF, no alert |
| Localization quality | 15% | Fingerprint match against expected RSSI vector |
| Vision person at seat | 20% | Scaled 0.35→1.00 by behaviour strength |
| Behaviour evidence | 15% | phone_visible / ear_touch / hand_under_desk / head_down |
| Temporal correlation | 10% | Scaled 0.30→1.00 by behaviour strength |
| Duration + burst + persistence | 8% | Sustained TX, repeating advertisements |
| Protocol fingerprint | 5% | BLE+WIFI from one source = phone signature |
| Cross-sensor agreement | 7% | Scaled 0.30→1.00 by behaviour strength |

**Three mechanisms carry most of the reliability:**

1. **Proportional behaviour gating.** A seated person is true of all 99 seats, so
   presence alone must not raise an alert. Presence weights start at a floor and
   unlock in proportion to how suspicious the behaviour actually is:
   `vision_factor = 0.35 + 0.65 × behaviour`, `corr_gate = 0.30 + 0.70 × behaviour`.
   `head_down` (0.5 — common in any exam) opens the gate to 0.65; `phone_visible`
   (1.0) opens it fully.

2. **Persistence ceiling.** Sustained-ness caps the maximum achievable confidence:
   1 window → 0.68 (below threshold, always), 2 windows → 0.93, 3+ → 0.99.
   Strong evidence is not punished; it must simply persist, as real cheating does
   and a brief phone wake-up does not.

3. **Multi-seat disambiguation.** Candidate seats within 1.5 m are scored jointly
   and one alert is emitted for the best match — *unless* both seats have their own
   independent behaviour evidence, in which case they are separate incidents.

Thresholds: **70%** normal seats, **55%** blind-spot seats (the 6 front-edge seats
can never get Vision corroboration).

### Validated test results (2026-07-29, confirmed across two runs)

Graded scenario: 2 cheaters, 3 innocent RF sources, 1 transient blip,
1 ambiguous device, 1 pair of genuinely separate adjacent cheaters.

| # | Check | Result |
|---|---|---|
| 1 | Cheaters detected | **2/2** PASS |
| 2 | False positives | **0/3** PASS |
| 3 | Ambiguous device → one alert | **1** PASS |
| 4 | Transient blip rejected | **0** PASS |
| 5 | Separate adjacent pair → two alerts | **2/2** PASS |

**ALL TESTS PASS.**

Confidence ladder for a cheater:

| Stage | Evidence | Gate | Persist | Confidence |
|---|---|---|---|---|
| A | RF + seated | 0.30 | 0.25 | 45–57% — no alert |
| B | + head_down | 0.63 | 0.60 | 78% — alert |
| C | + hand_under_desk + localization | 0.85 | 1.00 | 88–90% |
| D | + phone_visible + ear_touch + WIFI | 1.00 | 1.00 | 99% |

Innocent controls: teacher laptop 41-45%, wifi router 37%,
**seated student with phone in bag 57%** — the hardest case, 13 points clear.

Reproduced twice with independent random RSSI draws, identical 5/5 result.
Two passes matter more than one here: it means the thresholds are not sitting
on a knife edge where noise decides the outcome.

The fingerprint dataset is committed at `RF/simulation/rssi_realistic_summary.json`
and resolved by a repo-relative path (with the old Desktop location kept as a
fallback), so the repo is self-contained and a clone reproduces these results.
A missing file now prints a loud boxed warning naming both consequences —
localization silently falling back to the variance heuristic, and multi-seat
disambiguation switching off — because silent degradation is more dangerous
than an outright failure.

### Version history — each fix came from a test failure, not a feature request

| Version | Defect found | Fix |
|---|---|---|
| v3 | Alerted at 72% on RF + a merely-seated person — would have fired on all 99 seats | Gate presence weights behind behaviour |
| v4 | Binary gate: one `head_down` jumped straight to 90% | Make the gate proportional to behaviour strength |
| v5 | Corner seats penalised — lopsided RSSI read as "uncertain" when it is the most informative profile | Fingerprint matching instead of variance |
| v6 | 2-second blip alerted at 76%; neighbour radius 2.5 m spanned rows | Persistence ceiling; radius 1.5 m + independent-behaviour guard |
| v7 | — | 5/5 tests pass |

A flat persistence multiplier was tried and rejected: it dragged a genuine
Stage B detection from 78% to 52%.

### How to run

```bash
cd Backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `Dashboard/guardian_dashboard_v3.html` in Chrome. API docs at `/docs`.
The scenario takes ~3 minutes — the delays are deliberate so persistence
windows fill as they would in a real exam.

### What remains for Phase 5

- [ ] Docker + PostgreSQL (upgrade from SQLite)
- [ ] docker-compose — one command to run the full system
- [ ] Evidence packaging (screenshot + RF snapshot + timestamp per alert)
- [ ] Surface the evidence breakdown in the dashboard alert card
- [ ] Sustained false-alert rate test (1-hour quiet-room run)

---

## Known issues / to revisit

- **Fusion constants are provisional, and this is the most important caveat in
  this document.** The structure has now survived five adversarial tests; the
  constants have survived none. `BEHAVIOR_SCORES`, the gate floors, and the
  persistence thresholds are tuned against synthetic behaviour events that fire
  cleanly and on cue. Real YOLO pose estimation is intermittent, noisy, and
  sometimes wrong. Expect to retune all of them against real footage.

- **Adding a second protocol degrades localization.** At Stage D the WIFI bursts
  carry `rssi + 2`, pushing the observed vector away from the seat's BLE
  fingerprint — `Loc` fell from 0.15 to 0.11. It cost nothing because everything
  else was saturated, but the direction is wrong: more evidence from the same
  device should not reduce positional confidence. Proper fix is per-protocol
  fingerprints, which needs the `node_id` column below.

- **Event schema has no `node_id`.** Fingerprint matching currently compares
  *sorted* RSSI values, so it captures the shape of a profile but not which node
  is strongest — two seats with mirrored profiles could match equally well.
  Adding `node_id` to the Event model fixes this properly and becomes necessary
  anyway when real ESP32 data arrives.

- **Persistence ceiling may become the binding constraint.** Most detections sit
  at `persist=0.6` (ceiling 0.93). If thresholds rise or the gate widens, that
  ceiling — not the evidence — will limit confidence.

---

## Hardware — all deferred to Phase 6

| Item | Qty | Status | Purpose |
|---|---|---|---|
| USRP (50 MHz–2.2 GHz) | 1 | Owned — **cannot reach 2.4 GHz** | Sub-GHz only |
| ESP32 dev board | 5 | To order (~$25) | 4× RSSI nodes + 1× BLE test beacon |
| IP Camera (Hikvision DS-2CD2143G2-I, 4MP PoE) | 1 | To buy (~$60–80) | Real footage |
| PoE switch (4-port) | 1 | To buy (~$25) | Powers camera |
| Cat6 cable (5 m) | 1 | To buy (~$5) | Camera to switch |
| Laptop (Quadro M1200, Windows 10) | 1 | Ready | Dev machine |

**Minimum to begin RF testing: ~$25 (ESP32 only).** Full setup ~$115–135.

The USRP's 2.2 GHz ceiling means it cannot be used for 2.4 GHz work. ESP32 boards
replace it — native 2.4 GHz radio, RSSI reported directly, ~1/60th the cost.

---

## Success metrics

| Metric | Target | Current | Measured in |
|---|---|---|---|
| Detection rate | >90% | 2/2 in controlled test | Phase 6 |
| Classification rate | >90% | Not yet measured | Phase 6 |
| Localization median error | <2 m | 0.0 m (clean sim) ✅ | Phase 6 real hardware |
| Correct-bench rate | >80% | 94.9% (clean sim) ✅ | Phase 6 real hardware |
| Vision seat accuracy | >90% | 100% geometry proxy (sim) | Phase 6 real footage |
| Alert latency | <5 s | Confirmed ✅ | Phase 5 |
| False alerts | <1/hr | 0/3 in controlled test ✅ | Phase 5 sustained run + Phase 6 |

Localization and correct-bench figures are from the *clean* dataset. The realistic
dataset has not yet been used to retrain the model — that will produce lower,
more honest numbers.

---

## Open items

- **Person 2: retrain FingerprintKNN on `rssi_realistic.csv`** and report the
  degradation vs the clean dataset. Most informative outstanding task.
- Add `node_id` to the Event model (unblocks proper fingerprint matching).
- Docker not yet installed — PostgreSQL migration and docker-compose blocked.
- Privacy/retention policy not yet drafted — required before any real pilot.
- `DigitalTwin/README.md` needs update to reflect simulation-first strategy.
- Dashboard does not yet display the fusion evidence breakdown.
- All hardware deferred to Phase 6.
- `rssi_realistic.csv` (9.7 MB) is only needed for model training, not at
  runtime — the 68 KB summary JSON is what the backend reads.

---

## Repo

- Public: https://github.com/Mohamedhassan268/ai-guardian
- Latest: Fusion v7 — persistence ceiling + corrected neighbour radius,
  repo-relative data path. 5/5 graded tests pass, reproduced twice (2026-07-29).
