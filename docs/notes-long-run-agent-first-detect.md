---
title: Long Run Agent-First Detect
required: false
---

# Long Run Agent-First Detect

## Intent

`bagakit-long-run` is the execution driver.

It should not hardcode every upstream system in control flow. Instead:
- Agent performs detect-stage understanding.
- Agent curates execution-table mapping.
- Script validates quality and executes deterministic loop operations.

## Why

Unknown upstream systems are common (OpenSpec, ft-harness, issue trackers, custom docs).
Pure script detection cannot reliably infer semantics for all cases.

Agent-first detect provides:
- semantic interpretation of upstream work
- high-quality execution contracts for coding passes

Script validation provides:
- reproducibility
- auditable quality gates

## Runtime Contract

1. Agent updates `.bagakit/long-run/bk-execution-table.json`.
2. `detection.status` becomes `ready`.
3. `validate-table` passes.
4. only then does long-run init/plan/sync proceed.

## Quality Baseline

Execution planning must include:
- why now
- exact files to touch
- commands/checks to run
- verification expectations
- risk/rollback and unblock actions

For unsupported upstream systems, use `kind=manual` rows with explicit execution fields.
