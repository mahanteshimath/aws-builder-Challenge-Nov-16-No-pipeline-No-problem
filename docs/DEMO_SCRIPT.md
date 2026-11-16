# Demo video script (target 2:50, hard limit under 3:00)

Record the screen with voice-over (OBS or Win+G). Upload as **Public** to YouTube, paste the link in the Builder Center *demo* field and at the top of the README.

## Before you hit record (5 minutes)
1. Alert email: click the SNS confirmation link sent to mahanteshimath@gmail.com (without it no escalation email arrives).
2. Open these tabs in order: architecture PNG (`docs/architecture.png`), the app, Step Functions console, S3 console (audit bucket), your inbox.
3. Open a fresh job (stuck-lock alert after 45 s so the email lands during the take):
   ```
   python scripts/demo_job.py https://kucvps8yif.execute-api.us-east-1.amazonaws.com
   ```
   It prints the supervisor link, one link per worker, the read-only link and the Step Functions execution link. Put each in its own browser window/tab, labelled.
4. After recording, stop leftover executions so alerts stop (see "Clean up").

## Shot list

| Time | On screen | Say (about) |
|---|---|---|
| 0:00 to 0:20 | Title card, then OSHA line from the README | "Five technicians are inside a hydraulic press. One finishes, switches the line back on. Four are still inside. Lockout/tagout was OSHA's fourth most-cited standard in FY2025, 2,562 citations. The hard part is the group: shift changes, forgotten locks, no record of who was inside." |
| 0:20 to 0:40 | `docs/architecture.png` | "It's fully serverless. The quorum **is** the workflow: a Step Functions Map with one branch per worker, each waiting on a task token. DynamoDB holds the locks, S3 Object Lock seals the audit, SNS escalates. One SAM template, nothing to babysit." |
| 0:40 to 0:55 | Supervisor page, **Open a lockout**: Press Line 4, Asha/Ben/Chen. (Or show the pre-opened job.) | "A supervisor locks out Press Line 4 for three workers. Each gets a personal link." |
| 0:55 to 1:15 | Three worker windows tap **Apply my lock**. Board turns red. | "Every worker applies their own lock. The board says LOCKED OUT: DO NOT START." |
| 1:15 to 1:35 | Asha releases. Supervisor clicks **Request restart**: refused, blocked by Ben, Chen. Point at `RESTART_REFUSED` in the audit trail. | "Asha is out. The supervisor tries to restart: refused, Ben and Chen are still locked. Even the refusal is on the record." |
| 1:35 to 1:55 | Ben hands over to Dana. Click Ben's old link's release: "wrong key for this lock". | "Shift change. Ben hands his lock to Dana in one atomic step, so the lock never comes off, and Ben's old link stops working." |
| 1:55 to 2:15 | Step Functions execution graph (Map branches waiting), then the escalation email arriving (stuck lock). Board still red. | "Chen's lock stays on too long. The workflow alerts the supervisor and keeps waiting. It can only make a restart harder, never easier." |
| 2:15 to 2:35 | Dana and Chen release. Board turns green: CLEARED FOR RESTART. Click restart: success. | "When the last lock comes off, Step Functions re-verifies every lock. Only now does the board go green." |
| 2:35 to 2:50 | S3 console: audit object with Object Lock retention. Back to the board: "hash chain verified". Flash the terminal with `40/40 checks passed`. | "The audit record is hash-chained and sealed with Object Lock. A smoke test of 40 checks, including eight workers at the same instant, passes against the live stack." |
| 2:50 to 2:55 | Closing card | "Any everyone-must-sign-off gate works the same way: two-person rules, change freezes, lab access. Idle cost is about zero. It supplements physical locks, it never replaces them." |

## Tips
- Say the safety line out loud (it adds to physical locks, never replaces them). Judges reward honesty about safety.
- Don't narrate code. Show the board, the Step Functions graph, and the failure case (refused restart).
- Keep each take under 3:00 on the timer, or the entry can be cut at Gate 1.

## Clean up after recording
```powershell
$sm = "arn:aws:states:us-east-1:686112930486:stateMachine:QuorumMachine-2HypBxAEFGCB"
foreach ($a in (aws stepfunctions list-executions --state-machine-arn $sm --status-filter RUNNING --query "executions[].executionArn" --output text --profile hackathon --region us-east-1) -split "\s+" | Where-Object { $_ }) {
  aws stepfunctions stop-execution --execution-arn $a --profile hackathon --region us-east-1 | Out-Null }
```
