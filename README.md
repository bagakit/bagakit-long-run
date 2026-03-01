# bagakit-long-run

A Bagakit skill focused on driving long-running delivery loops.

`long-run` is an execution driver:
- it does not own worktree state
- it does not replace upstream change systems
- it enforces a repeatable loop: detect -> check+resume -> execute one item -> verify -> continue

Reference:
- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

## **Outer Orchestrator Runner** (Core Concept)

- `outer orchestrator runner` 是项目内的外层循环调度器（默认 `.bagakit/long-run/ralphloop-runner.sh`），负责稳定地调用 `ralphloop.sh run --endless`。
- 它应该只做 orchestration：调度、失败停止、边界保护、日志输出；不要在 runner 内承载业务实现逻辑。
- 托管生成文件（不建议手改）放在 `.bagakit/long-run/.gen/`；根目录脚本保留为兼容入口包装器。
- 推荐最小安全边界参数：
  - `RALPHLOOP_MAX_ROUNDS`（最大轮数，`0`=不限）
  - `RALPHLOOP_MAX_RUNTIME_SECONDS`（最大总运行时长，`0`=不限）
  - `RALPHLOOP_MAX_INTERVAL_SECONDS`（轮询间隔上限，用来约束 `RALPHLOOP_SLEEP_SECONDS`）
- 推荐可观测性参数：
  - `RALPHLOOP_LOG_FILE`（默认 `.bagakit/long-run/logs/ralphloop-runner.log`）
  - `RALPHLOOP_JSON_MODE=1`（输出 JSON 风格 run/pulse 结果）

## Outer Orchestrator Checklist

1. Determine command route:
- `package.json` script, `Makefile` target, or standalone shell launcher.
2. Determine coding CLI:
- configure `BAGAKIT_AGENT_CMD` (preferred) or `BAGAKIT_AGENT_CLI`.
- require non-TUI/non-interactive command form to avoid blocking loops (for example `codex exec`).
- use `"{prompt_file}"` placeholder when command needs explicit prompt path injection.
  - example: `export BAGAKIT_AGENT_CMD='codex exec {prompt_text}'`
  - escape hatch (debug only): `export BAGAKIT_ALLOW_INTERACTIVE_AGENT_CMD=1`
3. Implement scripts:
- keep `ralphloop.sh` for single-step `pulse`/`run`.
- keep `ralphloop-runner.sh` for infinite outer loop orchestration.
- ensure safety guardrails exist: `RALPHLOOP_MAX_ROUNDS`, `RALPHLOOP_MAX_RUNTIME_SECONDS`, `RALPHLOOP_MAX_INTERVAL_SECONDS`.
- ensure logs are visible and persisted (`RALPHLOOP_LOG_FILE`, optional `RALPHLOOP_JSON_MODE=1`).
4. Dry-run:
- `bash .bagakit/long-run/ralphloop.sh run --endless --dry-run --json`
5. End-to-end test:
- run one closed loop with `bash .bagakit/long-run/ralphloop-runner.sh`.
6. Failure stop policy:
- if `status=failed`, stop and inspect `resume_stderr_tail` before retry.

## Core Design

1. Agent-first detect
- Agent analyzes upstream systems and curates `.bagakit/long-run/bk-execution-table.json`.
- Script validates quality (`validate-table`) before loop execution.

2. Script-driven execution
- Script normalizes rows, ranks actionable work by `status -> confidence -> evidence -> weight -> priority`, syncs `feature-list.json`, and enforces single-item progression.

3. Quality contract
- Planning must include: why now, exact files, commands/checks, verification expectation, risk/rollback.
- Coding pass cannot mark `done` without check evidence.
- Detect/initializer/coding responses must end with `[[BAGAKIT]]` and include a peer line: `- LongRun: Item=...; Status=...; Confidence=...; Evidence=...; Next=...`.
- If ending a session without continuing the loop right now, also include `- LongRunStop: ...` to explain why you stop (and a brief retro if not fully done).

## What this repo contains

- `SKILL.md`: skill entrypoint
- `references/tpl/`: runtime templates
- `scripts/`: apply/validate/doctor/execution helpers

## Install skill locally

```bash
make install-skill BAGAKIT_HOME=~/.bagakit
```

Restart your agent runtime after install.

## Step-by-step Usage

### 1. Apply harness files

```bash
export BAGAKIT_LONG_RUN_SKILL_DIR="<path-to-bagakit-long-run-skill>"
bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/apply-long-run.sh" .
```

Creates:
- `.bagakit/long-run/.gen/detect_prompt.md`
- `.bagakit/long-run/.gen/coding_prompt.md`
- `.bagakit/long-run/.gen/initializer_prompt.md`
- `.bagakit/long-run/.gen/check_and_resume.sh`
- `.bagakit/long-run/.gen/ralphloop.sh`
- `.bagakit/long-run/.gen/ralphloop-runner.sh`
- `.bagakit/long-run/detect_prompt.md` (compat pointer)
- `.bagakit/long-run/initializer_prompt.md` (compat pointer)
- `.bagakit/long-run/coding_prompt.md` (compat pointer)
- `.bagakit/long-run/ralphloop.sh`
- `.bagakit/long-run/ralphloop-runner.sh`
- `.bagakit/long-run/project-profile.json` (auto-detected project context)
- `.bagakit/long-run/feature-list.json`
- `.bagakit/long-run/bk-execution-handoff.md`
- `.bagakit/long-run/bk-execution-table.json`
- `.bagakit/long-run/check_and_resume.sh`
- `.bagakit/long-run/heartbeat.config.json`
- `.bagakit/long-run/heartbeat-schedules.json`
- `.bagakit/long-run/heartbeat.state.json`
- `.bagakit/long-run/inbox/queue.json`
- `AGENTS.md` (`BAGAKIT:LONGRUN` managed block)

### 2. Run detect pass (Agent)

Use `.bagakit/long-run/.gen/detect_prompt.md` to drive one detect pass:
- discover upstream execution systems
- update adapters/guidance in `bk-execution-table.json`
- set `detection.status=ready`

For unknown/custom upstream systems, use `kind=manual` rows.

### 3. Validate execution table quality

```bash
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-execution.py" validate-table .
```

### 4. Runner entry (continuous, recommended)

```bash
bash .bagakit/long-run/ralphloop-runner.sh
```

Behavior:
- if `BAGAKIT_AGENT_CMD`/`BAGAKIT_AGENT_CLI` is configured, loop continuously: pulse -> agent dispatch -> next round
- `run` rejects interactive/TUI-looking commands for known CLIs; use non-interactive command forms.
- if no agent command is configured, runner falls back to one `pulse --endless`
- runner supports safety/observability envs:
  - `RALPHLOOP_MAX_ROUNDS`, `RALPHLOOP_MAX_RUNTIME_SECONDS`, `RALPHLOOP_MAX_INTERVAL_SECONDS`
  - `RALPHLOOP_LOG_FILE` (default `.bagakit/long-run/logs/ralphloop-runner.log`), `RALPHLOOP_JSON_MODE=1`
- `run` dispatch logic:
  - `actionable(todo)` -> run `.gen/initializer_prompt.md`
  - `actionable(in_progress)` -> run `.gen/coding_prompt.md`
  - `endless_prompt_ready` -> run `endless_expand_prompt.md`
- one round = one pass (no initializer+coding in same round)
- strict outcome gate is default: success requires `LONG_RUN_OUTCOME_JSON` markers + schema-valid JSON + evidence-backed status
- failures include deterministic anomaly routing via `anomaly_action`:
  - `blocked_stop` | `retryable` | `needs_detect`
- compatibility rollback switch: `BAGAKIT_LONG_RUN_LEGACY_RC_ONLY=1`
- async message inbox:
  - `.bagakit/long-run/ralph-msg.md` is lazily created.
  - top segment (split by `---`) is injected into current round and then moved to `.bagakit/long-run/ralph-msg.consumed.md` with timestamp + ralph context.

### 5. Pulse entry (single-step fallback)

```bash
bash .bagakit/long-run/ralphloop.sh pulse --endless
```

Behavior:
- always runs `check_and_resume.sh`
- if next row exists, returns actionable item for executor
- if no next row and `--endless`, writes `.bagakit/long-run/endless_expand_prompt.md` for agent-driven plan expansion
- expansion prompt includes detected stack/paths/quality commands from `project-profile.json`

### 6. Check and resume (fallback/direct)

```bash
bash .bagakit/long-run/check_and_resume.sh
```

This runs:
- harness validation
- execution-table quality validation
- detect/plan/guide outputs
- feature-list sync
- structured next-action contract output (`.bagakit/long-run/next-action.json`)

Treat `bash .bagakit/long-run/check_and_resume.sh` as the resume command for every round.

### 7. Initializer pass

Run one initializer pass with:
- `.bagakit/long-run/.gen/initializer_prompt.md`

Output must be a high-quality single-item handoff in:
- `.bagakit/long-run/bk-execution-handoff.md`
- end the response with `[[BAGAKIT]]`, adding `- LongRun: ...`
- add a brief reflection before finalizing outcome (selection correctness / handoff completeness / unblock quality)
- append outcome JSON markers:
  - `<!-- LONG_RUN_OUTCOME_JSON:START -->`
  - `<!-- LONG_RUN_OUTCOME_JSON:END -->`

### 8. Coding pass

Run one coding pass with:
- `.bagakit/long-run/.gen/coding_prompt.md`

Constraints:
- exactly one execution item
- commands/checks executed
- update status to `done` or `blocked`
- end the response with `[[BAGAKIT]]`, adding `- LongRun: ...`
- add a brief reflection before finalizing outcome (evidence sufficiency / scope drift / residual risk)
- append outcome JSON markers:
  - `<!-- LONG_RUN_OUTCOME_JSON:START -->`
  - `<!-- LONG_RUN_OUTCOME_JSON:END -->`

### 9. Close the iteration

```bash
bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/validate-long-run.sh" .
bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-doctor.sh" .
```

Then re-run `bash .bagakit/long-run/check_and_resume.sh` and continue the next single-item round.

## Heartbeat + Flash + Inbox (Standalone v1)

Run one heartbeat tick:

```bash
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-heartbeat.py" tick . --json
```

Preview flash ideas:

```bash
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-heartbeat.py" flash-ideas . --count 5 --json
```

Manage local schedules:

```bash
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-heartbeat.py" schedule-add . --kind every --name "half-hour-loop" --spec 30m
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-heartbeat.py" schedule-list .
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-heartbeat.py" schedule-render . --id <schedule_id>
```

Defaults:
- heartbeat enabled, 30-minute interval, active window `08:00-22:00`
- run context `main`, autonomy mode `full_auto_execute`
- guardrails: allowlist + timeout + command budget + git safety
- no inbox actionable item -> generate 3~5 flash ideas and auto-execute top-1
- delivery is announce + file history; webhook optional

Standalone policy:
- no built-in daemon, no required external service
- `schedule-render` only generates external-scheduler runnable artifacts (`at`, loop script, cron line)
- if `docs/.bagakit/inbox/` exists, heartbeat mirrors notes there; otherwise local inbox paths remain the source of truth

## Upstream Integration Modes

Built-in adapter kinds:
- `bagakit-ft` (reads `.bagakit/ft-harness/index/feats.json`)
- `openspec` (reads `openspec/changes/*`)

Custom/any system:
- `manual` adapter with curated `rows[]` in execution table.
- Manual rows should carry `confidence` (0~1) and `evidence[]` so ranking stays explainable.

If no rows exist yet, `check_and_resume.sh` will now print explicit next actions instead of hard-failing the whole flow.

## Useful Commands

```bash
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-execution.py" validate-table .
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-execution.py" detect .
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-execution.py" plan . --limit 8
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-execution.py" next-action . --json
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-execution.py" guide .
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-execution.py" sync-feature-list .
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-loop.py" pulse . --endless --json
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-loop.py" run . --endless --json
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-loop.py" preflight . --json
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-heartbeat.py" tick . --json
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-heartbeat.py" schedule-list .
```

## Local verification

```bash
./scripts_dev/test.sh
```

## Migration Notes

- See `docs/migration-evidence-gate.md` for upgrading old RC-only runners/executors.
