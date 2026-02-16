<!-- BAGAKIT:LONGRUN:START -->
This is a managed block. Do not edit content between START/END tags directly; it may be overwritten by re-running the Bagakit apply script. Edit the Bagakit templates/scripts instead.

Role:
- `long-run` is the execution-loop driver over upstream execution systems.
- Upstream systems keep source-of-truth state; `long-run` normalizes one actionable item at a time.

Tooling:
- Resolve the installed skill dir as: `export BAGAKIT_LONG_RUN_SKILL_DIR="${BAGAKIT_LONG_RUN_SKILL_DIR:-${BAGAKIT_HOME:-$HOME/.claude}/skills/bagakit-long-run}"`

Loop Protocol (every round):
1. Run `sh .bagakit/long-run/init.sh`.
2. If detect is not ready, run `.bagakit/long-run/detect_prompt.md`, update `.bagakit/long-run/bk-execution-table.json`, then re-run init.
3. Run initializer pass with `.bagakit/long-run/initial_prompt.md` and produce a single-item handoff.
4. Run coding pass with `.bagakit/long-run/coding_prompt.md`, execute exactly one item, and update status/check evidence.
5. Re-run `sh .bagakit/long-run/init.sh` to actively pick the next actionable item and continue.

Detect Rules:
- Detect is agent-driven and rule-based; do not hardcode project-specific names in scripts.
- Map upstream systems to adapters (`bagakit-ft`, `openspec`, `manual`) in `.bagakit/long-run/bk-execution-table.json`.
- Every execution row must include: why-now, binary acceptance criteria, files to touch, commands, and risk/rollback notes.

Validation:
- `bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/validate-long-run.sh" .`
- `bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/bagakit_long_run_doctor.sh" .`
<!-- BAGAKIT:LONGRUN:END -->
