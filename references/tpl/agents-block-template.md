<!-- BAGAKIT:LONGRUN:START -->
This is a managed block. Do not edit content between START/END tags directly; it may be overwritten by re-running the Bagakit apply script. Edit the Bagakit templates/scripts instead.

Role:
- `long-run` is the execution-loop driver over upstream execution systems.
- Upstream systems keep source-of-truth state; `long-run` normalizes one actionable item at a time.

Tooling:
- Resolve the installed skill dir as: `export BAGAKIT_LONG_RUN_SKILL_DIR="<path-to-bagakit-long-run-skill>"`
- Configure coding CLI dispatch command:
  - preferred: `export BAGAKIT_AGENT_CMD='<non-interactive-agent-command-with-{prompt_file}|{prompt_text}>'`
  - non-interactive form is required to avoid TUI blocking (for example: `export BAGAKIT_AGENT_CMD='codex exec {prompt_text}'`)
  - fallback: `export BAGAKIT_AGENT_CLI='<your-agent-cli>'`
  - escape hatch (debug only): `export BAGAKIT_ALLOW_INTERACTIVE_AGENT_CMD=1`

Loop Protocol (every round):
1. Preferred entry: `bash .bagakit/long-run/ralphloop-runner.sh` (continuous loop; requires `BAGAKIT_AGENT_CMD`/`BAGAKIT_AGENT_CLI`).
2. Single-step fallback: `bash .bagakit/long-run/ralphloop.sh pulse --endless`.
3. Fallback resume command: `bash .bagakit/long-run/check_and_resume.sh`.
4. If detect is not ready, run `.bagakit/long-run/.gen/detect_prompt.md`, update `.bagakit/long-run/bk-execution-table.json`, then re-run resume.
5. One round executes exactly one pass:
  - `next_row.status=todo` -> initializer pass (`.bagakit/long-run/.gen/initializer_prompt.md`)
  - `next_row.status=in_progress` -> coding pass (`.bagakit/long-run/.gen/coding_prompt.md`)
6. Pass success is evidence-gated (not RC-only): output must include `LONG_RUN_OUTCOME_JSON` markers with schema-valid JSON.
6.1 Failure payload exposes deterministic `anomaly_action`: `blocked_stop` | `retryable` | `needs_detect`.
7. After each pass, re-run `bash .bagakit/long-run/check_and_resume.sh` to actively pick the next actionable item and continue.
8. Temporary rollback switch (compatibility only): `BAGAKIT_LONG_RUN_LEGACY_RC_ONLY=1`.

**Outer Orchestrator Runner**:
- `ralphloop-runner.sh` is the outer orchestrator runner; keep it orchestration-only (dispatch/guardrail/log), do not embed domain implementation.
- safety params:
  - `RALPHLOOP_MAX_ROUNDS` (max loop rounds, `0` = unlimited)
  - `RALPHLOOP_MAX_RUNTIME_SECONDS` (max runtime seconds, `0` = unlimited)
  - `RALPHLOOP_MAX_INTERVAL_SECONDS` (max sleep cap for `RALPHLOOP_SLEEP_SECONDS`)
- observability params:
  - `RALPHLOOP_LOG_FILE` (default `.bagakit/long-run/logs/ralphloop-runner.log`)
  - `RALPHLOOP_JSON_MODE=1` (optional)

Orchestrator Setup Steps (must be explicit):
1. select launcher route (`package.json` / `Makefile` / shell).
2. select coding CLI command (`BAGAKIT_AGENT_CMD` preferred).
  - non-interactive command form only; avoid TUI entry commands.
3. set safety/log parameters for runner (max rounds/runtime/interval + log path).
4. verify single-step dispatch: `bash .bagakit/long-run/ralphloop.sh run --endless --dry-run --json`.
5. run continuous orchestrator: `bash .bagakit/long-run/ralphloop-runner.sh`.
6. if loop fails, stop and inspect `resume_stderr_tail` before next retry.

Response Driver (every long-run pass):
- End detect/initializer/coding responses with the project footer block `[[BAGAKIT]]`.
- Add long-run progress as a peer footer line (same level as `- LivingDoc: ...`):
  - `- LongRun: Item=<id|detect>; Status=<ready|todo|in_progress|done|blocked>; Confidence=<0.00~1.00>; Evidence=<validation/tests>; Next=<exact command>`
- If ending current session without continuing the loop, add a peer stop line:
  - `- LongRunStop: Reason=<done|blocked|paused>; Retro=<if not done: why not fully complete + unblock/next step>`
- Append outcome JSON block markers in the final response:
  - `<!-- LONG_RUN_OUTCOME_JSON:START -->`
  - `<!-- LONG_RUN_OUTCOME_JSON:END -->`

Heartbeat Operations (standalone-first):
- Manual tick (one run): `python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-heartbeat.py" tick . --json`
- Flash ideas preview: `python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-heartbeat.py" flash-ideas . --count 5 --json`
- Enable/disable heartbeat via `.bagakit/long-run/heartbeat.config.json` field `enabled`.
- Validate heartbeat contracts:
  - `python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-heartbeat.py" validate-config .`
  - `python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-heartbeat.py" validate-schedules .`
- Local schedule management:
  - `schedule-add`: add `at|every|cron` records into `.bagakit/long-run/heartbeat-schedules.json`
  - `schedule-render`: generate external-scheduler runnable artifacts (one-shot script / loop script / cron line)
- External scheduler mounting is optional and out-of-process; no built-in daemon is required.

Detect Rules:
- Detect is agent-driven and rule-based; do not hardcode project-specific names in scripts.
- Map upstream systems to adapters (`bagakit-ft`, `openspec`, `manual`) in `.bagakit/long-run/bk-execution-table.json`.
- Every execution row must include: why-now, binary acceptance criteria, files to touch, commands, and risk/rollback notes.
- If no actionable row remains and loop is in `--endless` mode, use `.bagakit/long-run/endless_expand_prompt.md` to expand plan first, then continue.
- Optional async message inbox:
  - write message segments into `.bagakit/long-run/ralph-msg.md`, split by `---`.
  - each run round consumes only the top segment and prepends consumed history to `.bagakit/long-run/ralph-msg.consumed.md`.
- Managed generated files:
  - canonical generated scripts/prompts are under `.bagakit/long-run/.gen/`.
  - root-level `check_and_resume.sh` / `ralphloop.sh` / `ralphloop-runner.sh` are compatibility wrappers.

Validation:
- `bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/validate-long-run.sh" .`
- `bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-doctor.sh" .`
<!-- BAGAKIT:LONGRUN:END -->
