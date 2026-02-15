# Coding Prompt (Single-Feature Pass)

You are the coding agent for this repository.

## Inputs

- `.bagakit-long-run/feature-list.json`
- `.bagakit-long-run/claude-progress.md`
- repository codebase

## Required steps

1. Read the current feature from `claude-progress.md`.
2. Implement exactly one feature (`Feature ID`) in this pass.
3. Run relevant checks/tests for the touched scope.
4. Update `.bagakit-long-run/feature-list.json`:
   - `done` if acceptance criteria is met
   - `blocked` with reason if not finishable now
5. Update `.bagakit-long-run/claude-progress.md`:
   - files changed
   - commands run
   - test outcomes
   - open risks
   - next session suggestion

## Constraints

- Do not start a second feature in the same pass.
- Keep changes focused and reviewable.
- If blocked, stop and document unblock action instead of speculative rewrites.
