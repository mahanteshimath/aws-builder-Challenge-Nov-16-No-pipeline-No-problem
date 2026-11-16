# Demo video script (target 2:50, hard limit under 3:00)

Record one browser window plus the AWS console tabs. Voice-over, no music needed. Upload as **Public** to YouTube, paste the link in the Builder Center *demo* field and at the top of the README. Published: https://youtu.be/4QKF6SiACMg

## Before you hit record (5 minutes)
1. **Alert email:** click the SNS confirmation link sent to mahanteshimath@gmail.com. Without it no escalation email arrives.
2. **Tabs, in this order:** `docs/architecture.png`, the app, Step Functions console, S3 console (audit bucket), your inbox.
3. **Browser:** 1920x1080, zoom 100%, dark theme (it reads best on video; the app also has light).
4. **Rehearse once** (the whole flow takes about 90 seconds on the wall), then clean up (see the end of this file).
5. In the app choose **Fill with a demo crew**. That sets Press Line 4, Asha, Ben, Chen and the **Demo** alert timing (alerts after 45 seconds), so the escalation email lands during the take.

## The one-screen trick
After you lock out the machine, click **Open demo wall**. It shows the supervisor board and every worker's phone side by side, all live. You never switch windows.

## Shot list

| Time | On screen | Say (about) |
|---|---|---|
| 0:00 to 0:18 | Title card, then the OSHA line from the README | "Five technicians are inside a hydraulic press. One finishes and switches the line back on. Four are still inside. Lockout/tagout was OSHA's fourth most-cited standard in 2025: 2,562 citations. The hard part is the group." |
| 0:18 to 0:40 | `docs/architecture.png` | "Fully serverless. The quorum **is** the workflow: a Step Functions Map with one branch per worker, each waiting on a task token. DynamoDB holds the locks, S3 Object Lock seals the audit, SNS escalates, CloudWatch watches. One SAM template, no pipeline." |
| 0:40 to 0:55 | Home screen: **Fill with a demo crew**, **Lock out machine**, **Open demo wall** | "A supervisor names the crew and locks out the machine. This wall shows the supervisor and every worker's phone at once." |
| 0:55 to 1:10 | Each phone taps **Apply my lock**. Plate stays red: LOCKED OUT. | "Every worker applies their own lock. The board says: locked out, do not start." |
| 1:10 to 1:30 | Asha releases (checkbox, **Confirm release**). Supervisor: **Request restart**. Red callout: refused, Ben and Chen. Point at the audit trail. | "Releasing takes a deliberate confirmation. Asha is out, but a restart is refused while Ben and Chen are still locked, and even the refusal is in the audit trail." |
| 1:30 to 1:45 | In Ben's pane: **Handing over at shift change?**, type Dana, **Hand over**. | "Shift change. Ben hands his lock to Dana in one atomic step, so the lock never comes off. Ben's old link stops working." |
| 1:45 to 2:05 | Step Functions execution graph (Map branches waiting), then the escalation email. Back to the wall: still red. | "Locks left on past their limit raise an alert. The workflow keeps waiting. It can only make a restart harder, never easier." |
| 2:05 to 2:30 | Dana and Chen release. Plate turns green: CLEARED FOR RESTART. Click restart: RESTART AUTHORIZED. | "When the last lock comes off, the workflow re-checks every lock. Only then does the board go green." |
| 2:30 to 2:45 | S3 console: audit object with Object Lock. Back to the board: "Hash chain verified". Flash the terminal: `53/53 checks passed`. | "The audit record is hash-chained and sealed with Object Lock. A 53-check test passes against the live stack, including eight workers at the same instant." |
| 2:45 to 2:55 | Closing card | "Any everyone-must-sign-off gate works the same way: two-person rules, change freezes, lab access. Idle cost is about zero. It supplements physical locks and never replaces them." |

## Optional 5-second proofs (use if you have time)
- **Offline safety:** in browser dev tools set the network to Offline. After about 10 seconds the plate flips to **STATUS UNKNOWN** and says to follow the physical procedure.
- **Old link:** paste Ben's pre-handover link in a new tab. It says "This link is no longer active".
- **QR:** on the opened screen click **QR** next to a worker and point a phone at the monitor.

## Tips
- Say the safety line out loud: it adds to physical locks and never replaces them.
- Show the failure case (the refused restart) in the first half of the video, not the last.
- Keep each take under 3:00 on the timer, or the entry can be cut at Gate 1.

## Clean up after recording
Jobs left running keep sending alert emails every 45 seconds.
```powershell
$sm = "arn:aws:states:us-east-1:686112930486:stateMachine:QuorumMachine-2HypBxAEFGCB"
foreach ($a in (aws stepfunctions list-executions --state-machine-arn $sm --status-filter RUNNING --query "executions[].executionArn" --output text --profile hackathon --region us-east-1) -split "\s+" | Where-Object { $_ }) {
  aws stepfunctions stop-execution --execution-arn $a --profile hackathon --region us-east-1 | Out-Null }
```
