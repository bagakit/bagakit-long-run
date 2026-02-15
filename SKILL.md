---
name: bagakit-long-run
description: Build and run a robust harness for long-running agent projects using initializer/coding loops, execution-table adapters, machine-readable feature state, and repeatable session checks.
---

# Bagakit Long Run

## Overview

Use this skill when work spans many sessions and you want long-run to actively sense upstream execution systems.

This skill provides:
- stable initializer and coding prompts
- execution-table adapters (`bagakit-ft`, `openspec`) for proactive coupling
- machine-readable feature list synced from execution rows
- BK handoff file between sessions
- scripts to apply, validate, and diagnose harness health

## Workflow

1. Bootstrap harness files in your project

```bash
export BAGAKIT_LONG_RUN_SKILL_DIR="${BAGAKIT_LONG_RUN_SKILL_DIR:-${BAGAKIT_HOME:-$HOME/.bagakit}/skills/bagakit-long-run}"
bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/apply-long-run.sh" .
```

2. Run pre-session checks (this auto-detects adapters and syncs feature-list)

```bash
sh .bagakit-long-run/init.sh
```

3. Initializer pass
- Use `.bagakit-long-run/initial_prompt.md`
- Choose exactly one execution item for the next coding pass
- Update `feature-list.json` and `bk-execution-handoff.md`

4. Coding pass
- Use `.bagakit-long-run/coding_prompt.md`
- Implement exactly one selected execution item
- Run relevant tests/checks
- Mark the item `done` or `blocked`
- Update `bk-execution-handoff.md`

5. Verify harness health

```bash
bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/validate-long-run.sh" .
bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/bagakit_long_run_doctor.sh" .
```

6. Repeat from step 2

## Execution Coupling

Execution-table file: `.bagakit-long-run/bk-execution-table.json`.

Default adapters:
- `bagakit-ft`: reads `.bagakit-ft/index/feats.json` and feat/task state
- `openspec`: reads `openspec/changes/*` proposal/tasks

Use helper script directly when needed:

```bash
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/bagakit_long_run_execution.py" detect .
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/bagakit_long_run_execution.py" plan . --limit 8
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/bagakit_long_run_execution.py" guide .
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/bagakit_long_run_execution.py" sync-feature-list .
```

## Universal Principles

- Evidence over assumptions: detect outputs signals and rule context; it should not hard-bind decisions to one naming convention.
- Normalize before deciding: map heterogeneous upstream systems to one execution-row contract, then select next work from that contract.
- Guidance over rigid policy: rules describe what to analyze and what a plan must include; the agent decides using context.
- Loose coupling by adapters: integration stays at the adapter boundary so one system's internals do not leak into long-run core flow.
- Traceable decisions: selection rationale and execution intent must be captured in `bk-execution-handoff.md`.

## Design Principle: Avoid Assumptions And Tight Coupling

Core logic:
- Runtime/tool vendors can change, but project artifacts and execution facts are the stable contract.
- So long-run must couple to explicit rules and state artifacts, not to vendor naming or legacy file conventions.

Required implementation posture:
- Prefer rule-driven detection from `bk-execution-table.json` over hardcoded assumptions.
- Keep integration logic inside adapters; keep long-run core loop generic.
- Treat guidance as quality constraints for planning, not as a rigid closed policy that removes agent judgment.

Self-check triggers:
- Adding a new integration path: verify it can be modeled as adapter rules first.
- Adding fallback logic: verify it does not silently preserve deprecated assumptions.
- Adding naming semantics: verify names remain bagakit-neutral and execution-oriented.

## Feature Status Rules

- `todo`: ready but not started
- `in_progress`: current item being worked
- `done`: implemented and validated
- `blocked`: cannot proceed until dependency/unblock action

Constraints:
- at most one `in_progress` item at a time
- coding pass must touch only one item

## Template Files

Templates live in `references/`:
- `initial-prompt-template.md`
- `coding-prompt-template.md`
- `feature-list-template.json`
- `bk-execution-handoff-template.md`
- `bk-execution-table-template.json`
- `init-sh-template.sh`

## Scripts

Scripts live in `scripts/`:
- `apply-long-run.sh`: scaffold harness files into a target repo
- `validate-long-run.sh`: check harness files + execution-table + feature list validity
- `bagakit_long_run_doctor.sh`: diagnostics and actionable recommendations
- `bagakit_doctor.sh`: compatibility shim to `bagakit_long_run_doctor.sh`
- `bagakit_long_run_features.py`: feature list helper (validate/summary/pick/set-status)
- `bagakit_long_run_execution.py`: execution-table adapter bridge, guidance output, and feature sync
- `test.sh`: local self-test for the skill
