# Initializer Prompt (Long-Run Harness)

You are the initializer agent for this repository.

## Inputs

- `.bagakit-long-run/feature-list.json`
- `.bagakit-long-run/claude-progress.md`
- current repository code/docs/tests

## Required steps

1. Run pre-session checks:
   - `sh .bagakit-long-run/init.sh`
2. Read feature list and choose exactly one feature for the next coding pass:
   - if a feature is `in_progress`, continue it
   - else choose the highest-priority `todo` feature that is unblocked
3. Update `.bagakit-long-run/feature-list.json`:
   - selected item -> `in_progress` (or keep as `in_progress`)
   - do not move multiple items to `in_progress`
4. Rewrite `.bagakit-long-run/claude-progress.md` as a concise coding handoff.

## Constraints

- Do not implement product code in this pass.
- Do not select multiple features.
- Keep plans concrete and file-path-specific.

## Handoff format (write into `claude-progress.md`)

- Current feature ID/title/goal
- acceptance criteria checklist
- exact files to touch
- commands to run
- risks and rollback notes

If no feature is currently implementable, mark the best candidate as `blocked` with a clear unblock action.
