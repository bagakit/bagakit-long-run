# bagakit-long-run

A Bagakit skill focused on driving long-running delivery loops.

`long-run` is an execution driver:
- it does not own worktree state
- it does not replace upstream change systems
- it enforces a repeatable loop: detect -> init -> execute one item -> verify -> continue

Reference:
- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

## Core Design

1. Agent-first detect
- Agent analyzes upstream systems and curates `.bagakit/long-run/bk-execution-table.json`.
- Script validates quality (`validate-table`) before loop execution.

2. Script-driven execution
- Script normalizes rows, ranks actionable work, syncs `feature-list.json`, and enforces single-item progression.

3. Quality contract
- Planning must include: why now, exact files, commands/checks, verification expectation, risk/rollback.
- Coding pass cannot mark `done` without check evidence.
- Detect/initializer/coding responses must end with `[[BAGAKIT]]` and include a peer line: `- LongRun: Item=...; Status=...; Evidence=...; Next=...`.

## What this repo contains

- `SKILL.md`: skill entrypoint
- `references/`: runtime templates
- `scripts/`: apply/validate/doctor/execution helpers

## Install skill locally

```bash
make install-skill BAGAKIT_HOME=~/.bagakit
```

Restart your agent runtime after install.

## Step-by-step Usage

### 1. Apply harness files

```bash
export BAGAKIT_LONG_RUN_SKILL_DIR="${BAGAKIT_LONG_RUN_SKILL_DIR:-${BAGAKIT_HOME:-$HOME/.claude}/skills/bagakit-long-run}"
bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/apply-long-run.sh" .
```

Creates:
- `.bagakit/long-run/detect_prompt.md`
- `.bagakit/long-run/initial_prompt.md`
- `.bagakit/long-run/coding_prompt.md`
- `.bagakit/long-run/feature-list.json`
- `.bagakit/long-run/bk-execution-handoff.md`
- `.bagakit/long-run/bk-execution-table.json`
- `.bagakit/long-run/init.sh`
- `AGENTS.md` (`BAGAKIT:LONGRUN` managed block)

### 2. Run detect pass (Agent)

Use `.bagakit/long-run/detect_prompt.md` to drive one detect pass:
- discover upstream execution systems
- update adapters/guidance in `bk-execution-table.json`
- set `detection.status=ready`

For unknown/custom upstream systems, use `kind=manual` rows.

### 3. Validate execution table quality

```bash
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/bagakit_long_run_execution.py" validate-table .
```

### 4. Start session init

```bash
sh .bagakit/long-run/init.sh
```

This runs:
- harness validation
- execution-table quality validation
- detect/plan/guide outputs
- feature-list sync

### 5. Initializer pass

Run one initializer pass with:
- `.bagakit/long-run/initial_prompt.md`

Output must be a high-quality single-item handoff in:
- `.bagakit/long-run/bk-execution-handoff.md`
- end the response with `[[BAGAKIT]]`, adding `- LongRun: ...` as a peer line to `- LivingDoc: ...`

### 6. Coding pass

Run one coding pass with:
- `.bagakit/long-run/coding_prompt.md`

Constraints:
- exactly one execution item
- commands/checks executed
- update status to `done` or `blocked`
- end the response with `[[BAGAKIT]]`, adding `- LongRun: ...` as a peer line to `- LivingDoc: ...`

### 7. Close the iteration

```bash
bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/validate-long-run.sh" .
bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/bagakit_long_run_doctor.sh" .
```

Then re-run `sh .bagakit/long-run/init.sh` and continue the next single-item round.

## Upstream Integration Modes

Built-in adapter kinds:
- `bagakit-ft` (reads `.bagakit/ft-harness/index/feats.json`)
- `openspec` (reads `openspec/changes/*`)

Custom/any system:
- `manual` adapter with curated `rows[]` in execution table.

If no rows exist yet, `init.sh` will now print explicit next actions instead of hard-failing the whole flow.

## Useful Commands

```bash
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/bagakit_long_run_execution.py" validate-table .
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/bagakit_long_run_execution.py" detect .
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/bagakit_long_run_execution.py" plan . --limit 8
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/bagakit_long_run_execution.py" guide .
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/bagakit_long_run_execution.py" sync-feature-list .
```

## Local verification

```bash
./scripts/test.sh
```
