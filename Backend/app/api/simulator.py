"""
Guardian AI — Realistic Scenario Simulator v5

CHANGES FROM v4:
  1. Reports the behaviour gate value at each stage, so the proportional
     unlocking in fusion v5 is visible rather than inferred.
  2. Stage expectations updated to the v5 verified figures:
       Stage A  RF + seated        -> no alert  (~57%)
       Stage B  + head_down        -> alert     (~79%)
       Stage C  + hand_under_desk  -> alert     (~95%)
       Stage D  full corroboration -> alert     (~99%)
  3. Innocent set unchanged (teacher laptop, wifi router, seated student with
     phone in bag) — the third is the hardest false positive and the one that
     decides whether this is deployable in a real hall.
  4. Removed non-ASCII arrows/emoji from print statements — Windows consoles
     using cp1256 raised UnicodeEncodeError on those.
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

REALISTIC_DATA_PATH = os.path.join(
    os.path.expanduser("~"), "Desktop", "GuardianAI_RF",
    "realistic", "rssi_realistic_summary.json"
)
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
        print("[SIM] WARNING: realistic RSSI not found - using fallback")
        _rssi_db = {}
    return _rssi_db


def node_rssi(seat_id, node_num):
    """Per-node RSSI from the realistic dataset, plus live reading noise."""
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
    """Current confidence and the behaviour gate driving it."""
    window_start = datetime.utcnow() - timedelta(seconds=fusion.TIME_WINDOW_S)
    rf, vis = fusion.gather_evidence(db, seat_id, window_start)
    if not rf:
        return None, None
    conf, bd = fusion.compute_confidence_v5(rf, vis, seat_id)
    return conf, bd.get('corr_gate')


def report_stage(db, seat_id, stage, expected):
    conf, gate = live_state(db, seat_id)
    a = db.query(Alert).filter(
        Alert.seat_id == seat_id, Alert.is_cleared == False
    ).order_by(Alert.timestamp_utc.desc()).first()

    gate_s = f"gate={gate}" if gate is not None else "gate=-"
    if a is None:
        shown = f"{conf:.0%}" if conf is not None else "n/a"
        print(f"[SIM]    -> {stage}: NO ALERT ({shown}, {gate_s})  expected {expected}  [OK]")
    else:
        print(f"[SIM]    -> {stage}: {a.confidence:.0%} ({gate_s})  expected {expected}")


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

    try:
        print("\n[SIM] === Scenario v5 - proportional behaviour gating ===")
        print("[SIM] Weak behaviour earns partial corroboration; strong earns all.\n")

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
                time.sleep(0.15)
            report_stage(db, dev["seat"], f"innocent ({dev['label']})", "no alert")
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

            # Stage A - RF + seated only. Must NOT alert.
            print(f"[SIM] Stage A - RF + seated only (should NOT alert)")
            for n in range(1, 5):
                r = node_rssi(sid, n)
                emit(db, mk_event(session_id, "rf", "signal_detected",
                                  sid, cx, cy, protocol="BLE",
                                  rssi=r, duration=3.0, confidence=0.45),
                     f"rf     | burst {n}/4   | {sid:9} | {r} dBm | dur=3s")
            report_stage(db, sid, "Stage A", "no alert / ~57%")
            time.sleep(1.5)

            # Stage B - head_down (weak behaviour, partial gate)
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
            report_stage(db, sid, "Stage B", "~79%")
            time.sleep(1.5)

            # Stage C - hand_under_desk + localization
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
            report_stage(db, sid, "Stage C", "~95%")
            time.sleep(1.5)

            # Stage D - phone visible + dual protocol + sustained
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
            report_stage(db, sid, "Stage D", "~99%")
            time.sleep(1.5)

        # ---- SUMMARY ----
        print("\n[SIM] === Scenario complete ===")
        alerts = db.query(Alert).filter(Alert.session_id == session_id).all()
        innocent_seats = {d["seat"] for d in INNOCENT}
        cheat_seats    = {c["seat"] for c in CHEATERS}

        true_pos  = [a for a in alerts if a.seat_id in cheat_seats]
        false_pos = [a for a in alerts if a.seat_id in innocent_seats]

        print(f"[SIM] Alerts fired: {len(alerts)}")
        for a in sorted(alerts, key=lambda x: -x.confidence):
            kind = "TRUE POSITIVE " if a.seat_id in cheat_seats else "FALSE POSITIVE"
            flag = " [BLIND SPOT]" if a.seat_id in fusion.BLIND_SPOTS else ""
            print(f"[SIM]   {kind} | {a.seat_id:9} | {a.confidence:.0%} | "
                  f"{a.protocol} | {a.rssi_dbm} dBm{flag}")
            if a.notes:
                print(f"[SIM]        {a.notes}")

        print(f"\n[SIM] -- Test result --")
        print(f"[SIM] Cheaters detected : {len(true_pos)}/{len(cheat_seats)}")
        print(f"[SIM] False positives   : {len(false_pos)}/{len(innocent_seats)}")
        if len(true_pos) == len(cheat_seats) and not false_pos:
            print("[SIM] PASS - all cheaters caught, no innocent device alerted")
        elif false_pos:
            print("[SIM] FAIL - innocent devices triggered alerts:")
            for a in false_pos:
                print(f"[SIM]      {a.seat_id} at {a.confidence:.0%} - {a.notes}")
        else:
            print("[SIM] FAIL - some cheaters were missed")

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
            name    = f"Proportional Gate Sim {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            hall_id = "hall_a",
        )
        db.add(session); db.commit()

    background_tasks.add_task(run_scenario_background, session.id)
    return {
        "status":      "started",
        "session_id":  session.id,
        "data_source": "realistic dataset" if rssi_db else "fallback",
        "rssi_seats":  len(rssi_db),
        "fusion":      "v5 - proportional behaviour gating",
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
        "fusion":      "v5",
    }
