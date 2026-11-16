"""POST /jobs/{jobId}/restart: supervisor-only. Re-reads every lock, records the decision, seals the audit in S3."""
import json
import os
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError

import rules
from common import Refuse, _json, api, body_of, commit, load, log, now, released_check, reply, retry, same, T, pk

BUCKET = os.environ["BUCKET"]
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "1"))
S3 = boto3.client("s3")


def seal(job_id):
    job, _, events = load(job_id, events=True)
    ok, why = rules.verify_chain(events, job["lastHash"], job["seq"])
    key = f"audits/{job_id}.json"
    until = datetime.now(timezone.utc) + timedelta(days=RETENTION_DAYS)
    doc = {"jobId": job_id, "machine": job["machine"], "supervisor": job["supervisor"], "status": job["status"],
           "chainVerified": ok, "chainResult": why, "lastHash": job["lastHash"], "events": events, "sealedAt": now()}
    try:
        S3.put_object(Bucket=BUCKET, Key=key, Body=json.dumps(doc, default=_json, indent=2).encode(),
                      ContentType="application/json", ChecksumAlgorithm="SHA256",
                      ObjectLockMode="GOVERNANCE", ObjectLockRetainUntilDate=until)
    except ClientError as e:
        log.error("seal failed for job %s: %r", job_id, e)
        raise Refuse(502, "restart is authorized but sealing the audit failed; call restart again to retry the seal")
    T.update_item(Key={"PK": pk(job_id), "SK": "META"}, UpdateExpression="SET sealKey = :k, sealedAt = :t",
                  ExpressionAttributeValues={":k": key, ":t": now()})
    return reply(200, {"status": "RESTARTED", "sealKey": key, "retainUntil": until.isoformat(timespec="seconds"),
                       "chainVerified": ok})


def run(job_id, body):
    job, locks, _ = load(job_id)
    if not same(body.get("key"), job["supKeyHash"]):
        raise Refuse(403, "supervisor key required")
    if job["status"] == "RESTARTED":
        if job.get("sealKey"):
            return reply(200, {"status": "RESTARTED", "already": True, "sealKey": job["sealKey"]})
        return seal(job_id)
    blocking = sorted(l["holder"] for l in locks.values() if l["state"] != rules.RELEASED)
    if job["status"] != "CLEARED" or blocking:
        why = ("still locked or not yet applied: " + ", ".join(blocking)) if blocking else "the workflow has not cleared the job yet"
        commit(job, "RESTART_REFUSED", job["supervisor"], why)
        raise Refuse(409, "restart refused", blocking=blocking)
    commit(job, "RESTART_AUTHORIZED", job["supervisor"], "every lock re-verified released; restart permitted",
           [released_check(job, s) for s in locks], {"status": "RESTARTED", "restartedAt": now()})
    return seal(job_id)


@api
def handler(event, ctx):
    return retry(lambda: run(event["pathParameters"]["jobId"], body_of(event)))
