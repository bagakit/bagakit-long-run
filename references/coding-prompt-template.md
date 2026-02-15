# Coding Prompt (Single-Item Pass)

You are the coding agent for this repository.

## Inputs

- `.bagakit-long-run/feature-list.json`
- `.bagakit-long-run/bk-execution-handoff.md`
- `.bagakit-long-run/bk-execution-table.json`
- repository codebase

## Required steps

1. Read current execution item from `bk-execution-handoff.md`.
2. Implement exactly one execution item in this pass.
3. Run relevant checks/tests for touched scope.
4. Update `.bagakit-long-run/feature-list.json`:
   - `done` if acceptance criteria are met
   - `blocked` with reason if not finishable now
5. Update `.bagakit-long-run/bk-execution-handoff.md`:
   - files changed
   - commands run
   - test outcomes
   - open risks
   - next-run suggestion

## Constraints

- Do not start a second execution item in the same pass.
- Keep changes focused and reviewable.
- If blocked, stop and document explicit unblock action.
