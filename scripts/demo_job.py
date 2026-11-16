#!/usr/bin/env python3
"""Open a ready-to-record demo lockout on a deployed stack and print the links (standard library only).

  python scripts/demo_job.py https://<id>.execute-api.<region>.amazonaws.com
  python scripts/demo_job.py <url> --prelock Asha Ben Chen     # start the take with these locks already on
"""
import argparse
import json
import urllib.request


def call(method, url, body=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


ap = argparse.ArgumentParser()
ap.add_argument("url")
ap.add_argument("--machine", default="Press Line 4")
ap.add_argument("--workers", nargs="+", default=["Asha", "Ben", "Chen"])
ap.add_argument("--lock-wait", type=int, default=300, help="seconds before 'lock not applied' alerts")
ap.add_argument("--stuck", type=int, default=45, help="seconds before a held lock raises a stuck-lock alert")
ap.add_argument("--prelock", nargs="*", default=[], help="worker names whose locks are applied for you")
ap.add_argument("--site-code", default="")
a = ap.parse_args()

base = a.url.rstrip("/")
job = call("POST", base + "/jobs", {"machine": a.machine, "supervisor": "Sam", "roster": a.workers,
                                    "lockWaitSeconds": a.lock_wait, "stuckSeconds": a.stuck, "siteCode": a.site_code})
workers = {w["name"]: w for w in job["workers"]}
for name in a.prelock:
    w = workers[name]
    call("POST", f"{base}/jobs/{job['jobId']}/act", {"action": "lock", "slot": w["slot"], "key": w["key"]})

link = lambda **kw: f"{base}/#" + "&".join(f"{k}={v}" for k, v in kw.items())  # noqa: E731
print(f"\nJob {job['jobId']} on {a.machine} (stuck-lock alert after {a.stuck}s)\n")
print("Supervisor :", link(job=job["jobId"], sup=job["supervisorKey"]))
for w in job["workers"]:
    print(f"{w['name']:<11}:", link(job=job["jobId"], slot=w["slot"], key=w["key"]),
          "(lock already ON)" if w["name"] in a.prelock else "")
print("Read-only  :", link(job=job["jobId"]))
arn = call("GET", f"{base}/jobs/{job['jobId']}")["executionArn"]
region = arn.split(":")[3]
print(f"Step Functions: https://{region}.console.aws.amazon.com/states/home?region={region}#/v2/executions/details/{arn}\n")
