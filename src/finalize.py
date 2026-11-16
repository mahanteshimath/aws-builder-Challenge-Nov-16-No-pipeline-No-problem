"""Last step of the workflow: re-read every lock and only then mark the job CLEARED.

Any doubt raises, the workflow fails, and the job stays LOCKED_OUT (fail safe).
"""
import rules
from common import commit, load, now, released_check, retry


def clear(job_id):
    job, locks, _ = load(job_id)
    if job["status"] in ("CLEARED", "RESTARTED"):
        return {"cleared": True}
    if not rules.all_released(l["state"] for l in locks.values()):
        raise RuntimeError("quorum incomplete: a lock is still on; the job stays locked out")
    commit(job, "CLEARED_FOR_RESTART", "workflow", f"all {len(locks)} locks released and re-verified",
           [released_check(job, s) for s in locks], {"status": "CLEARED", "clearedAt": now()})
    return {"cleared": True}


def handler(event, ctx):
    return retry(lambda: clear(event["jobId"]))
