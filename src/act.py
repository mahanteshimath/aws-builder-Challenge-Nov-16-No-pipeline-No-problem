"""POST /jobs/{jobId}/act: lock, release, handover (workers) and override (supervisor)."""
import rules
from common import (Refuse, api, body_of, commit, digest, load, lock_update, log, new_key, now, reply, retry,
                    same, text, wake_waiters)

ACTIONS = ("lock", "release", "handover", "override", "check")
NAMES = {"#s": "state", "#k": "keyHash"}


def run(job_id, b, action):
    job, locks, _ = load(job_id)
    slot = b.get("slot")
    lock = locks.get(slot) if isinstance(slot, str) else None
    if not lock:
        raise Refuse(404, "no such lock")
    if action == "check":  # lets a link's owner confirm it still controls a lock (e.g. not handed over)
        return {"valid": same(b.get("key"), lock["keyHash"])}
    if action == "override":
        if not same(b.get("key"), job["supKeyHash"]):
            raise Refuse(403, "supervisor key required")
    elif not same(b.get("key"), lock["keyHash"]):
        raise Refuse(403, "wrong key for this lock")

    st, who, t = lock["state"], lock["holder"], now()
    target = rules.LOCKED if action in ("lock", "handover") else rules.RELEASED
    if action in ("lock", "release") and st == target:
        return {"state": st, "already": True}
    if job["status"] != "LOCKED_OUT":
        raise Refuse(409, f"job is {job['status']}; open a new lockout to work on this machine")
    if action == "handover":
        if st != rules.LOCKED:
            raise Refuse(409, f"lock is {st}; only an applied lock can be handed over")
    elif not rules.legal(st, target, override=action == "override"):
        raise Refuse(409, f"lock is {st}; cannot {action}")

    out = {"state": target}
    old = {":old": st, ":kh": lock["keyHash"]}
    if action == "lock":
        op = lock_update(job, slot, "SET #s = :new, lockedAt = :t", "#s = :old AND #k = :kh", NAMES,
                         {**old, ":new": target, ":t": t})
        commit(job, "LOCK_APPLIED", who, f"{slot} ({who}) applied their lock", [op])
    elif action == "release":
        op = lock_update(job, slot, "SET #s = :new, releasedAt = :t, releasedBy = :by", "#s = :old AND #k = :kh",
                         NAMES, {**old, ":new": target, ":t": t, ":by": who})
        commit(job, "LOCK_RELEASED", who, f"{slot} ({who}) released their lock", [op])
    elif action == "handover":
        to, nk = text(b.get("to"), "incoming worker", 40), new_key()
        op = lock_update(job, slot, "SET #h = :to, #k = :nk", "#s = :old AND #k = :kh",
                         {**NAMES, "#h": "holder"}, {**old, ":to": to, ":nk": digest(nk)})
        commit(job, "LOCK_HANDED_OVER", who, f"{slot} handed over {who} -> {to}; the lock never came off", [op])
        out = {"state": rules.LOCKED, "slot": slot, "holder": to, "key": nk}
    else:
        reason = text(b.get("reason"), "reason", 200, minimum=10)
        if b.get("confirmNotInside") is not True:
            raise Refuse(400, "supervisor must confirm they verified the worker is not inside")
        op = lock_update(job, slot, "SET #s = :new, releasedAt = :t, releasedBy = :by, overrideReason = :why",
                         "#s = :old", {"#s": "state"}, {":old": st, ":new": target, ":t": t,
                                                         ":by": f"SUPERVISOR {job['supervisor']}", ":why": reason})
        commit(job, "SUPERVISOR_OVERRIDE", job["supervisor"],
               f"{slot} ({who}) force-released; verified not inside; reason: {reason}", [op])
    return out


@api
def handler(event, ctx):
    job_id = event["pathParameters"]["jobId"]
    b = body_of(event)
    action = b.get("action")
    if action not in ACTIONS:
        raise Refuse(400, f"action must be one of {', '.join(ACTIONS)}")
    res = retry(lambda: run(job_id, b, action))
    if action not in ("handover", "check"):
        try:
            wake_waiters(job_id, b["slot"])
        except Exception as e:  # the committed state is the truth; the workflow's timeout loop re-checks the lock
            log.error("wake failed for job %s slot %s: %r", job_id, b.get("slot"), e)
    return reply(200, res)
