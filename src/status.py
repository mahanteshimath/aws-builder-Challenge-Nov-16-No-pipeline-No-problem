"""GET /jobs/{jobId}: public board data. Never returns keys or task tokens."""
import rules
from common import api, load, reply


@api
def handler(event, ctx):
    job, locks, events = load(event["pathParameters"]["jobId"], events=True)
    ok, why = rules.verify_chain(events, job["lastHash"], job["seq"])
    pick = lambda item, keys: {k: item.get(k) for k in keys}  # noqa: E731
    return reply(200, {
        **pick(job, ("jobId", "machine", "supervisor", "status", "openedAt", "clearedAt", "restartedAt",
                     "sealKey", "executionArn", "seq", "lastHash")),
        "locks": [pick(l, ("slot", "holder", "state", "lockedAt", "releasedAt", "releasedBy"))
                  for l in sorted(locks.values(), key=lambda l: int(l["slot"][1:]))],
        "events": [pick(e, ("seq", "ts", "type", "actor", "detail", "prevHash", "hash")) for e in events],
        "chain": {"ok": ok, "detail": why, "length": len(events)},
    })
