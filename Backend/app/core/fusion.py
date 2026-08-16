"""
Guardian AI — Fusion Engine v5 (Proportional Behaviour Gating)

HISTORY OF FIXES
  v3: fired 72% on RF + a merely-seated person. Every one of the 99 seats has a
      seated person, so this would have alerted on the whole hall.
  v4: gated the presence bonuses behind behaviour. Fixed the v3 bug, but the gate
      was BINARY — the instant any behaviour appeared, all 0.37 of presence weight
      unlocked at once. A single `head_down` (the weakest behaviour, score 0.5)
      pushed R04-C03 to 90%, when ~76% was intended. Students look down at their
      paper constantly during an exam; that must not carry the same weight as a
      phone being visibly held.
  v5: the gate is now PROPORTIONAL to behaviour strength.

        vision_factor = 0.35 + 0.65 * s_beh
        corr_gate     = 0.30 + 0.70 * s_beh

      s_beh = 0.0 (seated only)     → vision 0.35, corr 0.30  → no alert
      s_beh = 0.5 (head_down)       → vision 0.68, corr 0.65  → ~76-80%
      s_beh = 1.0 (phone_visible)   → vision 1.00, corr 1.00  → ~95-99%

      Weak behaviour earns partial corroboration. Strong behaviour earns all of it.

CONFIDENCE BUDGET (max 100%, clamped to 0.99):
  RF signal present         25%   required — no RF, no alert
  Localization quality      15%   RSSI variance across the 4 nodes
  Vision person at seat     20%   x(0.35 → 1.00) scaled by behaviour strength
  Behaviour evidence        15%   phone_visible / ear_touch / hand_under_desk / head_down
  Temporal correlation      10%   x(0.30 → 1.00) scaled by behaviour strength
  Signal duration + burst    8%
  Protocol fingerprint       5%
  Cross-sensor agreement     7%   x(0.30 → 1.00) scaled by behaviour strength

EXPECTED OUTCOMES
  RF only, no person                  ~30-40%   no alert
  RF + seated person, no behaviour    ~45-52%   no alert
  RF + head_down (weak)               ~74-80%   alert
  RF + hand_under_desk + localization ~86-93%   alert
  Full corroboration                  ~95-99%   alert
"""

from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
from datetime import datetime, timedelta
import uuid, math, statistics

from app.models.models import Event, Alert

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

TIME_WINDOW_S        = 30.0
MIN_RF_DURATION_S    = 5.0
CONFIDENCE_THRESHOLD = 0.70    # normal seats
BLIND_SPOT_THRESHOLD = 0.55    # blind-spot seats: Vision impossible, RF+duration must carry it

# Camera blind spots — 6 front-edge seats (validated 93/99 coverage)
BLIND_SPOTS = {
    'R01-L01', 'R01-C01', 'R01-C05', 'R01-R02',
    'R02-L01', 'R02-R02',
}

# ── WEIGHTS ──
W_RF_PRESENT    = 0.25
W_LOCALIZATION  = 0.15
W_VISION_PERSON = 0.20
W_BEHAVIOR      = 0.15
W_TEMPORAL      = 0.10
W_DURATION      = 0.08
W_PROTOCOL      = 0.05
W_CROSS_SENSOR  = 0.07

MAX_CONFIDENCE  = 0.99   # never claim certainty

# ── PROPORTIONAL BEHAVIOUR GATING (the v5 fix) ──
# Floor = what presence evidence is worth with NO behaviour at all.
# The remainder is unlocked in proportion to behaviour strength.
VISION_FLOOR = 0.35   # merely-seated earns 35% of Vision weight
CORR_FLOOR   = 0.30   # temporal + cross-sensor floor before behaviour

# ── BEHAVIOUR SCORES ──
BEHAVIOR_SCORES = {
    'phone_visible':     1.00,   # strongest — device actually seen in frame
    'ear_touch':         0.80,   # earpiece suspected
    'hand_under_desk':   0.70,
    'head_down':         0.50,   # weak on its own — students read their papers
    'suspicious_motion': 0.40,
}

# ── RSSI VARIANCE (localization quality) ──
RSSI_VAR_EXCELLENT = 5.0
RSSI_VAR_GOOD      = 8.0
RSSI_VAR_POOR      = 12.0

# ── BURST PATTERN ──
BURST_COUNT_HIGH = 20
BURST_COUNT_MED  = 10

# ── CROSS-SENSOR AGREEMENT ──
CROSS_DIST_TIGHT = 0.5
CROSS_DIST_LOOSE = 1.2


# ─────────────────────────────────────────────
# EVIDENCE SCORERS  (each returns 0.0 – 1.0)
# ─────────────────────────────────────────────

def score_localization(rf_events):
    """Low RSSI variance across nodes = confident position estimate."""
    vals = [e.rssi_dbm for e in rf_events if e.rssi_dbm is not None]
    if len(vals) < 2:
        return 0.35
    try:
        var = statistics.stdev(vals)
    except statistics.StatisticsError:
        return 0.35
    if var <= RSSI_VAR_EXCELLENT: return 1.00
    if var <= RSSI_VAR_GOOD:      return 0.70
    if var <= RSSI_VAR_POOR:      return 0.40
    return 0.15


def score_behavior(vision_events):
    """
    Strongest behaviour counts fully; additional distinct behaviours add with
    diminishing return. Returns 0.0 if the Vision pipeline reported nothing
    suspicious — a seated person is not behaviour.
    """
    seen = set()
    for ev in vision_events:
        payload = ev.raw_payload or {}
        beh = payload.get('behavior') or payload.get('event_subtype')
        if beh in BEHAVIOR_SCORES:
            seen.add(beh)
        for key in BEHAVIOR_SCORES:
            if key in (ev.event_type or ''):
                seen.add(key)
    if not seen:
        return 0.0
    scores = sorted((BEHAVIOR_SCORES[b] for b in seen), reverse=True)
    total = scores[0]
    for s in scores[1:]:
        total += s * 0.35
    return min(1.0, total)


def score_temporal(rf_events, vision_events):
    """Smallest RF-to-Vision time gap. 0s = 1.0, 30s = 0.0."""
    if not rf_events or not vision_events:
        return 0.0
    best = None
    for rf in rf_events:
        if not rf.timestamp_utc:
            continue
        for vs in vision_events:
            if not vs.timestamp_utc:
                continue
            d = abs((rf.timestamp_utc - vs.timestamp_utc).total_seconds())
            if best is None or d < best:
                best = d
    if best is None or best > TIME_WINDOW_S:
        return 0.0
    return 1.0 - (best / TIME_WINDOW_S)


def score_duration(rf_events):
    """Sustained transmission is far more suspicious than a single blip."""
    durs = [e.duration_s for e in rf_events if e.duration_s]
    if not durs:
        return 0.0
    d = max(durs)
    if d >= 60: return 1.00
    if d >= 30: return 0.85
    if d >= 15: return 0.65
    if d >= MIN_RF_DURATION_S: return 0.40
    return 0.15


def score_burst_pattern(rf_events):
    """Repeating advertisements = intentional transmitter, not random noise."""
    n = len(rf_events)
    if n >= BURST_COUNT_HIGH: return 1.00
    if n >= BURST_COUNT_MED:  return 0.65
    if n >= 4:                return 0.35
    return 0.10


def score_protocol(rf_events):
    """BLE and WIFI from the same seat is a strong phone signature."""
    protos = {e.protocol for e in rf_events if e.protocol}
    if not protos:
        return 0.0
    if 'BLE' in protos and 'WIFI' in protos:
        return 1.00
    if 'BLE' in protos or 'WIFI' in protos:
        return 0.75
    return 0.30


def score_cross_sensor(rf_events, vision_events):
    """Independent sensors agreeing on position is powerful corroboration."""
    rf_pts  = [(e.position_x, e.position_y) for e in rf_events
               if e.position_x is not None and e.position_y is not None]
    vis_pts = [(e.position_x, e.position_y) for e in vision_events
               if e.position_x is not None and e.position_y is not None]
    if not rf_pts or not vis_pts:
        return 0.0
    rx = sum(p[0] for p in rf_pts) / len(rf_pts)
    ry = sum(p[1] for p in rf_pts) / len(rf_pts)
    vx = sum(p[0] for p in vis_pts) / len(vis_pts)
    vy = sum(p[1] for p in vis_pts) / len(vis_pts)
    dist = math.hypot(rx - vx, ry - vy)
    if dist <= CROSS_DIST_TIGHT: return 1.00
    if dist <= CROSS_DIST_LOOSE: return 0.60
    if dist <= 2.5:              return 0.25
    return 0.0


# ─────────────────────────────────────────────
# CONFIDENCE CALCULATION
# ─────────────────────────────────────────────

def compute_confidence_v5(rf_events, vision_events, seat_id=None):
    """
    Returns (confidence, breakdown).
    The breakdown is stored on the alert so an operator can see exactly which
    evidence drove the score — the decision is explainable, not a bare number.
    """
    if not rf_events:
        return 0.0, {}

    s_loc   = score_localization(rf_events)
    s_beh   = score_behavior(vision_events)
    s_temp  = score_temporal(rf_events, vision_events)
    s_dur   = score_duration(rf_events)
    s_burst = score_burst_pattern(rf_events)
    s_proto = score_protocol(rf_events)
    s_cross = score_cross_sensor(rf_events, vision_events)

    has_vision = len(vision_events) > 0

    # ── THE v5 PROPORTIONAL GATE ──
    # Presence is true of every occupied seat, so it starts at a floor and is
    # unlocked in proportion to how suspicious the observed behaviour actually is.
    vision_factor = VISION_FLOOR + (1.0 - VISION_FLOOR) * s_beh
    corr_gate     = CORR_FLOOR   + (1.0 - CORR_FLOOR)   * s_beh

    conf = 0.0
    conf += W_RF_PRESENT
    conf += W_LOCALIZATION  * s_loc
    conf += W_VISION_PERSON * (vision_factor if has_vision else 0.0)
    conf += W_BEHAVIOR      * s_beh
    conf += W_TEMPORAL      * s_temp  * corr_gate
    conf += W_DURATION      * (s_dur * 0.7 + s_burst * 0.3)
    conf += W_PROTOCOL      * s_proto
    conf += W_CROSS_SENSOR  * s_cross * corr_gate

    conf = round(min(conf, MAX_CONFIDENCE), 3)

    breakdown = {
        'rf_present':     round(W_RF_PRESENT, 3),
        'localization':   round(W_LOCALIZATION * s_loc, 3),
        'vision_person':  round(W_VISION_PERSON * (vision_factor if has_vision else 0.0), 3),
        'behavior':       round(W_BEHAVIOR * s_beh, 3),
        'temporal':       round(W_TEMPORAL * s_temp * corr_gate, 3),
        'duration_burst': round(W_DURATION * (s_dur*0.7 + s_burst*0.3), 3),
        'protocol':       round(W_PROTOCOL * s_proto, 3),
        'cross_sensor':   round(W_CROSS_SENSOR * s_cross * corr_gate, 3),
        'vision_factor':  round(vision_factor, 2),
        'corr_gate':      round(corr_gate, 2),
        'raw_scores': {
            'localization': round(s_loc, 2),
            'behavior':     round(s_beh, 2),
            'temporal':     round(s_temp, 2),
            'duration':     round(s_dur, 2),
            'burst':        round(s_burst, 2),
            'protocol':     round(s_proto, 2),
            'cross_sensor': round(s_cross, 2),
        },
        'rf_event_count':     len(rf_events),
        'vision_event_count': len(vision_events),
        'blind_spot':         seat_id in BLIND_SPOTS if seat_id else False,
    }
    return conf, breakdown


# Backward-compatible aliases
compute_confidence_v4 = compute_confidence_v5
compute_confidence_v3 = compute_confidence_v5

def compute_confidence(rf_event, vision_event):
    rf  = [rf_event] if rf_event else []
    vis = [vision_event] if vision_event else []
    conf, _ = compute_confidence_v5(rf, vis)
    return conf


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def parse_seat(seat_id):
    """R04-C03 -> (4, 'Center')"""
    row = section = None
    try:
        row = int(seat_id[1:3])
        section = {'L': 'Left', 'C': 'Center', 'R': 'Right'}.get(seat_id[4])
    except Exception:
        pass
    return row, section


def gather_evidence(db, seat_id, window_start):
    events = db.query(Event).filter(
        Event.seat_id == seat_id,
        Event.timestamp_utc >= window_start,
    ).all()
    rf     = [e for e in events if e.source_module == 'rf']
    vision = [e for e in events if e.source_module in ('vision', 'localization')]
    return rf, vision


def threshold_for(seat_id):
    """Blind-spot seats can never get Vision corroboration, so they use a lower bar."""
    return BLIND_SPOT_THRESHOLD if seat_id in BLIND_SPOTS else CONFIDENCE_THRESHOLD


def _format_breakdown(b):
    if not b:
        return ''
    parts = [
        f"RF:{b.get('rf_present',0):.2f}",
        f"Loc:{b.get('localization',0):.2f}",
        f"Vis:{b.get('vision_person',0):.2f}",
        f"Beh:{b.get('behavior',0):.2f}",
        f"Temp:{b.get('temporal',0):.2f}",
        f"Dur:{b.get('duration_burst',0):.2f}",
        f"Proto:{b.get('protocol',0):.2f}",
        f"Cross:{b.get('cross_sensor',0):.2f}",
    ]
    gate = f" (gate={b.get('corr_gate','?')})"
    tag  = ' [BLIND SPOT]' if b.get('blind_spot') else ''
    return ' | '.join(parts) + gate + tag


def _alert_to_dict(a):
    return {
        'id': a.id, 'session_id': a.session_id,
        'timestamp_utc': str(a.timestamp_utc) if a.timestamp_utc else None,
        'seat_id': a.seat_id, 'row': a.row, 'section': a.section,
        'protocol': a.protocol, 'rssi_dbm': a.rssi_dbm,
        'duration_s': a.duration_s, 'confidence': a.confidence,
        'is_cleared': a.is_cleared,
        'blind_spot': a.seat_id in BLIND_SPOTS,
    }


async def _broadcast_alert(alert):
    from app.api.ws import manager
    await manager.send_alert(_alert_to_dict(alert))


def _build_alert(db, seat_id, rf_events, vision_events, confidence,
                 breakdown, session_id):
    window_start = datetime.utcnow() - timedelta(seconds=TIME_WINDOW_S)
    existing = db.query(Alert).filter(
        Alert.seat_id == seat_id,
        Alert.is_cleared == False,
        Alert.timestamp_utc >= window_start,
    ).first()

    if existing:
        if confidence > existing.confidence:
            existing.confidence = confidence
            existing.notes = _format_breakdown(breakdown)
            db.commit()
            print(f"   -> {seat_id} confidence raised to {confidence:.0%}")
        return None

    strongest = max(rf_events, key=lambda e: (e.rssi_dbm or -999))
    row, section = parse_seat(seat_id)

    alert = Alert(
        id              = str(uuid.uuid4()),
        session_id      = session_id,
        seat_id         = seat_id,
        row             = row,
        section         = section,
        protocol        = strongest.protocol,
        rssi_dbm        = strongest.rssi_dbm,
        duration_s      = max((e.duration_s or 0) for e in rf_events),
        confidence      = confidence,
        rf_event_id     = strongest.id,
        vision_event_id = vision_events[0].id if vision_events else None,
        notes           = _format_breakdown(breakdown),
    )
    db.add(alert); db.commit(); db.refresh(alert)
    return alert


def _print_alert(seat_id, confidence, breakdown, strongest):
    blind = ' [BLIND SPOT - RF only]' if seat_id in BLIND_SPOTS else ''
    print(f"\n*** ALERT: {seat_id} | confidence={confidence:.0%} | "
          f"{strongest.protocol} | {strongest.rssi_dbm} dBm{blind}")
    print(f"    Evidence: {_format_breakdown(breakdown)}")
    rs = breakdown.get('raw_scores', {})
    print(f"    RF events: {breakdown.get('rf_event_count')} | "
          f"Vision events: {breakdown.get('vision_event_count')} | "
          f"loc={rs.get('localization')} beh={rs.get('behavior')} "
          f"temp={rs.get('temporal')} cross={rs.get('cross_sensor')}")


# ─────────────────────────────────────────────
# PUBLIC API — sync (simulator)
# ─────────────────────────────────────────────

def check_and_fuse(db: Session, new_event: Event):
    if not new_event.seat_id:
        return
    seat_id = new_event.seat_id
    window_start = datetime.utcnow() - timedelta(seconds=TIME_WINDOW_S)
    rf_events, vision_events = gather_evidence(db, seat_id, window_start)
    if not rf_events:
        return
    confidence, breakdown = compute_confidence_v5(rf_events, vision_events, seat_id)
    if confidence >= threshold_for(seat_id):
        alert = _build_alert(db, seat_id, rf_events, vision_events,
                             confidence, breakdown, new_event.session_id)
        if alert:
            strongest = max(rf_events, key=lambda e: (e.rssi_dbm or -999))
            _print_alert(seat_id, confidence, breakdown, strongest)


# ─────────────────────────────────────────────
# PUBLIC API — async (events endpoint, broadcasts over WebSocket)
# ─────────────────────────────────────────────

async def check_and_fuse_async(db: Session, new_event: Event,
                                background_tasks: BackgroundTasks):
    if not new_event.seat_id:
        return
    seat_id = new_event.seat_id
    window_start = datetime.utcnow() - timedelta(seconds=TIME_WINDOW_S)
    rf_events, vision_events = gather_evidence(db, seat_id, window_start)
    if not rf_events:
        return
    confidence, breakdown = compute_confidence_v5(rf_events, vision_events, seat_id)
    if confidence >= threshold_for(seat_id):
        alert = _build_alert(db, seat_id, rf_events, vision_events,
                             confidence, breakdown, new_event.session_id)
        if alert:
            strongest = max(rf_events, key=lambda e: (e.rssi_dbm or -999))
            _print_alert(seat_id, confidence, breakdown, strongest)
            background_tasks.add_task(_broadcast_alert, alert)
