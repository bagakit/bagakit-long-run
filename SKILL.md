---
name: bagakit-long-run
description: Drive long-running delivery with an Agent-first detect stage and a script-validated single-item execution loop. Use when work spans many sessions and upstream execution systems must be normalized into one execution-table contract.
---

# Bagakit Long Run

## Role

`long-run` is the execution driver in the Bagakit stack.

It is responsible for:
- validating execution-table quality
- normalizing upstream systems into execution rows
- selecting and syncing single-item work
- enforcing repeatable session loops

It is not responsible for:
- creating/managing worktrees
- replacing upstream system semantics

## Design Principles

1. Agent-first detect:
- Agent owns upstream discovery and execution-table authoring.
- Script enforces deterministic quality gates.

2. Script-driven loop:
- detect/plan/guide/sync are reproducible commands.
- each coding pass handles exactly one execution item.

3. Quality over convenience:
- no pass if execution-table is still draft.
- no `done` without explicit checks and verification context.
- every detect/initializer/coding response ends with `[[BAGAKIT]]` and a peer line `- LongRun: Item=...; Status=...; Evidence=...; Next=...`.

## Workflow

1) Apply harness files

```bash
export BAGAKIT_LONG_RUN_SKILL_DIR="${BAGAKIT_LONG_RUN_SKILL_DIR:-${BAGAKIT_HOME:-$HOME/.claude}/skills/bagakit-long-run}"
bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/apply-long-run.sh" .
```

Apply also injects/updates a managed AGENTS block (`<!-- BAGAKIT:LONGRUN:START -->` ... `<!-- BAGAKIT:LONGRUN:END -->`) with loop-driving instructions.

2) Run detect pass (Agent)
- Use `.bagakit/long-run/detect_prompt.md`
- Update `.bagakit/long-run/bk-execution-table.json`
- Set `detection.status=ready`

3) Validate detect output quality

```bash
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/bagakit_long_run_execution.py" validate-table .
```

4) Run session init

```bash
sh .bagakit/long-run/init.sh
```

5) Initializer pass
- Use `.bagakit/long-run/initial_prompt.md`
- Produce high-quality `bk-execution-handoff.md`
- End the response with `[[BAGAKIT]]` and include `- LongRun: ...`

6) Coding pass
- Use `.bagakit/long-run/coding_prompt.md`
- Execute one item only
- Update `feature-list.json` and `bk-execution-handoff.md`
- End the response with `[[BAGAKIT]]` and include `- LongRun: ...`

7) Verify and iterate

```bash
bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/validate-long-run.sh" .
bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/bagakit_long_run_doctor.sh" .
```

Then re-run `sh .bagakit/long-run/init.sh` to actively pick the next actionable item.

## Execution-table Contract

Execution table file:
- `.bagakit/long-run/bk-execution-table.json`

Built-in kinds:
- `bagakit-ft`
- `openspec`
- `manual` (for any other upstream system)

`manual` rows are how you support arbitrary systems without writing new collectors.

## Quality Contract

The planning contract (required) includes:
- Why this item now
- Exact files to touch
- Commands/checks to run
- Verification/gate expectation
- Risk/rollback note

For manual rows, required fields include:
- `id`, `title`, `status`, `source_ref`, `why_now`
- `acceptance_criteria` (>=2)
- `files_to_touch` (>=1)
- `commands` (>=1)

## Scripts

- `apply-long-run.sh`: scaffold runtime files
- `validate-long-run.sh`: validate harness + execution-table quality
- `bagakit_long_run_doctor.sh`: diagnose loop health and next actions
- `bagakit_long_run_execution.py`: validate-table/detect/plan/guide/sync-feature-list
- `bagakit_long_run_features.py`: feature list validate/summary/pick/set-status
- `test.sh`: self-test
