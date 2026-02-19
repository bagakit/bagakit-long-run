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

Compatibility policy:
- no hard dependency on external systems (for example OpenSpec).
- external systems are optional adapters in execution-table; unavailable adapters must not break the loop.

## Why

Unknown upstream systems are common (OpenSpec, ft-harness, issue trackers, custom docs).
Pure script detection cannot reliably infer semantics for all cases.

Agent-first detect provides:
- semantic interpretation of upstream work
- high-quality execution contracts for coding passes

Script validation provides:
- reproducibility
- auditable quality gates
- evidence-aware ranking with explicit confidence signals

## Runtime Contract

1. Agent updates `.bagakit/long-run/bk-execution-table.json`.
2. `detection.status` becomes `ready`.
3. `validate-table` passes.
4. only then does long-run check/resume, plan, and sync proceed.

Loop operation is resume-driven:
- use `bash .bagakit/long-run/check_and_resume.sh` as the resume command (next-action SSOT)
- run it at session start and after each detect/initializer/coding pass
- follow resume output instead of manually guessing next actions

When stopping a session without continuing:
- final `[[BAGAKIT]]` footer should include `- LongRunStop: ...`
- if not fully completed, include a short retro on why full completion was not possible and what unblocks the next run

## Quality Baseline

Execution planning must include:
- why now
- exact files to touch
- commands/checks to run
- verification expectations
- risk/rollback and unblock actions
- confidence (0~1) and concrete evidence lines for why this item should run now

For unsupported upstream systems, use `kind=manual` rows with explicit execution fields.
