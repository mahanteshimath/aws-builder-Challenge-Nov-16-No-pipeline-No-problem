"""POST /jobs: a supervisor opens a lockout. Writes the job, one lock per worker and event #1 atomically, then starts the workflow."""
import hmac
import json
import os
import secrets
import time

import rules
from common import DB, SFN, T, TABLE, TTL_DAYS, Refuse, api, body_of, digest, log, new_key, now, reply, text

SITE_CODE = os.environ.get("SITE_CODE", "")
MACHINE = os.environ["STATE_MACHINE_ARN"]


def seconds(v, default):
    if v is None:
        return default
    if isinstance(v, bool) or not isinstance(v, int) or not 10 <= v <= 604800:
        raise Refuse(400, "timeouts must be whole seconds between 10 and 604800")
    return v


@api
def handler(event, ctx):
    b = body_of(event)
    if SITE_CODE and not hmac.compare_digest(str(b.get("siteCode", "")), SITE_CODE):
        raise Refuse(403, "site code required")
    machine = text(b.get("machine"), "machine", 60)
    supervisor = text(b.get("supervisor"), "supervisor", 40)
    roster = b.get("roster")
    if not isinstance(roster, list) or not 1 <= len(roster) <= 20:
        raise Refuse(400, "roster must list 1-20 workers")
    names = [text(n, "worker name", 40) for n in roster]
    if len({n.lower() for n in names}) != len(names):
        raise Refuse(400, "worker names must be unique")
    lock_wait = seconds(b.get("lockWaitSeconds"), 900)
    stuck = seconds(b.get("stuckSeconds"), 14400)

    job_id, sup_key, opened = secrets.token_hex(8), new_key(), now()
    workers = [{"slot": f"L{i}", "name": n, "key": new_key()} for i, n in enumerate(names, 1)]
    ev = {"seq": 1, "ts": opened, "type": "JOB_OPENED", "actor": supervisor,
          "detail": f"{machine}: {len(names)} locks required ({', '.join(names)})"}
    h = rules.event_hash(rules.GENESIS, ev)
    pk, ttl = f"JOB#{job_id}", {"ttl": int(time.time()) + TTL_DAYS * 86400}
    items = [
        {"PK": pk, "SK": "META", "jobId": job_id, "machine": machine, "supervisor": supervisor,
         "supKeyHash": digest(sup_key), "status": "LOCKED_OUT", "seq": 1, "lastHash": h, "openedAt": opened, **ttl},
        {"PK": pk, "SK": "EVT#000001", **ev, "prevHash": rules.GENESIS, "hash": h, **ttl},
        *[{"PK": pk, "SK": f"LOCK#{w['slot']}", "slot": w["slot"], "holder": w["name"],
           "keyHash": digest(w["key"]), "state": rules.AWAITING, **ttl} for w in workers],
    ]
    DB.transact_write_items(TransactItems=[{"Put": {"TableName": TABLE, "Item": i}} for i in items])

    try:
        arn = SFN.start_execution(
            stateMachineArn=MACHINE, name=job_id,
            input=json.dumps({"jobId": job_id, "lockWaitSeconds": lock_wait, "stuckSeconds": stuck,
                              "roster": [{"slot": w["slot"], "name": w["name"]} for w in workers]}),
        )["executionArn"]
    except Exception as e:
        log.error("start_execution failed: %r", e)
        raise Refuse(502, "workflow failed to start; the job stays locked out. Open a new lockout.", jobId=job_id)
    T.update_item(Key={"PK": pk, "SK": "META"}, UpdateExpression="SET executionArn = :a",
                  ExpressionAttributeValues={":a": arn})
    return reply(201, {"jobId": job_id, "supervisorKey": sup_key,
                       "workers": [{"slot": w["slot"], "name": w["name"], "key": w["key"]} for w in workers]})
