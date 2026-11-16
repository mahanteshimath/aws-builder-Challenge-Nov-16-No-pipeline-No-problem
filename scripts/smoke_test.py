#!/usr/bin/env python3
"""End-to-end smoke test against a deployed LOTO Quorum stack (standard library only).

  python scripts/smoke_test.py https://<id>.execute-api.<region>.amazonaws.com
  python scripts/smoke_test.py <url> --escalation --profile hackathon --region us-east-1
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import rules  # noqa: E402

BASE, SITE = "", ""
passed, failed = 0, []


def check(name, cond, extra=""):
    global passed
    if cond:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed.append(name)
        print(f"  FAIL {name} {extra}")


def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def open_job(names, **kw):
    code, d = call("POST", "/jobs", {"machine": "Press Line 4", "supervisor": "Sam", "roster": names, "siteCode": SITE, **kw})
    assert code == 201, (code, d)
    return d["jobId"], d["supervisorKey"], {w["name"]: w for w in d["workers"]}


def act(job, w, action, **kw):
    return call("POST", f"/jobs/{job}/act", {"action": action, "slot": w["slot"], "key": w["key"], **kw})


def status(job):
    return call("GET", f"/jobs/{job}")[1]


def restart(job, key):
    return call("POST", f"/jobs/{job}/restart", {"key": key})


def wait_for(job, want, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        s = status(job)
        if s["status"] == want:
            return s
        time.sleep(1.5)
    return status(job)


def types(s):
    return Counter(e["type"] for e in s["events"])


def chain_ok(s):
    return rules.verify_chain(s["events"], s["lastHash"], s["seq"])[0] and s["chain"]["ok"]


def scenario_main():
    print("\n[1] Press Line 4: Asha, Ben, Chen (refusals, handover, restart, seal)")
    job, sup, w = open_job(["Asha", "Ben", "Chen"])
    check("restart refused before anyone has locked", restart(job, sup)[0] == 409)
    check("restart with a wrong supervisor key is rejected", restart(job, w["Asha"]["key"])[0] == 403)
    check("lock with a wrong key is rejected", act(job, {"slot": "L1", "key": "nope"}, "lock")[0] == 403)
    for n in w:
        check(f"{n} applies their lock", act(job, w[n], "lock")[0] == 200)
    before = status(job)["seq"]
    code, d = act(job, w["Asha"], "lock")
    check("repeated lock tap is idempotent (no new event)", code == 200 and d.get("already") and status(job)["seq"] == before)
    check("Asha releases", act(job, w["Asha"], "release")[0] == 200)
    code, d = restart(job, sup)
    check("restart refused while Ben and Chen are still locked", code == 409 and d["blocking"] == ["Ben", "Chen"], d)
    check("the refusal is in the audit trail", types(status(job))["RESTART_REFUSED"] == 2)

    code, d = act(job, w["Ben"], "handover", to="Dana")
    check("Ben hands his lock to Dana", code == 200 and d["holder"] == "Dana", d)
    dana = {"slot": w["Ben"]["slot"], "key": d.get("key")}
    check("Ben's old link stops working", act(job, w["Ben"], "release")[0] == 403)
    s = status(job)
    check("the lock never came off during handover", [l["state"] for l in s["locks"] if l["holder"] == "Dana"] == ["LOCKED"])
    check("override without the confirmation is refused", call("POST", f"/jobs/{job}/act", {"action": "override", "slot": "L3", "key": sup, "reason": "went home early"})[0] == 400)
    check("override with a worker key is refused", call("POST", f"/jobs/{job}/act", {"action": "override", "slot": "L3", "key": dana["key"], "reason": "went home early", "confirmNotInside": True})[0] == 403)
    check("Dana releases", act(job, dana, "release")[0] == 200)
    check("Chen releases", act(job, w["Chen"], "release")[0] == 200)
    s = wait_for(job, "CLEARED")
    check("Step Functions re-verifies and the board turns CLEARED", s["status"] == "CLEARED", s["status"])
    check("a lock cannot be re-applied after clear", act(job, w["Chen"], "lock")[0] == 409)
    code, d = restart(job, sup)
    check("restart succeeds and the audit is sealed in S3", code == 200 and d.get("sealKey") and d.get("chainVerified"), d)
    code, d2 = restart(job, sup)
    check("second restart is idempotent", code == 200 and d2.get("already"))
    s = status(job)
    check("status is RESTARTED and the seal is recorded", s["status"] == "RESTARTED" and s["sealKey"])
    check("hash chain verifies end to end (server and client)", chain_ok(s))
    check("sequence numbers are contiguous", [e["seq"] for e in s["events"]] == list(range(1, len(s["events"]) + 1)))


def scenario_override():
    print("\n[2] Supervisor override (written reason + 'not inside' confirmation)")
    job, sup, w = open_job(["Eve", "Frank"])
    check("Eve locks", act(job, w["Eve"], "lock")[0] == 200)
    code, _ = call("POST", f"/jobs/{job}/act", {"action": "override", "slot": "L2", "key": sup, "reason": "Frank called in sick, verified at gate", "confirmNotInside": True})
    check("supervisor force-releases Frank who never locked", code == 200)
    check("Eve releases", act(job, w["Eve"], "release")[0] == 200)
    s = wait_for(job, "CLEARED")
    check("job clears once every lock is off", s["status"] == "CLEARED")
    check("the override is on the record", types(s)["SUPERVISOR_OVERRIDE"] == 1 and chain_ok(s))


def scenario_concurrency(n=8):
    print(f"\n[3] {n} workers lock and release at the same instant")
    job, sup, w = open_job([f"Worker{i}" for i in range(1, n + 1)])
    with ThreadPoolExecutor(n) as ex:
        codes = list(ex.map(lambda x: act(job, x, "lock")[0], w.values()))
    check(f"all {n} simultaneous locks accepted", codes == [200] * n, codes)
    s = status(job)
    check("every lock is LOCKED and the job is still LOCKED_OUT", s["status"] == "LOCKED_OUT" and all(l["state"] == "LOCKED" for l in s["locks"]))
    with ThreadPoolExecutor(n) as ex:
        codes = list(ex.map(lambda x: act(job, x, "release")[0], w.values()))
    check(f"all {n} simultaneous releases accepted", codes == [200] * n, codes)
    s = wait_for(job, "CLEARED")
    check("job clears", s["status"] == "CLEARED")
    t = types(s)
    check("zero lost or duplicated events (sequence = 2n+2 exactly)", s["seq"] == 2 * n + 2 == len(s["events"]) and t["LOCK_APPLIED"] == n and t["LOCK_RELEASED"] == n, dict(t))
    check("hash chain still verifies under concurrency", chain_ok(s))


def scenario_escalation(profile, region):
    print("\n[4] Escalation: a stuck lock alerts the supervisor and is NOT released")
    import boto3
    job, sup, w = open_job(["Gus", "Hana"], lockWaitSeconds=10, stuckSeconds=10)
    act(job, w["Gus"], "lock")
    time.sleep(35)
    s = status(job)
    check("job is still locked out after the timeouts", s["status"] == "LOCKED_OUT")
    check("Gus's lock was NOT auto-released", [l["state"] for l in s["locks"] if l["holder"] == "Gus"] == ["LOCKED"])
    sfn = boto3.Session(profile_name=profile, region_name=region).client("stepfunctions")
    names = [e["stateExitedEventDetails"]["name"] for p in sfn.get_paginator("get_execution_history").paginate(executionArn=s["executionArn"])
             for e in p["events"] if e["type"] == "TaskStateExited"]
    check("SNS alert for the worker who never locked", "AlertLockMissing" in names, names)
    check("SNS alert for the stuck lock", "AlertStuckLock" in names, names)
    check("restart is still refused", restart(job, sup)[0] == 409)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--site-code", default="")
    ap.add_argument("--escalation", action="store_true")
    ap.add_argument("--profile", default="hackathon")
    ap.add_argument("--region", default="us-east-1")
    a = ap.parse_args()
    BASE, SITE = a.url.rstrip("/"), a.site_code
    scenario_main()
    scenario_override()
    scenario_concurrency()
    if a.escalation:
        scenario_escalation(a.profile, a.region)
    total = passed + len(failed)
    print(f"\n{passed}/{total} checks passed" + ("" if not failed else f"  FAILED: {failed}"))
    sys.exit(1 if failed else 0)
