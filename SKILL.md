---
name: bagakit-long-run
description: Build and run a robust harness for long-running agent projects using a two-agent loop (initializer + coding), machine-readable feature state, and repeatable session checks.
---

# Bagakit Long Run

## Overview

Use this skill when a task is too large for one session and you need reliable multi-session progress without losing context.

This skill provides:
- a stable initializer prompt
- a stable coding prompt
- a feature list JSON with explicit statuses
- a handoff progress file between sessions
- scripts to apply, validate, and diagnose harness health

## Workflow

1. Bootstrap harness files in your project

```bash
export BAGAKIT_LONG_RUN_SKILL_DIR="${BAGAKIT_LONG_RUN_SKILL_DIR:-${CODEX_HOME:-$HOME/.codex}/skills/bagakit-long-run}"
bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/apply-long-run.sh" .
```

2. Run pre-session checks

```bash
sh .bagakit-long-run/init.sh
```

3. Initializer pass
- Use `.bagakit-long-run/initial_prompt.md`
- Choose exactly one feature for the next coding pass
- Update `feature-list.json` and `claude-progress.md`

4. Coding pass
- Use `.bagakit-long-run/coding_prompt.md`
- Implement exactly one selected feature
- Run relevant tests/checks
- Mark the feature `done` or `blocked`
- Update `claude-progress.md`

5. Verify harness health

```bash
bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/validate-long-run.sh" .
bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/bagakit_long_run_doctor.sh" .
```

6. Repeat from step 2

## Feature Status Rules

- `todo`: ready but not started
- `in_progress`: current feature being worked
- `done`: implemented and validated
- `blocked`: cannot proceed until dependency/unblock action

Constraints:
- at most one `in_progress` item at a time
- coding pass must touch only one feature item

## Template Files

Templates live in `references/`:
- `initial-prompt-template.md`
- `coding-prompt-template.md`
- `feature-list-template.json`
- `claude-progress-template.md`
- `init-sh-template.sh`

## Scripts

Scripts live in `scripts/`:
- `apply-long-run.sh`: scaffold harness files into a target repo
- `validate-long-run.sh`: check harness files + feature list validity
- `bagakit_long_run_doctor.sh`: diagnostics and actionable recommendations
- `bagakit_doctor.sh`: compatibility shim to `bagakit_long_run_doctor.sh`
- `bagakit_long_run_features.py`: feature list helper (validate/summary/pick/set-status)
- `test.sh`: local self-test for the skill
