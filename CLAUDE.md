# Ai guardian

## Commands
<!-- No code exists yet — repo is at Phase 1 (Foundation & Data Contract). Fill in as each module comes online. -->
<!-- RF/: GNU Radio + Python (UHD Source -> Waterfall + File Sink) -->
<!-- Vision/: YOLOv8 + ByteTrack, PyTorch, OpenCV -->
<!-- DigitalTwin/: Unreal Engine 5 + Blender -->
<!-- Backend/: FastAPI + PostgreSQL (Phase 5) -->
<!-- Dashboard/: React (Phase 5) -->

## Architecture
Guardian AI is an AI-powered RF intelligence platform; first application is exam-hall
security (passive RF + vision detection of hidden devices/behavior).

- Simulation-first pipeline: Digital Twin -> synthetic data -> AI training -> real deployment.
- Repo layout (per plan, not yet scaffolded): `RF/ Vision/ DigitalTwin/ Fusion/ Backend/
  Dashboard/ AI/ Shared/ Docs/ ROADMAP.md`
- Three tracks, each owned by one person: RF Intelligence (GNU Radio, Python, USRP B210,
  Phase 3), Vision AI (YOLO, OpenCV, PyTorch, Phase 4), Digital Twin (Unreal Engine 5,
  Blender, Phase 2). Digital Twin starts first — it produces the coordinate system, seat
  map, and node placement everything else depends on.
- Phase 5 (Fusion & Platform) ties it together: real-time RF service over MQTT/ZeroMQ,
  a fusion engine doing spatial + temporal correlation, and FastAPI + PostgreSQL + React
  + Docker for the backend/dashboard.
- All modules emit a shared JSON event schema from day one (see Conventions).

## Conventions
- Coordinate system: origin front-left, X across rows, Y along rows, units in meters.
- Seat numbering: `Row-Seat` (e.g. `R4-S7`).
- Every module output uses this shared JSON event schema:
  ```json
  {
    "event_id": "uuid",
    "timestamp_utc": "2026-07-14T10:32:11.482Z",
    "source_module": "rf | vision | localization | fusion",
    "event_type": "signal_detected | person_detected | position_estimate | alert",
    "position": {"x": 3.2, "y": 5.1, "seat": "R4-S7", "error_m": 1.2},
    "signal": {"protocol": "BLE | WIFI | UNKNOWN", "freq_hz": 2437000000,
               "bandwidth_hz": 2000000, "rssi_dbm": -58, "duration_s": 18.2},
    "confidence": 0.94,
    "evidence_ref": "path/or/null"
  }
  ```
- RF tooling is GNU Radio + Python only for now — MATLAB and CST are deferred (see
  ROADMAP.md), not to be introduced without an explicit decision.
- Match RF signals to people by *timing* (e.g. signal appears when a hand moves under a
  desk), not position alone — this is the core disambiguation strategy for Phase 5 fusion.
- NTP-synced, UTC+ms timestamps across all nodes.

## Important
- **Phase 1 scope is frozen**: 2.4 GHz ISM band only, one room, RSSI localization, BLE +
  Wi-Fi classification. Any new idea outside this scope goes to `ROADMAP.md`, not into
  Phase 1 work — scope creep is the named top risk.
- Privacy constraint: passive sensing only, no demodulation of captured signals, and a
  retention policy must exist before any pilot deployment.
- Deferred/out of scope for now: MATLAB, CST, 5/6 GHz + Zigbee/LoRa/cellular, TDoA/AoA,
  full behavior AI, Transformers/autoencoders, expansion beyond exam halls (airports,
  hospitals, prisons).
- Success metrics to design/validate against: detection >90%, classification >90%,
  localization median error <2 m, correct-bench rate >80%, vision seat accuracy >90%,
  alert latency <5 s, false alerts <1/hr.
- Full plan: `Guardian AI – Master Execution Plan.pdf` in repo root.

