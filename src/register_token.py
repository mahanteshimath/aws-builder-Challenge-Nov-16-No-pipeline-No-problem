"""Task-token parking. Invoked by Step Functions (waitForTaskToken); never touched by clients.

The token is stored with an atomic UpdateItem that returns the lock as it is NOW. If the awaited
condition already holds (a worker tapped while an old token was timing out), resume immediately.
Otherwise act.py resumes the token when the lock changes. Either order: no lost wake-up.
"""
import rules
from common import T, pk, wake


def handler(event, ctx):
    attr = "lockToken" if event["phase"] == "LOCK" else "releaseToken"
    lock = T.update_item(
        Key={"PK": pk(event["jobId"]), "SK": f"LOCK#{event['slot']}"},
        UpdateExpression="SET #t = :t", ConditionExpression="attribute_exists(PK)",
        ExpressionAttributeNames={"#t": attr}, ExpressionAttributeValues={":t": event["token"]},
        ReturnValues="ALL_NEW",
    )["Attributes"]
    if rules.awaited(lock["state"], event["phase"]):
        wake(event["token"])
