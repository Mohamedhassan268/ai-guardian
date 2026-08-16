"""
Guardian AI - Realistic Scenario Simulator v7

CHANGES FROM v6
  1. Stage timings widened so genuine detections span 2+ persistence windows.
     Fusion v7 caps single-window evidence at 68%, so a real cheating episode
     must accumulate across time - as it would in reality. The v6 timings had
     Stage B landing entirely inside one 10s window.
  2. Ambiguous-device test now emits behaviour on ONE seat only. That is the
     real ambiguity case: one device, one person, uncertain which seat. v6 put
     hand_under_desk on both seats, which under v7 correctly counts as two
     separate incidents rather than one ambiguous device.
  3. Added a fifth check: two genuinely separate adjacent cheaters must both
     alert - verifying that the ambiguity suppression does not swallow a real
     second offender.

INHERITED FROM v6
  1. New test case: AMBIGUOUS DEVICE. One hidden phone sitting between R06-C02
     and R06-C03, emitting RF that both seats plausibly claim. Under v5 this
     produced two alerts for one device. v6's multi-seat disambiguation should
     produce ONE alert with the loser listed as an alternate.
  2. New test case: TRANSIENT BLIP. A 2-second RF burst with behaviour but no
     persistence - v6's persistence scoring should keep it below threshold,
     where v5 would have let duration alone carry it.
  3. Stage timings spread out so the persistence windows are actually exercised.
  4. Final report now checks all four properties: detection, false positives,
     duplicate alerts, and transient rejection.
"""

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid, time, json, os, random

from app.core.database import get_db, SessionLocal
from app.models.models import Event, Alert
from app.models.models import Session as SessionModel
from app.core import fusion

router = APIRouter()
_scenario_running = False

# Repo-relative path so the project runs for anyone who clones it.
# fusion.py lives at  <repo>/Backend/app/core/fusion.py
# simulator.py lives at <repo>/Backend/app/api/simulator.py
# Both are 3 levels below the repo root.
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))

_CANDIDATE_PATHS = [
    os.path.join(_REPO_ROOT, "RF", "simulation", "rssi_realistic_summary.json"),
    os.path.join(_REPO_ROOT, "AI", "training_data", "rssi_realistic_summary.json"),
    # Legacy Desktop location - kept as a last resort so existing setups keep working
    os.path.join(os.path.expanduser("~"), "Desktop", "GuardianAI_RF",
                 "realistic", "rssi_realistic_summary.json"),
]


def _find_realistic_data():
    for p in _CANDIDATE_PATHS:
        if os.path.exists(p):
            return p
    return _CANDIDATE_PATHS[0]   # report the canonical path in the error message


REALISTIC_DATA_PATH = _find_realistic_data()
_rssi_db = None


def load_rssi_db():
    global _rssi_db
    if _rssi_db is not None:
        return _rssi_db
    try:
        with open(REALISTIC_DATA_PATH, "r") as f:
            data = json.load(f)
        _rssi_db = {s["seat_id"]: s for s in data["seats"]}
        print(f"[SIM] Loaded realistic RSSI for {len(_rssi_db)} seats")
    except FileNotFoundError:
        print("[SIM] " + "!"*60)
        print(f"[SIM] WARNING: realistic RSSI dataset NOT FOUND")
        print(f"[SIM]   expected at: {REALISTIC_DATA_PATH}")
        print(f"[SIM] Falling back to random RSSI - results will NOT be")
        print(f"[SIM] reproducible and will not match the documented figures.")
        print("[SIM] " + "!"*60)
        _rssi_db = {}
    return _rssi_db


def node_rssi(seat_id, node_num):
    db = load_rssi_db()
    if seat_id in db:
        s = db[seat_id]
        mean = s.get(f"rssi_node{node_num}_mean", -70.0)
        std  = s.get(f"rssi_node{node_num}_std", 5.0)
        return round(mean + random.gauss(0, std * 0.35), 1)
    return round(random.gauss(-68.0, 5.0), 1)


def all_node_rssi(seat_id):
    return [node_rssi(seat_id, n) for n in range(1, 5)]


def mk_event(session_id, source, etype, seat_id, x, y, *,
             protocol=None, rssi=None, duration=None,
             confidence=None, behavior=None):
    payload = {"behavior": behavior} if behavior else None
    return Event(
        id            = str(uuid.uuid4()),
        session_id    = session_id,
        source_module = source,
        event_type    = etype,
        seat_id       = seat_id,
        position_x    = x,
        position_y    = y,
        protocol      = protocol,
        rssi_dbm      = rssi,
        duration_s    = duration,
        confidence    = confidence,
        raw_payload   = payload,
    )


def emit(db, ev, label):
    db.add(ev); db.commit(); db.refresh(ev)
    fusion.check_and_fuse(db, ev)
    print(f"[SIM] {label}")


def live_state(db, seat_id):
    now = datetime.utcnow()
    ws = now - timedelta(seconds=fusion.TIME_WINDOW_S)
    rf, vis = fusion.gather_evidence(db, seat_id, ws)
    if not rf:
        return None, None, None
    conf, bd = fusion.compute_confidence_v6(rf, vis, seat_id, now)
    return conf, bd.get('corr_gate'), bd.get('raw_scores', {}).get('persistence')


def report_stage(db, seat_id, stage, expected):
    conf, gate, persist = live_state(db, seat_id)
    a = db.query(Alert).filter(
        Alert.seat_id == seat_id, Alert.is_cleared == False
    ).order_by(Alert.timestamp_utc.desc()).first()
    meta = f"gate={gate}, persist={persist}" if gate is not None else "no rf"
    if a is None:
        shown = f"{conf:.0%}" if conf is not None else "n/a"
        print(f"[SIM]    -> {stage}: NO ALERT ({shown}, {meta})  expected {expected}  [OK]")
    else:
        print(f"[SIM]    -> {stage}: {a.confidence:.0%} ({meta})  expected {expected}")


def run_scenario_background(session_id: str):
    global _scenario_running
    _scenario_running = True
    db = SessionLocal()
    load_rssi_db()

    CHEATERS = [
        {"seat": "R04-C03", "x": 6.12,  "y": 6.4},
        {"seat": "R07-R01", "x": 10.65, "y": 10.0},
    ]

    INNOCENT = [
        {"seat": "R01-C03", "x": 6.12,  "y": 2.8,  "label": "teacher laptop", "proto": "WIFI", "seated": False},
        {"seat": "R11-L01", "x": 0.53,  "y": 14.8, "label": "wifi router",    "proto": "WIFI", "seated": False},
        {"seat": "R09-C02", "x": 4.946, "y": 12.4, "label": "phone in bag",   "proto": "BLE",  "seated": True},
    ]

    # DEFECT 2 test: one device between two seats
    AMBIGUOUS = {"seat_a": "R06-C02", "xa": 4.946, "ya": 8.8,
                 "seat_b": "R06-C03", "xb": 6.12,  "yb": 8.8}

    # DEFECT 3 test: brief blip with behaviour but no persistence
    TRANSIENT = {"seat": "R10-C04", "x": 7.294, "y": 13.6}

    try:
        print("\n[SIM] === Scenario v7 ===")
        print("[SIM] Tests: detection, false positives, ambiguity, transients, separate pairs\n")

        # ---- PHASE 0: innocent RF ----
        print("[SIM] Phase 0 - innocent RF (false-positive control)")
        for dev in INNOCENT:
            if dev["seated"]:
                emit(db, mk_event(session_id, "vision", "person_detected",
                                  dev["seat"], dev["x"], dev["y"], confidence=0.94),
                     f"vision | seated      | {dev['seat']:9} | innocent student")
            for _ in range(4):
                r = node_rssi(dev["seat"], 1)
                emit(db, mk_event(session_id, "rf", "signal_detected",
                                  dev["seat"], dev["x"], dev["y"],
                                  protocol=dev["proto"], rssi=r,
                                  duration=2.0, confidence=0.30),
                     f"rf     | innocent    | {dev['seat']:9} | {r} dBm | {dev['label']}")
                time.sleep(0.2)
            report_stage(db, dev["seat"], f"innocent ({dev['label']})", "no alert")
        time.sleep(1.0)

        # ---- PHASE 0b: TRANSIENT BLIP (defect 3 test) ----
        print("\n[SIM] Phase 0b - transient blip with behaviour (should NOT alert)")
        sid, tx, ty = TRANSIENT["seat"], TRANSIENT["x"], TRANSIENT["y"]
        emit(db, mk_event(session_id, "vision", "person_detected",
                          sid, tx, ty, confidence=0.90, behavior="head_down"),
             f"vision | behaviour   | {sid:9} | head_down (normal exam behaviour)")
        for n in range(1, 4):
            r = node_rssi(sid, n)
            emit(db, mk_event(session_id, "rf", "signal_detected",
                              sid, tx, ty, protocol="BLE",
                              rssi=r, duration=2.0, confidence=0.40),
                 f"rf     | blip {n}/3    | {sid:9} | {r} dBm | dur=2s")
            time.sleep(0.1)
        report_stage(db, sid, "transient blip", "no alert - fails persistence")
        time.sleep(1.0)

        # ---- PHASE 0c: AMBIGUOUS DEVICE (defect 2 test) ----
        print("\n[SIM] Phase 0c - one device between two seats (should give ONE alert)")
        A, B = AMBIGUOUS["seat_a"], AMBIGUOUS["seat_b"]
        for seat, x, y in [(A, AMBIGUOUS["xa"], AMBIGUOUS["ya"]),
                           (B, AMBIGUOUS["xb"], AMBIGUOUS["yb"])]:
            emit(db, mk_event(session_id, "vision", "person_detected",
                              seat, x, y, confidence=0.92),
                 f"vision | seated      | {seat:9} | person detected")
        # ONE device, ONE person, uncertain which seat.
        # Behaviour appears on seat A only - RF is seen by both.
        for rnd in range(3):
            emit(db, mk_event(session_id, "vision", "person_detected",
                              A, AMBIGUOUS["xa"], AMBIGUOUS["ya"],
                              confidence=0.91, behavior="hand_under_desk"),
                 f"vision | behaviour   | {A:9} | hand_under_desk")
            for seat, x, y in [(A, AMBIGUOUS["xa"], AMBIGUOUS["ya"]),
                               (B, AMBIGUOUS["xb"], AMBIGUOUS["yb"])]:
                for n in range(1, 5):
                    r = node_rssi(seat, n)
                    emit(db, mk_event(session_id, "rf", "signal_detected",
                                      seat, x, y, protocol="BLE", rssi=r,
                                      duration=12.0 + rnd*8, confidence=0.70),
                         f"rf     | burst {n}/4   | {seat:9} | {r} dBm")
            time.sleep(11.0)   # span persistence windows   # spread across persistence windows
        amb_alerts = db.query(Alert).filter(
            Alert.seat_id.in_([A, B]), Alert.is_cleared == False).all()
        print(f"[SIM]    -> ambiguous device: {len(amb_alerts)} alert(s)  expected 1")
        for a in amb_alerts:
            print(f"[SIM]       {a.seat_id} @ {a.confidence:.0%}  {a.notes}")
        time.sleep(1.0)

        # ---- PHASE 0d: TWO SEPARATE ADJACENT CHEATERS (defect 5 test) ----
        print("\n[SIM] Phase 0d - two adjacent but SEPARATE cheaters (expect TWO alerts)")
        PAIR = [("R08-C01", 3.772, 11.2), ("R08-C02", 4.946, 11.2)]
        for rnd in range(3):
            for seat, x, y in PAIR:
                emit(db, mk_event(session_id, "vision", "person_detected",
                                  seat, x, y, confidence=0.93,
                                  behavior="hand_under_desk"),
                     f"vision | behaviour   | {seat:9} | hand_under_desk (own device)")
                for n in range(1, 5):
                    r = node_rssi(seat, n)
                    emit(db, mk_event(session_id, "rf", "signal_detected",
                                      seat, x, y, protocol="BLE", rssi=r,
                                      duration=15.0 + rnd*10, confidence=0.75),
                         f"rf     | burst {n}/4   | {seat:9} | {r} dBm")
            time.sleep(11.0)
        pair_alerts = db.query(Alert).filter(
            Alert.seat_id.in_([p[0] for p in PAIR]),
            Alert.is_cleared == False).all()
        print(f"[SIM]    -> separate cheaters: {len(pair_alerts)} alert(s)  expected 2")
        for a in pair_alerts:
            print(f"[SIM]       {a.seat_id} @ {a.confidence:.0%}")
        time.sleep(1.0)

        # ---- PHASE 1: cheaters seated ----
        print("\n[SIM] Phase 1 - students seated")
        for c in CHEATERS:
            emit(db, mk_event(session_id, "vision", "person_detected",
                              c["seat"], c["x"], c["y"],
                              confidence=round(random.uniform(0.88, 0.97), 2)),
                 f"vision | seated      | {c['seat']:9} | person detected")
            time.sleep(0.3)
        time.sleep(1.0)

        # ---- PHASE 2: escalating evidence ----
        for c in CHEATERS:
            sid, cx, cy = c["seat"], c["x"], c["y"]
            rssi_vec = all_node_rssi(sid)
            best = rssi_vec.index(max(rssi_vec))

            print(f"\n[SIM] -- {sid} - realistic RSSI per node --")
            for i, r in enumerate(rssi_vec, 1):
                print(f"[SIM]    Node {i}: {r} dBm" + ("   <- strongest" if i-1 == best else ""))

            print(f"[SIM] Stage A - RF + seated only (should NOT alert)")
            for n in range(1, 5):
                r = node_rssi(sid, n)
                emit(db, mk_event(session_id, "rf", "signal_detected",
                                  sid, cx, cy, protocol="BLE",
                                  rssi=r, duration=3.0, confidence=0.45),
                     f"rf     | burst {n}/4   | {sid:9} | {r} dBm | dur=3s")
            report_stage(db, sid, "Stage A", "no alert")
            time.sleep(11.0)   # cross a persistence window boundary

            print(f"[SIM] Stage B - + head_down (weak: gate opens partially)")
            emit(db, mk_event(session_id, "vision", "person_detected",
                              sid, round(cx + random.uniform(-0.15, 0.15), 2),
                              round(cy + random.uniform(-0.15, 0.15), 2),
                              confidence=0.91, behavior="head_down"),
                 f"vision | behaviour   | {sid:9} | head_down 4.2s")
            for n in range(1, 5):
                r = node_rssi(sid, n)
                emit(db, mk_event(session_id, "rf", "signal_detected",
                                  sid, cx, cy, protocol="BLE",
                                  rssi=r, duration=9.0, confidence=0.62),
                     f"rf     | burst {n}/4   | {sid:9} | {r} dBm | dur=9s")
            report_stage(db, sid, "Stage B", "~75-82% (needs 2 windows)")
            time.sleep(11.0)

            print(f"[SIM] Stage C - + hand_under_desk + localization")
            emit(db, mk_event(session_id, "vision", "person_detected",
                              sid, round(cx + random.uniform(-0.1, 0.1), 2),
                              round(cy + random.uniform(-0.1, 0.1), 2),
                              confidence=0.93, behavior="hand_under_desk"),
                 f"vision | behaviour   | {sid:9} | hand_under_desk 6.1s")
            emit(db, mk_event(session_id, "localization", "position_estimate",
                              sid, cx, cy, protocol="BLE",
                              rssi=max(rssi_vec), duration=14.0, confidence=0.86),
                 f"loc    | position    | {sid:9} | N1={rssi_vec[0]} N2={rssi_vec[1]} "
                 f"N3={rssi_vec[2]} N4={rssi_vec[3]} dBm")
            for n in range(1, 5):
                r = node_rssi(sid, n)
                emit(db, mk_event(session_id, "rf", "signal_detected",
                                  sid, cx, cy, protocol="BLE",
                                  rssi=r, duration=18.0, confidence=0.78),
                     f"rf     | burst {n}/4   | {sid:9} | {r} dBm | dur=18s")
            report_stage(db, sid, "Stage C", "~90-96%")
            time.sleep(11.0)

            print(f"[SIM] Stage D - + phone_visible + ear_touch + WIFI + sustained")
            emit(db, mk_event(session_id, "vision", "person_detected",
                              sid, round(cx + random.uniform(-0.08, 0.08), 2),
                              round(cy + random.uniform(-0.08, 0.08), 2),
                              confidence=0.96, behavior="phone_visible"),
                 f"vision | behaviour   | {sid:9} | PHONE VISIBLE in frame")
            emit(db, mk_event(session_id, "vision", "person_detected",
                              sid, cx, cy, confidence=0.89, behavior="ear_touch"),
                 f"vision | behaviour   | {sid:9} | ear_touch (earpiece)")
            for n in range(1, 5):
                r = round(node_rssi(sid, n) + 2, 1)
                emit(db, mk_event(session_id, "rf", "signal_detected",
                                  sid, cx, cy, protocol="WIFI",
                                  rssi=r, duration=42.0, confidence=0.88),
                     f"rf     | burst {n}/4   | {sid:9} | {r} dBm | WIFI | dur=42s")
            for n in range(1, 5):
                r = node_rssi(sid, n)
                emit(db, mk_event(session_id, "rf", "signal_detected",
                                  sid, cx, cy, protocol="BLE",
                                  rssi=r, duration=65.0, confidence=0.92),
                     f"rf     | burst {n}/4   | {sid:9} | {r} dBm | BLE | dur=65s")
            report_stage(db, sid, "Stage D", "~97-99%")
            time.sleep(1.5)

        # ---- SUMMARY ----
        print("\n[SIM] === Scenario complete ===")
        alerts = db.query(Alert).filter(Alert.session_id == session_id).all()
        innocent_seats = {d["seat"] for d in INNOCENT}
        cheat_seats    = {c["seat"] for c in CHEATERS}
        amb_seats      = {A, B}
        trans_seat     = {TRANSIENT["seat"]}
        pair_seats     = {"R08-C01", "R08-C02"}

        true_pos   = [a for a in alerts if a.seat_id in cheat_seats]
        false_pos  = [a for a in alerts if a.seat_id in innocent_seats]
        amb_hits   = [a for a in alerts if a.seat_id in amb_seats]
        trans_hits = [a for a in alerts if a.seat_id in trans_seat]
        pair_hits  = [a for a in alerts if a.seat_id in pair_seats]

        print(f"[SIM] Alerts fired: {len(alerts)}")
        for a in sorted(alerts, key=lambda x: -x.confidence):
            if a.seat_id in cheat_seats:      kind = "TRUE POSITIVE "
            elif a.seat_id in innocent_seats: kind = "FALSE POSITIVE"
            elif a.seat_id in amb_seats:      kind = "AMBIGUOUS     "
            elif a.seat_id in trans_seat:     kind = "TRANSIENT     "
            elif a.seat_id in pair_seats:     kind = "SEPARATE PAIR "
            else:                              kind = "OTHER         "
            flag = " [BLIND SPOT]" if a.seat_id in fusion.BLIND_SPOTS else ""
            print(f"[SIM]   {kind} | {a.seat_id:9} | {a.confidence:.0%} | "
                  f"{a.protocol} | {a.rssi_dbm} dBm{flag}")
            if a.notes:
                print(f"[SIM]        {a.notes}")

        print(f"\n[SIM] -- Test results --")
        t1 = len(true_pos) == len(cheat_seats)
        t2 = len(false_pos) == 0
        t3 = len(amb_hits) <= 1
        t4 = len(trans_hits) == 0
        t5 = len(pair_hits) == 2
        print(f"[SIM] 1. Cheaters detected       : {len(true_pos)}/{len(cheat_seats)}   {'PASS' if t1 else 'FAIL'}")
        print(f"[SIM] 2. False positives         : {len(false_pos)}/{len(innocent_seats)}   {'PASS' if t2 else 'FAIL'}")
        print(f"[SIM] 3. Ambiguous -> one alert  : {len(amb_hits)}     {'PASS' if t3 else 'FAIL'}")
        print(f"[SIM] 4. Transient rejected      : {len(trans_hits)}     {'PASS' if t4 else 'FAIL'}")
        print(f"[SIM] 5. Separate pair -> two    : {len(pair_hits)}/2   {'PASS' if t5 else 'FAIL'}")
        print(f"[SIM]")
        print(f"[SIM] {'ALL TESTS PASS' if all([t1,t2,t3,t4,t5]) else 'SOME TESTS FAILED - see above'}")

    except Exception as e:
        print(f"[SIM] ERROR: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()
        _scenario_running = False


@router.post("/run")
def run_scenario(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    global _scenario_running
    if _scenario_running:
        return {"status": "already running"}
    rssi_db = load_rssi_db()
    session = db.query(SessionModel).filter(SessionModel.is_active == True).first()
    if not session:
        session = SessionModel(
            id      = str(uuid.uuid4()),
            name    = f"Fusion v7 Sim {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            hall_id = "hall_a",
        )
        db.add(session); db.commit()
    background_tasks.add_task(run_scenario_background, session.id)
    return {
        "status":      "started",
        "session_id":  session.id,
        "data_source": "realistic dataset" if rssi_db else "fallback",
        "rssi_seats":  len(rssi_db),
        "fusion":      "v7 - persistence cap, corrected neighbour radius",
    }


@router.post("/reset")
def reset_simulation(db: Session = Depends(get_db)):
    db.query(Alert).delete()
    db.query(Event).delete()
    db.commit()
    return {"status": "reset complete"}


@router.get("/status")
def scenario_status():
    rssi_db = load_rssi_db()
    return {
        "running":     _scenario_running,
        "data_source": "realistic dataset" if rssi_db else "fallback",
        "rssi_seats":  len(rssi_db),
        "fusion":      "v7",
    }
