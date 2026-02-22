<!-- BAGAKIT:LONGRUN:START -->
This is a managed block. Do not edit content between START/END tags directly; it may be overwritten by re-running the Bagakit apply script. Edit the Bagakit templates/scripts instead.

Role:
- `long-run` is the execution-loop driver over upstream execution systems.
- Upstream systems keep source-of-truth state; `long-run` normalizes one actionable item at a time.

Tooling:
- Resolve the installed skill dir as: `export BAGAKIT_LONG_RUN_SKILL_DIR="${BAGAKIT_LONG_RUN_SKILL_DIR:-${BAGAKIT_HOME:-$HOME/.bagakit}/skills/bagakit-long-run}"`
- Configure coding CLI dispatch command:
  - preferred: `export BAGAKIT_AGENT_CMD='<non-interactive-agent-command-with-{prompt_file}|{prompt_text}>'`
  - non-interactive form is required to avoid TUI blocking (for example: `export BAGAKIT_AGENT_CMD='codex exec {prompt_text}'`)
  - fallback: `export BAGAKIT_AGENT_CLI='<your-agent-cli>'`
  - escape hatch (debug only): `export BAGAKIT_ALLOW_INTERACTIVE_AGENT_CMD=1`

Loop Protocol (every round):
1. Preferred entry: `bash .bagakit/long-run/ralphloop-runner.sh` (continuous loop; requires `BAGAKIT_AGENT_CMD`/`BAGAKIT_AGENT_CLI`).
2. Single-step fallback: `bash .bagakit/long-run/ralphloop.sh pulse --endless`.
3. Fallback resume command: `bash .bagakit/long-run/check_and_resume.sh`.
4. If detect is not ready, run `.bagakit/long-run/detect_prompt.md`, update `.bagakit/long-run/bk-execution-table.json`, then re-run resume.
5. Run initializer pass with `.bagakit/long-run/initializer_prompt.md` and produce a single-item handoff.
6. Run coding pass with `.bagakit/long-run/coding_prompt.md`, execute exactly one item, and update status/check evidence.
7. After each pass, re-run `bash .bagakit/long-run/check_and_resume.sh` to actively pick the next actionable item and continue.

Orchestrator Setup Steps (must be explicit):
1. select launcher route (`package.json` / `Makefile` / shell).
2. select coding CLI command (`BAGAKIT_AGENT_CMD` preferred).
  - non-interactive command form only; avoid TUI entry commands.
3. verify single-step dispatch: `bash .bagakit/long-run/ralphloop.sh run --endless --dry-run --json`.
4. run continuous orchestrator: `bash .bagakit/long-run/ralphloop-runner.sh`.
5. if loop fails, stop and inspect `resume_stderr_tail` before next retry.

Response Driver (every long-run pass):
- End detect/initializer/coding responses with the project footer block `[[BAGAKIT]]`.
- Add long-run progress as a peer footer line (same level as `- LivingDoc: ...`):
  - `- LongRun: Item=<id|detect>; Status=<ready|todo|in_progress|done|blocked>; Confidence=<0.00~1.00>; Evidence=<validation/tests>; Next=<exact command>`
- If ending current session without continuing the loop, add a peer stop line:
  - `- LongRunStop: Reason=<done|blocked|paused>; Retro=<if not done: why not fully complete + unblock/next step>`

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

Validation:
- `bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/validate-long-run.sh" .`
- `bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-doctor.sh" .`
<!-- BAGAKIT:LONGRUN:END -->
