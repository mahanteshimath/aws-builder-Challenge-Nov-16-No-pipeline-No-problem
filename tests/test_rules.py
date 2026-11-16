"""Offline checks for the rules that make LOTO Quorum safe. Run: python tests/test_rules.py"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import rules  # noqa: E402


def make_chain(n=5):
    events, prev = [], rules.GENESIS
    for i in range(1, n + 1):
        ev = {"seq": i, "ts": f"2026-11-16T10:00:{i:02d}+00:00", "type": "LOCK_APPLIED", "actor": f"w{i}", "detail": f"lock {i}"}
        ev.update(prevHash=prev, hash=rules.event_hash(prev, ev))
        events.append(ev)
        prev = ev["hash"]
    return events, prev


def test_intact_chain_verifies():
    events, last = make_chain()
    assert rules.verify_chain(events, last, 5) == (True, "ok")


def test_edit_is_detected():
    events, last = make_chain()
    events[2]["detail"] = "nobody was inside"
    ok, why = rules.verify_chain(events, last, 5)
    assert not ok and "altered" in why


def test_delete_is_detected():
    events, last = make_chain()
    del events[2]
    ok, why = rules.verify_chain(events, last, 5)
    assert not ok and "missing" in why


def test_truncate_is_detected():
    events, last = make_chain()
    ok, why = rules.verify_chain(events[:-1], last, 5)
    assert not ok and "truncated" in why


def test_reorder_is_detected():
    events, last = make_chain()
    events[1], events[2] = events[2], events[1]
    assert not rules.verify_chain(events, last, 5)[0]


def test_rehashing_one_event_still_breaks_the_next_link():
    events, last = make_chain()
    forged = copy.deepcopy(events)
    forged[1]["detail"] = "forged"
    forged[1]["hash"] = rules.event_hash(forged[1]["prevHash"], forged[1])
    assert not rules.verify_chain(forged, last, 5)[0]


def test_wakeup_truth_table():
    table = {
        ("AWAITING", "LOCK"): False, ("LOCKED", "LOCK"): True, ("RELEASED", "LOCK"): True,
        ("AWAITING", "RELEASE"): False, ("LOCKED", "RELEASE"): False, ("RELEASED", "RELEASE"): True,
    }
    for (state, phase), want in table.items():
        assert rules.awaited(state, phase) is want, (state, phase)


def test_lock_only_moves_forward():
    assert rules.legal("AWAITING", "LOCKED") and rules.legal("LOCKED", "RELEASED")
    for frm, to in [("RELEASED", "LOCKED"), ("RELEASED", "AWAITING"), ("LOCKED", "AWAITING"), ("AWAITING", "RELEASED")]:
        assert not rules.legal(frm, to), (frm, to)


def test_override_can_release_early_but_never_relock():
    assert rules.legal("AWAITING", "RELEASED", override=True) and rules.legal("LOCKED", "RELEASED", override=True)
    assert not rules.legal("RELEASED", "LOCKED", override=True)


def test_every_lock_must_be_released():
    assert rules.all_released(["RELEASED", "RELEASED"])
    assert not rules.all_released(["RELEASED", "LOCKED"])
    assert not rules.all_released(["RELEASED", "AWAITING"])
    assert not rules.all_released([])


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"{len(tests)}/{len(tests)} offline checks passed")
