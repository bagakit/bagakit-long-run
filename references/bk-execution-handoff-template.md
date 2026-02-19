# BK Execution Handoff

## Run Metadata

- Updated At (UTC): <YYYY-MM-DDTHH:MM:SSZ>
- Updated By: <initializer|coding>
- Branch: <branch-name>
- Worktree (optional): <path-or-empty>

## Current Execution Item

- Execution Item ID: <set-by-initializer>
- Source System: <bagakit-ft|openspec|manual>
- Source Ref: <path-or-identifier>
- Title: <set-by-initializer>
- Status: in_progress
- Why This Item Now: <set-by-initializer>

## Acceptance Criteria

- [ ] <criterion 1, binary pass/fail>
- [ ] <criterion 2, binary pass/fail>

## Execution Plan

1. <step 1>
2. <step 2>
3. <step 3>

## Files To Touch

- `<path/to/file>`

## Commands To Run

```bash
# add copy/paste commands (build/test/gate)
```

## Expected Verification

- Gate / verification command: <command>
- Expected result: <what pass looks like>

## Results

- Summary: <pending>
- Tests: <pending>
- Gate / Verification: <pending pass|fail + evidence>

## Response Driver Snapshot

Copy this block into the final coding response (fill concrete values):

```text
[[BAGAKIT]]
- LivingDoc: <project-required note>
- LongRun: Item=<Execution Item ID> | <Title>; Status=<in_progress|done|blocked>; Confidence=<0.00~1.00>; Evidence=<commands/tests/verifications and pass/fail>; Next=bash .bagakit/long-run/check_and_resume.sh
- LongRunStop: Reason=<done|blocked|paused>; Retro=<if not done: why not fully complete + unblock/next step>
```

## Risks / Open Questions

- Risks: <risk or question>
- Rollback: <rollback approach if this pass fails>
- Unblock Action (if blocked): <explicit next action>

## Next Run

- If completed: mark source item complete and pick next actionable row from execution table.
- If blocked: set status to `blocked` and capture explicit unblock action.
