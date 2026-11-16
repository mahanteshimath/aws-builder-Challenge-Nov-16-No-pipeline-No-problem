"""Pure LOTO Quorum rules. No AWS imports, so tests/test_rules.py runs offline."""
import hashlib
import json

GENESIS = "0" * 64
AWAITING, LOCKED, RELEASED = "AWAITING", "LOCKED", "RELEASED"
LEGAL = {(AWAITING, LOCKED), (LOCKED, RELEASED)}


def legal(frm, to, override=False):
    """A lock only moves AWAITING -> LOCKED -> RELEASED. A supervisor override may release early."""
    return (frm, to) in LEGAL or (override and frm in (AWAITING, LOCKED) and to == RELEASED)


def awaited(state, phase):
    """True when the condition a parked task token waits for already holds (no lost wake-ups)."""
    return state in (LOCKED, RELEASED) if phase == "LOCK" else state == RELEASED


def all_released(states):
    states = list(states)
    return bool(states) and all(s == RELEASED for s in states)


def event_hash(prev, ev):
    body = json.dumps(
        {"seq": int(ev["seq"]), "ts": ev["ts"], "type": ev["type"], "actor": ev["actor"], "detail": ev["detail"]},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256((prev + body).encode()).hexdigest()


def verify_chain(events, last_hash, seq):
    """Return (ok, reason). Detects edited, deleted, reordered and truncated events."""
    prev = GENESIS
    for i, ev in enumerate(events, 1):
        if int(ev["seq"]) != i:
            return False, f"event {i} missing or out of order"
        if ev["prevHash"] != prev or ev["hash"] != event_hash(prev, ev):
            return False, f"event {i} altered"
        prev = ev["hash"]
    if len(events) != int(seq) or prev != last_hash:
        return False, "chain truncated"
    return True, "ok"
