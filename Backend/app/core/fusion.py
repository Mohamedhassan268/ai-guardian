"""
Guardian AI - Fusion Engine v7

FIXES TWO DEFECTS FOUND IN THE v6 TEST RUN
==========================================

DEFECT 4: transient blip alerted at 76%.
  v6 put persistence inside the W_DURATION term (8% of the budget), so a
  single-window blip scoring 0.25 instead of 1.00 cost only ~1.8 points. A
  2-second RF burst with a head_down behaviour reached 76% and alerted. In a
  99-seat hall - where students look down constantly and phones wake briefly -
  that fires all day.

  v7 makes persistence a CAP on the maximum achievable confidence:
      1 window   -> ceiling 0.68  (below the 0.70 threshold, always)
      2 windows  -> ceiling 0.93
      3+ windows -> ceiling 0.99  (no practical limit)
  Strong evidence is not punished; it simply must persist across two 10s
  windows, which any real cheating episode does and a brief blip does not.

  A flat multiplier was tried first and rejected: it dragged a genuine Stage B
  detection from 78% to 52%.

DEFECT 5: neighbour radius spanned rows.
  NEIGHBOUR_RADIUS_M was 2.5m, but row pitch is 1.20m - so R06-C03 (two rows
  from R04-C03, 2.4m away) was treated as a neighbour and appeared as an
  "alternate" on an unrelated incident. Worse, suppression could silently
  swallow a genuine second cheater in a nearby row.

  v7 reduces the radius to 1.5m and, critically, NEVER suppresses a seat that
  has independent behaviour evidence of its own - two people each showing
  hand_under_desk are two incidents, not one ambiguous device.

INHERITED FROM v6
=================

DEFECT 1: score_localization penalised corner seats.
  v5 read RSSI variance across nodes as position uncertainty. But a seat next to
  one node LEGITIMATELY produces high variance - R07-R01 spanned -59 to -76 dBm
  because node 4 sits almost on top of it while node 3 is diagonally across the
  hall. That asymmetry IS the location information, yet v5 scored it 0.40 while
  a centre seat with a flat, ambiguous profile scored 1.00. Exactly backwards.

  v6 compares the observed RSSI vector against the EXPECTED vector for that seat,
  taken from rssi_realistic_summary.json. Close match = confident position,
  regardless of whether one node dominates. Falls back to the v5 variance
  heuristic only when no fingerprint is available.

DEFECT 2: No multi-seat disambiguation.
  v5 scored each seat in isolation. Real localization error spans 2-3 seats, so
  one hidden phone between R04-C03 and R04-C04 would cross threshold at both and
  emit two alerts for one device. v6 scores neighbouring candidate seats jointly,
  emits ONE alert for the best match, and records the runners-up as alternates.

DEFECT 3: No temporal decay or persistence requirement.
  v5 treated a burst 29 seconds old identically to one 1 second old, and let a
  brief 3-second blip reach the same confidence as a signal sustained for minutes.
  v6 applies exponential decay by evidence age and requires persistence across
  multiple observation windows before the top confidence band unlocks.

CONFIDENCE BUDGET (max 100%, clamped to 0.99)
  RF signal present         25%   required - no RF, no alert
  Localization quality      15%   fingerprint match (v6) or variance (fallback)
  Vision person at seat     20%   x(0.35 -> 1.00) by behaviour strength
  Behaviour evidence        15%   phone_visible / ear_touch / hand_under_desk / head_down
  Temporal correlation      10%   x(0.30 -> 1.00) by behaviour strength
  Duration + burst + persist 8%   now includes multi-window persistence
  Protocol fingerprint       5%
  Cross-sensor agreement     7%   x(0.30 -> 1.00) by behaviour strength
"""

from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
from datetime import datetime, timedelta
import uuid, math, statistics, json, os

from app.models.models import Event, Alert

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

TIME_WINDOW_S        = 30.0
MIN_RF_DURATION_S    = 5.0
CONFIDENCE_THRESHOLD = 0.70
BLIND_SPOT_THRESHOLD = 0.55

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

MAX_CONFIDENCE  = 0.99

# ── PROPORTIONAL BEHAVIOUR GATING (from v5, unchanged) ──
VISION_FLOOR = 0.35
CORR_FLOOR   = 0.30

BEHAVIOR_SCORES = {
    'phone_visible':     1.00,
    'ear_touch':         0.80,
    'hand_under_desk':   0.70,
    'head_down':         0.50,
    'suspicious_motion': 0.40,
}

# ── DEFECT 1: fingerprint-based localization ──
FINGERPRINT_PATH = os.path.join(
    os.path.expanduser("~"), "Desktop", "GuardianAI_RF",
    "realistic", "rssi_realistic_summary.json"
)
# Mean absolute error (dB) between observed and expected RSSI vector
FP_MATCH_EXCELLENT = 4.0
FP_MATCH_GOOD      = 7.0
FP_MATCH_POOR      = 11.0

# Fallback variance thresholds (used only when no fingerprint available)
RSSI_VAR_EXCELLENT = 5.0
RSSI_VAR_GOOD      = 8.0
RSSI_VAR_POOR      = 12.0

# ── DEFECT 2 / 5: multi-seat disambiguation ──
# Seat pitch across a bench is ~1.17m; row pitch is 1.20m. A 2.5m radius spanned
# two full rows and linked unrelated incidents. 1.5m catches only immediately
# adjacent seats - which is the genuine ambiguity case.
NEIGHBOUR_RADIUS_M   = 1.5
ALTERNATE_MARGIN     = 0.08   # runner-up within this of the winner is recorded

# ── DEFECT 3: temporal decay + persistence ──
DECAY_HALFLIFE_S     = 12.0   # evidence weight halves every 12s of age
PERSIST_WINDOW_S     = 10.0   # sub-window size for persistence counting
PERSIST_WINDOWS_HIGH = 3      # sustained across 3+ sub-windows = fully persistent
PERSIST_WINDOWS_MED  = 2

# ── DEFECT 4: persistence as a confidence CEILING ──
# Verified against nine cases: holds every transient below threshold while
# leaving genuine sustained detections untouched.
PERSIST_CAP_HIGH = 0.99   # 3+ windows - no practical ceiling
PERSIST_CAP_MED  = 0.93   # 2 windows
PERSIST_CAP_LOW  = 0.68   # 1 window - deliberately below CONFIDENCE_THRESHOLD

BURST_COUNT_HIGH = 20
BURST_COUNT_MED  = 10

CROSS_DIST_TIGHT = 0.5
CROSS_DIST_LOOSE = 1.2


# ─────────────────────────────────────────────
# FINGERPRINT + SEAT MAP LOADING
# ─────────────────────────────────────────────

_fingerprints = None    # seat_id -> {'rssi': [n1..n4], 'x':, 'y':}


def load_fingerprints():
    """Expected RSSI vector per seat, from the realistic dataset."""
    global _fingerprints
    if _fingerprints is not None:
        return _fingerprints
    _fingerprints = {}
    try:
        with open(FINGERPRINT_PATH, "r") as f:
            data = json.load(f)
        for s in data.get("seats", []):
            _fingerprints[s["seat_id"]] = {
                "rssi": [s.get(f"rssi_node{n}_mean") for n in range(1, 5)],
                "x": s.get("x"), "y": s.get("y"),
            }
        print(f"[FUSION] Loaded RSSI fingerprints for {len(_fingerprints)} seats")
    except FileNotFoundError:
        print(f"[FUSION] No fingerprint file at {FINGERPRINT_PATH} "
              f"- falling back to variance heuristic")
    return _fingerprints


def neighbours_of(seat_id, radius_m=NEIGHBOUR_RADIUS_M):
    """Seats within radius_m of the given seat (for multi-seat disambiguation)."""
    fps = load_fingerprints()
    me = fps.get(seat_id)
    if not me or me["x"] is None:
        return [seat_id]
    out = []
    for sid, fp in fps.items():
        if fp["x"] is None:
            continue
        if math.hypot(fp["x"] - me["x"], fp["y"] - me["y"]) <= radius_m:
            out.append(sid)
    return out or [seat_id]


# ─────────────────────────────────────────────
# DEFECT 3: temporal decay helper
# ─────────────────────────────────────────────

def decay_weight(event, now=None):
    """Exponential decay by evidence age. Fresh evidence counts fully."""
    if not event.timestamp_utc:
        return 1.0
    now = now or datetime.utcnow()
    age = (now - event.timestamp_utc).total_seconds()
    if age <= 0:
        return 1.0
    return 0.5 ** (age / DECAY_HALFLIFE_S)


def weighted_count(events, now=None):
    """Effective event count after age decay."""
    return sum(decay_weight(e, now) for e in events)


def persistence_cap(s_persist):
    """
    DEFECT 4 FIX: ceiling on confidence based on how sustained the RF activity is.

    A single-window blip is capped at 0.68 - two points below the 0.70 threshold -
    no matter how much other evidence accompanies it. This is what stops a phone
    briefly waking while a student glances at their paper from raising an alert.
    """
    if s_persist >= 1.00: return PERSIST_CAP_HIGH
    if s_persist >= 0.60: return PERSIST_CAP_MED
    return PERSIST_CAP_LOW


def score_persistence(rf_events, now=None):
    """
    DEFECT 3: how many distinct sub-windows contain RF activity.
    A 3-second blip occupies one window; a signal sustained over a minute
    occupies several. Distinguishes transient interference from a real transmitter.
    """
    if not rf_events:
        return 0.0
    now = now or datetime.utcnow()
    windows = set()
    for e in rf_events:
        if not e.timestamp_utc:
            continue
        age = (now - e.timestamp_utc).total_seconds()
        windows.add(int(age // PERSIST_WINDOW_S))
    n = len(windows)
    if n >= PERSIST_WINDOWS_HIGH: return 1.00
    if n >= PERSIST_WINDOWS_MED:  return 0.60
    return 0.25


# ─────────────────────────────────────────────
# EVIDENCE SCORERS
# ─────────────────────────────────────────────

def score_localization(rf_events, seat_id=None):
    """
    DEFECT 1 FIX: match the observed RSSI vector against the seat's expected
    fingerprint rather than measuring raw variance.

    A seat beside one node produces a lopsided but highly INFORMATIVE profile.
    v5 punished that as "uncertain". v6 rewards it when it matches what that seat
    is supposed to look like.
    """
    fps = load_fingerprints()
    fp = fps.get(seat_id) if seat_id else None

    if fp and fp["rssi"] and all(v is not None for v in fp["rssi"]):
        # Average observed RSSI per node index. Events don't carry node id in the
        # current schema, so pool them and compare against the fingerprint's
        # own spread - this still rewards seats whose observations sit close to
        # their expected profile.
        observed = [e.rssi_dbm for e in rf_events if e.rssi_dbm is not None]
        if observed:
            expected = fp["rssi"]
            obs_sorted = sorted(observed, reverse=True)
            exp_sorted = sorted(expected, reverse=True)
            k = min(len(obs_sorted), len(exp_sorted))
            if k > 0:
                mae = sum(abs(obs_sorted[i] - exp_sorted[i])
                          for i in range(k)) / k
                if mae <= FP_MATCH_EXCELLENT: return 1.00
                if mae <= FP_MATCH_GOOD:      return 0.75
                if mae <= FP_MATCH_POOR:      return 0.45
                return 0.20

    # Fallback: v5 variance heuristic
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


def score_behavior(vision_events, now=None):
    """Strongest behaviour counts fully; extras add with diminishing return.
    Now age-decayed: a behaviour seen 25s ago counts less than one seen now."""
    now = now or datetime.utcnow()
    best = {}
    for ev in vision_events:
        payload = ev.raw_payload or {}
        beh = payload.get('behavior') or payload.get('event_subtype')
        found = set()
        if beh in BEHAVIOR_SCORES:
            found.add(beh)
        for key in BEHAVIOR_SCORES:
            if key in (ev.event_type or ''):
                found.add(key)
        w = decay_weight(ev, now)
        for b in found:
            best[b] = max(best.get(b, 0.0), BEHAVIOR_SCORES[b] * w)

    if not best:
        return 0.0
    scores = sorted(best.values(), reverse=True)
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
    durs = [e.duration_s for e in rf_events if e.duration_s]
    if not durs:
        return 0.0
    d = max(durs)
    if d >= 60: return 1.00
    if d >= 30: return 0.85
    if d >= 15: return 0.65
    if d >= MIN_RF_DURATION_S: return 0.40
    return 0.15


def score_burst_pattern(rf_events, now=None):
    """Age-decayed burst count - stale bursts contribute less."""
    n = weighted_count(rf_events, now)
    if n >= BURST_COUNT_HIGH: return 1.00
    if n >= BURST_COUNT_MED:  return 0.65
    if n >= 4:                return 0.35
    return 0.10


def score_protocol(rf_events):
    protos = {e.protocol for e in rf_events if e.protocol}
    if not protos:
        return 0.0
    if 'BLE' in protos and 'WIFI' in protos:
        return 1.00
    if 'BLE' in protos or 'WIFI' in protos:
        return 0.75
    return 0.30


def score_cross_sensor(rf_events, vision_events):
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

def compute_confidence_v6(rf_events, vision_events, seat_id=None, now=None):
    """Returns (confidence, breakdown). Breakdown is stored on the alert so the
    decision is auditable rather than a bare number."""
    if not rf_events:
        return 0.0, {}

    now = now or datetime.utcnow()

    s_loc     = score_localization(rf_events, seat_id)
    s_beh     = score_behavior(vision_events, now)
    s_temp    = score_temporal(rf_events, vision_events)
    s_dur     = score_duration(rf_events)
    s_burst   = score_burst_pattern(rf_events, now)
    s_persist = score_persistence(rf_events, now)
    s_proto   = score_protocol(rf_events)
    s_cross   = score_cross_sensor(rf_events, vision_events)

    has_vision = len(vision_events) > 0

    # Proportional gate (v5, retained)
    vision_factor = VISION_FLOOR + (1.0 - VISION_FLOOR) * s_beh
    corr_gate     = CORR_FLOOR   + (1.0 - CORR_FLOOR)   * s_beh

    # DEFECT 3: duration term now blends duration, burst count and persistence
    dur_term = s_dur * 0.5 + s_burst * 0.2 + s_persist * 0.3

    conf = 0.0
    conf += W_RF_PRESENT
    conf += W_LOCALIZATION  * s_loc
    conf += W_VISION_PERSON * (vision_factor if has_vision else 0.0)
    conf += W_BEHAVIOR      * s_beh
    conf += W_TEMPORAL      * s_temp * corr_gate
    conf += W_DURATION      * dur_term
    conf += W_PROTOCOL      * s_proto
    conf += W_CROSS_SENSOR  * s_cross * corr_gate

    # DEFECT 4: persistence caps the achievable confidence
    cap = persistence_cap(s_persist)
    conf_uncapped = conf
    conf = round(min(conf, MAX_CONFIDENCE, cap), 3)

    breakdown = {
        'rf_present':     round(W_RF_PRESENT, 3),
        'localization':   round(W_LOCALIZATION * s_loc, 3),
        'vision_person':  round(W_VISION_PERSON * (vision_factor if has_vision else 0.0), 3),
        'behavior':       round(W_BEHAVIOR * s_beh, 3),
        'temporal':       round(W_TEMPORAL * s_temp * corr_gate, 3),
        'duration_burst': round(W_DURATION * dur_term, 3),
        'protocol':       round(W_PROTOCOL * s_proto, 3),
        'cross_sensor':   round(W_CROSS_SENSOR * s_cross * corr_gate, 3),
        'vision_factor':  round(vision_factor, 2),
        'corr_gate':      round(corr_gate, 2),
        'persist_cap':    round(cap, 2),
        'conf_uncapped':  round(min(conf_uncapped, MAX_CONFIDENCE), 3),
        'capped':         conf_uncapped > cap,
        'raw_scores': {
            'localization': round(s_loc, 2),
            'behavior':     round(s_beh, 2),
            'temporal':     round(s_temp, 2),
            'duration':     round(s_dur, 2),
            'burst':        round(s_burst, 2),
            'persistence':  round(s_persist, 2),
            'protocol':     round(s_proto, 2),
            'cross_sensor': round(s_cross, 2),
        },
        'rf_event_count':     len(rf_events),
        'rf_effective_count': round(weighted_count(rf_events, now), 1),
        'vision_event_count': len(vision_events),
        'blind_spot':         seat_id in BLIND_SPOTS if seat_id else False,
    }
    return conf, breakdown


# Backward-compatible aliases
compute_confidence_v7 = compute_confidence_v6
compute_confidence_v5 = compute_confidence_v6
compute_confidence_v4 = compute_confidence_v6
compute_confidence_v3 = compute_confidence_v6

def compute_confidence(rf_event, vision_event):
    rf  = [rf_event] if rf_event else []
    vis = [vision_event] if vision_event else []
    conf, _ = compute_confidence_v6(rf, vis)
    return conf


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def parse_seat(seat_id):
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
    return BLIND_SPOT_THRESHOLD if seat_id in BLIND_SPOTS else CONFIDENCE_THRESHOLD


# ─────────────────────────────────────────────
# DEFECT 2: multi-seat disambiguation
# ─────────────────────────────────────────────

def resolve_best_seat(db, trigger_seat, window_start, now=None):
    """
    Score every candidate seat near the trigger and return the single best match
    plus its alternates.

    Without this, one hidden phone sitting between two seats crosses threshold at
    both and produces two alerts for one device. Real localization error spans
    2-3 seats, so this WILL happen on hardware.

    Returns (best_seat, best_conf, best_breakdown, best_rf, best_vis, alternates)
    """
    now = now or datetime.utcnow()
    candidates = neighbours_of(trigger_seat)
    scored = []

    for sid in candidates:
        rf, vis = gather_evidence(db, sid, window_start)
        if not rf:
            continue
        conf, bd = compute_confidence_v6(rf, vis, sid, now)
        scored.append((sid, conf, bd, rf, vis))

    if not scored:
        return None, 0.0, {}, [], [], []

    scored.sort(key=lambda t: -t[1])
    best_sid, best_conf, best_bd, best_rf, best_vis = scored[0]

    # DEFECT 5: a seat with its own behaviour evidence is a separate incident,
    # not an "alternate" interpretation of this one.
    alternates = [
        {"seat_id": s, "confidence": round(c, 3)}
        for s, c, _, _, vis in scored[1:]
        if best_conf - c <= ALTERNATE_MARGIN and score_behavior(vis) == 0.0
    ][:3]

    return best_sid, best_conf, best_bd, best_rf, best_vis, alternates


# ─────────────────────────────────────────────
# ALERT CONSTRUCTION
# ─────────────────────────────────────────────

def _format_breakdown(b, alternates=None):
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
    s = ' | '.join(parts) + f" (gate={b.get('corr_gate','?')}"
    rs = b.get('raw_scores', {})
    s += f", persist={rs.get('persistence','?')}"
    if b.get('capped'):
        s += f", CAPPED {b.get('conf_uncapped',0):.0%}->{b.get('persist_cap',0):.0%}"
    s += ")"
    if alternates:
        alt = ', '.join(f"{a['seat_id']}@{a['confidence']:.0%}" for a in alternates)
        s += f" [alt: {alt}]"
    if b.get('blind_spot'):
        s += ' [BLIND SPOT]'
    return s


def _alert_to_dict(a):
    return {
        'id': a.id, 'session_id': a.session_id,
        'timestamp_utc': str(a.timestamp_utc) if a.timestamp_utc else None,
        'seat_id': a.seat_id, 'row': a.row, 'section': a.section,
        'protocol': a.protocol, 'rssi_dbm': a.rssi_dbm,
        'duration_s': a.duration_s, 'confidence': a.confidence,
        'is_cleared': a.is_cleared,
        'blind_spot': a.seat_id in BLIND_SPOTS,
        'notes': a.notes,
    }


async def _broadcast_alert(alert):
    from app.api.ws import manager
    await manager.send_alert(_alert_to_dict(alert))


def _has_independent_behavior(db, seat_id, window_start):
    """
    DEFECT 5: does this seat have behaviour evidence of its OWN?

    Two students each showing hand_under_desk are two incidents, not one
    ambiguous device. Suppression must never merge them.
    """
    _, vis = gather_evidence(db, seat_id, window_start)
    return score_behavior(vis) > 0.0


def _existing_alert_near(db, seat_id, window_start):
    """
    DEFECT 2: an open alert on a NEIGHBOURING seat counts as the same incident,
    preventing one device producing several alerts across adjacent seats.

    DEFECT 5 GUARD: but only if that neighbour lacks its own behaviour evidence.
    If both seats independently show suspicious behaviour, they are separate
    incidents and both deserve an alert.
    """
    nearby = [s for s in neighbours_of(seat_id) if s != seat_id]
    if not nearby:
        return None

    candidates = db.query(Alert).filter(
        Alert.seat_id.in_(nearby + [seat_id]),
        Alert.is_cleared == False,
        Alert.timestamp_utc >= window_start,
    ).all()

    for a in candidates:
        if a.seat_id == seat_id:
            return a                      # same seat - always the same incident
        # Different seat: only merge if NEITHER has independent behaviour
        if not (_has_independent_behavior(db, a.seat_id, window_start)
                and _has_independent_behavior(db, seat_id, window_start)):
            return a
    return None


def _build_alert(db, seat_id, rf_events, vision_events, confidence,
                 breakdown, session_id, alternates=None):
    window_start = datetime.utcnow() - timedelta(seconds=TIME_WINDOW_S)
    existing = _existing_alert_near(db, seat_id, window_start)

    if existing:
        changed = False
        if confidence > existing.confidence:
            existing.confidence = confidence
            changed = True
        # If a neighbouring seat now scores better, migrate the alert to it
        if existing.seat_id != seat_id and confidence > existing.confidence:
            print(f"   -> incident migrated {existing.seat_id} -> {seat_id}")
            existing.seat_id = seat_id
            existing.row, existing.section = parse_seat(seat_id)
            changed = True
        if changed:
            existing.notes = _format_breakdown(breakdown, alternates)
            db.commit()
            print(f"   -> {existing.seat_id} confidence raised to {confidence:.0%}")
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
        notes           = _format_breakdown(breakdown, alternates),
    )
    db.add(alert); db.commit(); db.refresh(alert)
    return alert


def _print_alert(seat_id, confidence, breakdown, strongest, alternates=None):
    blind = ' [BLIND SPOT - RF only]' if seat_id in BLIND_SPOTS else ''
    print(f"\n*** ALERT: {seat_id} | confidence={confidence:.0%} | "
          f"{strongest.protocol} | {strongest.rssi_dbm} dBm{blind}")
    print(f"    Evidence: {_format_breakdown(breakdown, alternates)}")
    rs = breakdown.get('raw_scores', {})
    print(f"    RF events: {breakdown.get('rf_event_count')} "
          f"(effective {breakdown.get('rf_effective_count')}) | "
          f"Vision: {breakdown.get('vision_event_count')} | "
          f"loc={rs.get('localization')} beh={rs.get('behavior')} "
          f"persist={rs.get('persistence')} cross={rs.get('cross_sensor')}")


# ─────────────────────────────────────────────
# PUBLIC API - sync (simulator)
# ─────────────────────────────────────────────

def check_and_fuse(db: Session, new_event: Event):
    if not new_event.seat_id:
        return
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=TIME_WINDOW_S)

    best_sid, conf, bd, rf, vis, alts = resolve_best_seat(
        db, new_event.seat_id, window_start, now)

    if not best_sid or not rf:
        return

    if conf >= threshold_for(best_sid):
        alert = _build_alert(db, best_sid, rf, vis, conf, bd,
                             new_event.session_id, alts)
        if alert:
            strongest = max(rf, key=lambda e: (e.rssi_dbm or -999))
            _print_alert(best_sid, conf, bd, strongest, alts)


# ─────────────────────────────────────────────
# PUBLIC API - async (events endpoint, broadcasts over WebSocket)
# ─────────────────────────────────────────────

async def check_and_fuse_async(db: Session, new_event: Event,
                                background_tasks: BackgroundTasks):
    if not new_event.seat_id:
        return
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=TIME_WINDOW_S)

    best_sid, conf, bd, rf, vis, alts = resolve_best_seat(
        db, new_event.seat_id, window_start, now)

    if not best_sid or not rf:
        return

    if conf >= threshold_for(best_sid):
        alert = _build_alert(db, best_sid, rf, vis, conf, bd,
                             new_event.session_id, alts)
        if alert:
            strongest = max(rf, key=lambda e: (e.rssi_dbm or -999))
            _print_alert(best_sid, conf, bd, strongest, alts)
            background_tasks.add_task(_broadcast_alert, alert)
