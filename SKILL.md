---
name: bagakit-long-run
description: Drive long-running delivery with an Agent-first detect stage and a script-validated single-item execution loop. Use when work spans many sessions and upstream execution systems must be normalized into one execution-table contract.
---

# Bagakit Long Run

## Standalone-First Contract

- This skill is standalone-first: it can run with only `long-run` runtime files and scripts.
- Upstream systems are integrated through optional adapter contracts/signals in the execution table, never mandatory direct script calls.
- Preferred runtime entry is `.bagakit/long-run/ralphloop-runner.sh` (continuous loop; internally uses `ralphloop.sh run/pulse` + `check_and_resume.sh`).

## When to Use

- Work spans many sessions and needs deterministic single-item progression.
- You need one normalized execution table that merges multiple upstream systems.
- You need evidence-based row ordering (`status -> confidence -> evidence -> weight -> priority`).

## When NOT to Use

- Work is a tiny one-shot task and a long-running loop is unnecessary.
- You want `long-run` to replace upstream domain semantics instead of normalize them.
- You require mandatory hard coupling to one specific external skill flow.

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
- row ranking is deterministic and evidence-aware: `status -> confidence -> evidence -> weight -> priority`.

3. Quality over convenience:
- no pass if execution-table is still draft.
- no `done` without explicit checks and verification context.
- every detect/initializer/coding response ends with `[[BAGAKIT]]` and a peer line `- LongRun: Item=...; Status=...; Confidence=...; Evidence=...; Next=...`.
- if you stop a session without continuing the loop right now, add a peer line `- LongRunStop: Reason=...; Retro=...` explaining why you stop (and why the plan cannot be fully completed if not done).

## **Outer Orchestrator Runner** (Core Concept)

- `outer orchestrator runner` 指项目内的外层调度器（默认 `.bagakit/long-run/ralphloop-runner.sh`），职责是循环调用 `ralphloop.sh run --endless`，而不是执行业务逻辑。
- Runner 必须保持 orchestration-only：只做命令调度、失败停止、边界保护、日志观测。
- 托管生成文件（不建议手改）必须放在 `.bagakit/long-run/.gen/`；根目录脚本保留兼容入口包装器。
- Runner 必须支持安全边界参数（至少）：
  - `RALPHLOOP_MAX_ROUNDS`：最大轮数（`0` 表示不限）。
  - `RALPHLOOP_MAX_RUNTIME_SECONDS`：最大运行时长（秒，`0` 表示不限）。
  - `RALPHLOOP_MAX_INTERVAL_SECONDS`：轮询最大间隔上限（用于约束 `RALPHLOOP_SLEEP_SECONDS`）。
- Runner 必须输出可观测日志（终端 + 文件），默认日志文件建议：`.bagakit/long-run/logs/ralphloop-runner.log`。

## Outer Orchestrator Checklist (Required)

Before claiming continuous-loop readiness, complete all steps:
1. Command route selection:
- pick project launcher route (`package.json` script / `Makefile` target / standalone shell launcher).
2. Coding CLI selection:
- set `BAGAKIT_AGENT_CMD` (preferred) or `BAGAKIT_AGENT_CLI` for prompt execution.
- require non-TUI/non-interactive command form to avoid waiting loops (for example: `codex exec`).
- ensure command supports `"{prompt_file}"` placeholder (or accepts prompt file as final arg).
  - example: `export BAGAKIT_AGENT_CMD='codex exec {prompt_text}'`
  - escape hatch (debug only): `export BAGAKIT_ALLOW_INTERACTIVE_AGENT_CMD=1`
3. Script implementation:
- keep `ralphloop.sh` as single-step (`pulse`/`run`) contract entry.
- keep `ralphloop-runner.sh` as outer infinite loop orchestrator.
- support safety params: `RALPHLOOP_MAX_ROUNDS`, `RALPHLOOP_MAX_RUNTIME_SECONDS`, `RALPHLOOP_MAX_INTERVAL_SECONDS`.
- keep log output enabled (`RALPHLOOP_LOG_FILE`, optional `RALPHLOOP_JSON_MODE=1`).
4. Dry-run verification:
- run `bash .bagakit/long-run/ralphloop.sh run --endless --dry-run --json`.
5. End-to-end smoke test:
- run `bash .bagakit/long-run/ralphloop-runner.sh` for at least one full closed loop.
6. Failure policy:
- on `status=failed`, stop loop and inspect `resume_stderr_tail` before retry.

## `[[BAGAKIT]]` Footer Contract

```text
[[BAGAKIT]]
- LongRun: Item=<id>; Status=<in_progress|done|blocked>; Confidence=<0~1>; Evidence=<commands/checks>; Next=<resume command>
- LongRunStop: Reason=<why stop now>; Retro=<why not fully complete and what unblocks next> (only when stopping loop)
```

## Workflow

1) Apply harness files

```bash
export BAGAKIT_LONG_RUN_SKILL_DIR="<path-to-bagakit-long-run-skill>"
bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/apply-long-run.sh" .
```

Apply also injects/updates a managed AGENTS block (`<!-- BAGAKIT:LONGRUN:START -->` ... `<!-- BAGAKIT:LONGRUN:END -->`) with loop-driving instructions.

Startup self-check + migration (required before first loop on existing projects):
- run `bash .bagakit/long-run/check_and_resume.sh`
- if self-check reports missing managed `.gen` files, run `bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/apply-long-run.sh" . --force` and retry

2) Run detect pass (Agent)
- Use `.bagakit/long-run/.gen/detect_prompt.md`
- Update `.bagakit/long-run/bk-execution-table.json`
- Set `detection.status=ready`

3) Validate detect output quality

```bash
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-execution.py" validate-table .
```

4) Runner entry (continuous, recommended)

```bash
bash .bagakit/long-run/ralphloop-runner.sh
```

Behavior:
- if `BAGAKIT_AGENT_CMD`/`BAGAKIT_AGENT_CLI` is configured, loop continuously: pulse -> agent dispatch -> next round
- `run` rejects interactive/TUI-looking commands for known CLIs; use non-interactive command forms.
- if agent command is missing, runner falls back to one `pulse --endless`
- runner safety/observability envs:
  - `RALPHLOOP_MAX_ROUNDS`, `RALPHLOOP_MAX_RUNTIME_SECONDS`, `RALPHLOOP_MAX_INTERVAL_SECONDS`
  - `RALPHLOOP_LOG_FILE` (default `.bagakit/long-run/logs/ralphloop-runner.log`), `RALPHLOOP_JSON_MODE=1`
- `run` mode dispatches prompts by status:
  - `actionable(todo)` -> `.gen/initializer_prompt.md`
  - `actionable(in_progress)` -> `.gen/coding_prompt.md`
  - `endless_prompt_ready` -> `endless_expand_prompt.md`
- one run round executes exactly one pass (no initializer+coding in same round).
- after each pass, the loop must re-run `check_and_resume.sh` to decide next pass.
- strict outcome gate is enabled by default: pass success requires `LONG_RUN_OUTCOME_JSON` markers + schema-valid JSON + evidence-backed status.
- failures are mapped to deterministic `anomaly_action` (`blocked_stop` | `retryable` | `needs_detect`).
- temporary rollback switch: `BAGAKIT_LONG_RUN_LEGACY_RC_ONLY=1` (RC-only compatibility mode).
- async message inbox:
  - `.bagakit/long-run/ralph-msg.md` is lazily created.
  - top segment (split by `---`) is injected into this round as user message and moved to `.bagakit/long-run/ralph-msg.consumed.md` (prepended with timestamp + ralph context).

5) Pulse entry (single-step fallback)

```bash
bash .bagakit/long-run/ralphloop.sh pulse --endless
```

Behavior:
- always runs `bash .bagakit/long-run/check_and_resume.sh`
- if next row exists: returns actionable item
- if no next row and `--endless`: writes `.bagakit/long-run/endless_expand_prompt.md` for agent-driven plan expansion
- expansion prompt is rendered with project-local context from `.bagakit/long-run/project-profile.json` (stack/launcher/quality commands)

6) Check and resume (fallback/direct)

```bash
bash .bagakit/long-run/check_and_resume.sh
```

Treat `bash .bagakit/long-run/check_and_resume.sh` as the resume command for every round.
This command also writes a structured next-action contract:
- `.bagakit/long-run/next-action.json`
- before quality validation, it runs execution-table archive maintenance (`archive-table`) to trim overflow `manual` done rows.
- archive scope is fixed to `manual + done` only.
- default archive output: `.bagakit/long-run/archive/execution-table/manual-rows-YYYYMM.ndjson`
- if manual `blocked` rows are detected, archive step will print warning and keep them untouched.
- archive knobs:
  - `BAGAKIT_LONG_RUN_ARCHIVE_DONE_KEEP` (default `120`)
  - `BAGAKIT_LONG_RUN_ARCHIVE_MAX_PER_RUN` (default `60`)
  - `BAGAKIT_LONG_RUN_ARCHIVE_FILE` (optional custom file)
  - `BAGAKIT_LONG_RUN_ARCHIVE_DISABLED=1` (disable archive step)

7) Initializer pass
- Use `.bagakit/long-run/.gen/initializer_prompt.md`
- Produce high-quality `bk-execution-handoff.md`
- End the response with `[[BAGAKIT]]` and include `- LongRun: ...`
- Add a brief reflection before finalizing outcome (selection correctness / handoff completeness / unblock quality).
- End the response with outcome JSON markers:
  - `<!-- LONG_RUN_OUTCOME_JSON:START -->`
  - `<!-- LONG_RUN_OUTCOME_JSON:END -->`

8) Coding pass
- Use `.bagakit/long-run/.gen/coding_prompt.md`
- Execute one item only
- Update `feature-list.json` and `bk-execution-handoff.md`
- End the response with `[[BAGAKIT]]` and include `- LongRun: ...`
- Add a brief reflection before finalizing outcome (evidence sufficiency / scope drift / residual risk).
- End the response with outcome JSON markers:
  - `<!-- LONG_RUN_OUTCOME_JSON:START -->`
  - `<!-- LONG_RUN_OUTCOME_JSON:END -->`

9) Verify and iterate

```bash
bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/validate-long-run.sh" .
bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-doctor.sh" .
```

Then re-run `bash .bagakit/long-run/check_and_resume.sh` to actively pick the next actionable item.

10) Heartbeat (optional, standalone)

```bash
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-heartbeat.py" tick . --json
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-heartbeat.py" flash-ideas . --count 5 --json
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-heartbeat.py" schedule-list .
```

Default behavior:
- heartbeat enabled, every 30 minutes, active window `08:00-22:00` (all days)
- autonomy mode `full_auto_execute`, run context `main`
- guardrails: allowlist + timeout + command budget + git clean check
- delivery route: `announce` with always-on file history
- inbox route: prefer `docs/.bagakit/inbox/` mirror when present, fallback to `.bagakit/long-run/inbox/`
- idle fallback: generate 3~5 flash ideas and auto-pick top-1

External scheduling remains optional:
- `schedule-add` only writes local contracts (`heartbeat-schedules.json`)
- `schedule-render` generates runnable artifacts for external schedulers (`at`/`every`/`cron`)
- no daemon and no external online dependency required

## Execution-table Contract

Execution table file:
- `.bagakit/long-run/bk-execution-table.json`

Built-in kinds:
- `bagakit-ft` (optional contract adapter via `.bagakit/ft-harness/index/feats.json` + feat state/tasks files)
- `openspec`
- `manual` (for any other upstream system)

`manual` rows are how you support arbitrary systems without writing new collectors.

Built-in archive maintenance (optional but enabled by default):
- configure in `maintenance.archive` inside `bk-execution-table.json`
- command: `python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-execution.py" archive-table .`
- scope: `manual + done` only; manual `blocked` rows are warned but not archived
- goal: keep active table compact while preserving archived row history in ndjson files

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
- `confidence` (0~1)
- `evidence` (>=1)

## Scripts

- `apply-long-run.sh`: scaffold runtime files
- `validate-long-run.sh`: validate harness + execution-table quality
- `long-run-doctor.sh`: diagnose loop health and next actions
- `long-run-execution.py`: validate-table/detect/plan/next-action/guide/sync-feature-list/archive-table
- `long-run-loop.py`: pulse/run/preflight entry (`pulse --endless`, `run --endless`, `preflight`) and strict outcome gating
- `long-run-features.py`: feature list validate/summary/pick/set-status
- `long-run-heartbeat.py`: heartbeat tick/flash-ideas/schedule-add|list|remove|render
- `scripts_dev/test.sh`: self-test

## Output Routes and Default Mode

- Deliverable type: process-driver loop that routes upstream execution rows into deterministic single-item action execution.
- Action handoff output (default route): `.bagakit/long-run/next-action.json` plus synchronized `feature-list.json`/`bk-execution-handoff.md` as execution-ready artifacts.
- Memory handoff output (default route): `bk-execution-handoff.md` session summary and `[[BAGAKIT]]` evidence lines; memory can be `none` when no durable update is needed with explicit rationale.
- Optional adapter routes: upstream systems (`bagakit-ft`, `openspec`, manual adapters) are integrated through optional adapter contracts in execution-table rows.
- Adapter policy: optional, rule-driven routing with standalone-safe fallback to local long-run artifacts.

## Archive Gate (Completion Handoff)

- Completion requires explicit destination path/id evidence for `action_handoff` (next-action + selected row outputs) and `memory_handoff` (handoff/memory destination, or explicit `none` rationale).
- Do not mark completion until loop gate conditions pass (`validate-long-run` + doctor/verification evidence) and archive destination reporting is present.

## Fallback Path

- If detect output is not ready or has no actionable rows, stop coding execution, run `validate-table` + `doctor`, and record `[[BAGAKIT]]` with `LongRunStop` reason and retro.
- If no actionable row remains and you want continuous flow, run `bash .bagakit/long-run/ralphloop-runner.sh` (with `BAGAKIT_AGENT_CMD` configured) so the loop can execute generated prompt files automatically.
