"""GET /jobs/{jobId}: public board data. Never returns keys or task tokens."""
import time

import rules
from common import SFN, api, load, log, reply

_wf = {}  # executionArn -> (checked_at, status); ponytail: per-container 10 s cache, shared cache if traffic grows


def workflow_status(arn):
    """RUNNING / FAILED / TIMED_OUT / ABORTED, or None when unknown. A dead workflow means the board must say so."""
    if not arn:
        return None
    hit = _wf.get(arn)
    if hit and time.time() - hit[0] < 10:
        return hit[1]
    try:
        status = SFN.describe_execution(executionArn=arn)["status"]
    except Exception as e:
        log.warning("describe_execution failed: %r", e)
        return hit[1] if hit else None
    _wf[arn] = (time.time(), status)
    return status


@api
def handler(event, ctx):
    job, locks, events = load(event["pathParameters"]["jobId"], events=True)
    ok, why = rules.verify_chain(events, job["lastHash"], job["seq"])
    pick = lambda item, keys: {k: item.get(k) for k in keys}  # noqa: E731
    return reply(200, {
        **pick(job, ("jobId", "machine", "supervisor", "status", "openedAt", "clearedAt", "restartedAt",
                     "sealKey", "executionArn", "seq", "lastHash")),
        "workflow": workflow_status(job.get("executionArn")) if job["status"] == "LOCKED_OUT" else None,
        "locks": [pick(l, ("slot", "holder", "state", "lockedAt", "releasedAt", "releasedBy"))
                  for l in sorted(locks.values(), key=lambda l: int(l["slot"][1:]))],
        "events": [pick(e, ("seq", "ts", "type", "actor", "detail", "prevHash", "hash")) for e in events],
        "chain": {"ok": ok, "detail": why, "length": len(events)},
    })
