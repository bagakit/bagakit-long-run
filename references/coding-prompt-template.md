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
6. Update `.bagakit/long-run/bk-execution-handoff.md`:
   - files changed
   - commands run
   - check/test outcomes
   - residual risks
   - next-run suggestion
7. End with explicit follow-up command:
   - `bash .bagakit/long-run/check_and_resume.sh`
8. End your response with `[[BAGAKIT]]` and include:
   - `- LongRun: Item=<execution-item-id>; Status=done|blocked; Evidence=acceptance checks + gate/test outcomes; Next=bash .bagakit/long-run/check_and_resume.sh`
   - If you are stopping the loop for this session (not continuing right now), also add:
     - `- LongRunStop: Reason=<done|blocked|paused>; Retro=<if not done: why not fully complete + unblock/next step>`

## Constraints

- Do not start a second execution item in the same pass.
- Do not mark `done` when checks are missing or failing.
- Keep changes focused and reviewable.
- If blocked, stop and document concrete unblock action.
- Do not omit the `- LongRun: ...` footer line under `[[BAGAKIT]]`.
