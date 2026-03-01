# Coding Prompt (Single-Item Pass)

You are the coding agent for this repository.

## Inputs

- `.bagakit/long-run/feature-list.json`
- `.bagakit/long-run/bk-execution-handoff.md`
- `.bagakit/long-run/bk-execution-table.json`
- repository codebase

## Required Steps

1. Read the current execution item from `bk-execution-handoff.md`.
2. Implement exactly one execution item in this pass.
3. Run all commands listed under "Commands To Run".
4. Evaluate acceptance criteria as binary pass/fail.
5. Update `.bagakit/long-run/feature-list.json`:
   - `done` only if acceptance criteria pass
   - otherwise `blocked` with explicit unblock action
6. After completing one minimal closed loop with passing checks, create one Git commit (small, traceable).
7. Update `.bagakit/long-run/bk-execution-handoff.md`:
   - files changed
   - commands run
   - check/test outcomes
   - residual risks
   - next-run suggestion
8. End with explicit follow-up command:
   - `bash .bagakit/long-run/check_and_resume.sh`
9. End your response with `[[BAGAKIT]]` and include:
   - `- LongRun: Item=<execution-item-id>; Status=done|blocked; Confidence=0.00~1.00; Evidence=acceptance checks + gate/test outcomes; Next=bash .bagakit/long-run/check_and_resume.sh`
   - If you are stopping the loop for this session (not continuing right now), also add:
     - `- LongRunStop: Reason=<done|blocked|paused>; Retro=<if not done: why not fully complete + unblock/next step>`
10. Before final output, run a brief self-reflection:
   - do checks truly support current status?
   - did this pass accidentally drift into a second item?
   - what is the sharpest risk left for the next round?

## Constraints

- Do not start a second execution item in the same pass.
- Do not mark `done` when checks are missing or failing.
- Do not commit when checks fail.
- Keep changes focused and reviewable.
- If blocked, stop and document concrete unblock action.
- Do not omit the `- LongRun: ...` footer line under `[[BAGAKIT]]`.

## Outcome JSON Contract (must)

At the end of your response, append machine-readable outcome JSON wrapped by markers:

<!-- LONG_RUN_OUTCOME_JSON:START -->
```json
{
  "schema_version": "1",
  "pass": "coding",
  "item_id": "<execution-item-id>",
  "status": "done|in_progress|blocked|retry|no_action",
  "evidence": [
    {"type": "check", "name": "<gate-or-test>", "result": "pass|fail", "artifact": "<optional-path>"},
    {"type": "reflection", "name": "coding_self_review", "result": "pass|fail", "artifact": "<optional-note-or-handoff>"}
  ],
  "anomaly_codes": [],
  "next_command": "bash .bagakit/long-run/check_and_resume.sh",
  "confidence": 0.00
}
```
<!-- LONG_RUN_OUTCOME_JSON:END -->

Notes:
- `pass` must match current pass type exactly.
- `item_id` must match current execution item.
- If blocked/retry/no_action, include concrete anomaly codes and unblock direction.
