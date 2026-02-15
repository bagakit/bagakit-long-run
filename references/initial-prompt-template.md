# Initializer Prompt (Long-Run Harness)

You are the initializer agent for this repository.

## Inputs

- `.bagakit-long-run/feature-list.json`
- `.bagakit-long-run/bk-execution-handoff.md`
- `.bagakit-long-run/bk-execution-table.json`
- current repository code/docs/tests

## Required steps

1. Run pre-session checks:
   - `sh .bagakit-long-run/init.sh`
2. Use execution-table output to select exactly one actionable row for this run:
   - if a row is already `in_progress`, continue it
   - else pick the highest-priority actionable row (`todo`) from adapters
3. Ensure `.bagakit-long-run/feature-list.json` contains a single active item:
   - selected item -> `in_progress` (or keep as `in_progress`)
   - do not leave multiple items as `in_progress`
4. Rewrite `.bagakit-long-run/bk-execution-handoff.md` as a concise coding handoff.

## Constraints

- Do not implement product code in this pass.
- Do not select multiple execution items.
- Keep plans concrete and file-path-specific.

## Handoff format (write into `bk-execution-handoff.md`)

- current execution item ID / source system / source ref
- acceptance criteria checklist
- exact files to touch
- commands to run
- risks and rollback notes

If no row is implementable, mark the best candidate `blocked` with a clear unblock action.
