"""Shared helpers: DynamoDB access, atomic audited commits, task-token wake-ups, HTTP replies."""
import base64
import functools
import hashlib
import hmac
import json
import os
import random
import secrets
import time
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

import rules

TABLE = os.environ["TABLE"]
_db = boto3.resource("dynamodb")
T = _db.Table(TABLE)
DB = _db.meta.client
SFN = boto3.client("stepfunctions")


class Refuse(Exception):
    def __init__(self, code, msg, **extra):
        super().__init__(msg)
        self.code, self.msg, self.extra = code, msg, extra


class Conflict(Exception):
    """A concurrent writer won. Re-read, re-check the rules, try again."""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(s):
    return hashlib.sha256(s.encode()).hexdigest()


def new_key():
    return secrets.token_urlsafe(16)


def same(key, key_hash):
    return hmac.compare_digest(digest(key if isinstance(key, str) else ""), key_hash)


def text(v, label, limit, minimum=1):
    if not isinstance(v, str) or not minimum <= len(v.strip()) <= limit or not v.isprintable():
        raise Refuse(400, f"{label} must be {minimum}-{limit} printable characters")
    return v.strip()


def pk(job_id):
    return f"JOB#{job_id}"


def load(job_id, events=False):
    """One consistent query: META + every lock (+ the audit events when asked)."""
    cond = Key("PK").eq(pk(job_id))
    if not events:
        cond &= Key("SK").gte("LOCK#")
    kw = {"KeyConditionExpression": cond, "ConsistentRead": True}
    items = []
    while True:
        r = T.query(**kw)
        items += r["Items"]
        if "LastEvaluatedKey" not in r:
            break
        kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]
    job = next((i for i in items if i["SK"] == "META"), None)
    if not job:
        raise Refuse(404, "no such job")
    locks = {i["SK"][5:]: i for i in items if i["SK"].startswith("LOCK#")}
    return job, locks, [i for i in items if i["SK"].startswith("EVT#")]


def lock_update(job, slot, expr, cond, names, values):
    return {"Update": {"TableName": TABLE, "Key": {"PK": job["PK"], "SK": f"LOCK#{slot}"},
                       "UpdateExpression": expr, "ConditionExpression": cond,
                       "ExpressionAttributeNames": names, "ExpressionAttributeValues": values}}


def released_check(job, slot):
    return {"ConditionCheck": {"TableName": TABLE, "Key": {"PK": job["PK"], "SK": f"LOCK#{slot}"},
                               "ConditionExpression": "#s = :r", "ExpressionAttributeNames": {"#s": "state"},
                               "ExpressionAttributeValues": {":r": rules.RELEASED}}}


def commit(job, etype, actor, detail, ops=(), meta_set=None):
    """Append one hash-chained audit event and apply `ops` in ONE transaction.

    The job's seq is the optimistic-concurrency token: a stale view of the job always loses,
    so simultaneous writers cannot fork the chain or drop an event.
    """
    seq = int(job["seq"]) + 1
    ev = {"seq": seq, "ts": now(), "type": etype, "actor": actor, "detail": detail}
    h = rules.event_hash(job["lastHash"], ev)
    names = {"#sq": "seq", "#lh": "lastHash"}
    vals = {":n": seq, ":h": h, ":c": int(job["seq"])}
    sets = ["#sq = :n", "#lh = :h"]
    for i, (k, v) in enumerate((meta_set or {}).items()):
        names[f"#m{i}"], vals[f":m{i}"] = k, v
        sets.append(f"#m{i} = :m{i}")
    items = [
        {"Put": {"TableName": TABLE, "ConditionExpression": "attribute_not_exists(PK)",
                 "Item": {"PK": job["PK"], "SK": f"EVT#{seq:06d}", **ev, "prevHash": job["lastHash"], "hash": h}}},
        {"Update": {"TableName": TABLE, "Key": {"PK": job["PK"], "SK": "META"},
                    "UpdateExpression": "SET " + ", ".join(sets), "ConditionExpression": "#sq = :c",
                    "ExpressionAttributeNames": names, "ExpressionAttributeValues": vals}},
        *ops,
    ]
    try:
        DB.transact_write_items(TransactItems=items)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("TransactionCanceledException", "TransactionInProgressException"):
            raise Conflict() from e
        raise


def retry(fn, tries=25):
    for i in range(tries):
        try:
            return fn()
        except Conflict:
            time.sleep(random.uniform(0.01, 0.05) * min(i + 1, 6))
    raise Refuse(503, "busy, please retry")


def wake(token):
    """Resume a waiting Step Functions branch. A stale or finished token is not an error."""
    try:
        SFN.send_task_success(taskToken=token, output="{}")
    except ClientError as e:
        if e.response["Error"]["Code"] not in ("TaskTimedOut", "TaskDoesNotExist", "InvalidToken"):
            raise


def wake_waiters(job_id, slot):
    lock = T.get_item(Key={"PK": pk(job_id), "SK": f"LOCK#{slot}"}, ConsistentRead=True)["Item"]
    for phase, attr in (("LOCK", "lockToken"), ("RELEASE", "releaseToken")):
        if lock.get(attr) and rules.awaited(lock["state"], phase):
            wake(lock[attr])


def _json(o):
    if isinstance(o, Decimal):
        return int(o) if o == o.to_integral_value() else float(o)
    raise TypeError(type(o))


def reply(code, body):
    return {"statusCode": code, "body": json.dumps(body, default=_json),
            "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"}}


def body_of(event):
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode()
    try:
        b = json.loads(raw)
    except ValueError:
        raise Refuse(400, "body must be JSON")
    if not isinstance(b, dict):
        raise Refuse(400, "body must be a JSON object")
    return b


def api(fn):
    @functools.wraps(fn)
    def wrapper(event, ctx):
        try:
            return fn(event, ctx)
        except Refuse as r:
            return reply(r.code, {"error": r.msg, **r.extra})
    return wrapper
