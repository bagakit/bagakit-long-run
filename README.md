# bagakit-long-run

A Bagakit Agent skill for building durable harnesses for long-running agent work.

This skill turns initializer/coding loops into reusable project files, and can proactively couple to upstream execution systems via an execution table.

- stable prompts
- machine-readable feature list
- BK execution handoff
- execution-table adapters (`bagakit-ft`, `openspec`)
- repeatable pre-session checks

Reference article:
- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

## What this repo contains

- `SKILL.md`: skill entrypoint loaded by Bagakit Agent
- `references/`: templates copied into target projects
- `scripts/`: apply/validate/doctor/test tooling

## Install skill locally

```bash
make install-skill BAGAKIT_HOME=~/.bagakit
```

After install, restart Bagakit Agent so the skill is reloaded.

## Apply harness to a target project

```bash
export BAGAKIT_LONG_RUN_SKILL_DIR="${BAGAKIT_LONG_RUN_SKILL_DIR:-${BAGAKIT_HOME:-$HOME/.bagakit}/skills/bagakit-long-run}"
bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/apply-long-run.sh" .
```

This creates:
- `.bagakit-long-run/initial_prompt.md`
- `.bagakit-long-run/coding_prompt.md`
- `.bagakit-long-run/feature-list.json`
- `.bagakit-long-run/bk-execution-handoff.md`
- `.bagakit-long-run/bk-execution-table.json`
- `.bagakit-long-run/init.sh`

## Suggested work loop

```bash
sh .bagakit-long-run/init.sh
```

Then run:
1. initializer agent with `.bagakit-long-run/initial_prompt.md`
2. coding agent with `.bagakit-long-run/coding_prompt.md`
3. `bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/validate-long-run.sh" .`
4. repeat

Each coding session should complete exactly one execution item (or mark it blocked).

## Execution-table bridge

```bash
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/bagakit_long_run_execution.py" detect .
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/bagakit_long_run_execution.py" plan . --limit 8
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/bagakit_long_run_execution.py" guide .
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/bagakit_long_run_execution.py" sync-feature-list .
```

Default adapters:
- `bagakit-ft` (`.bagakit-ft/index/feats.json`)
- `openspec` (`openspec/changes/*`)

## Universal Principles

- Evidence over assumptions: detect emits signals and rule context, not hardcoded yes/no coupling.
- Normalize before deciding: convert upstream systems into a shared execution-row model, then prioritize from that model.
- Guidance over rigid policy: define analysis/planning checklists as rules, but keep final judgment with the agent.
- Loose coupling by adapters: keep system-specific logic at adapter boundaries so long-run core remains stable.
- Traceable execution intent: decisions and rationale should always be written to `bk-execution-handoff.md`.

## Design Principle: Avoid Assumptions And Tight Coupling

Core logic:
- Agent systems are replaceable, but execution facts are not.
- Therefore long-run should couple to explicit artifacts and rules, not tool names, model names, or legacy file names.

Required practice:
- Detect by rule sets in `bk-execution-table.json` (`path_exists`, `json_has_key`, `glob_count_ge`, etc.), not by guessing from naming conventions.
- Keep coupling only at adapter boundaries (`bagakit-ft`, `openspec`, future adapters), and keep the core loop adapter-agnostic.
- Use guidance rules to constrain planning quality, while preserving agent judgment for context-specific tradeoffs.

Self-check checklist:
- If a new integration is added, ask: "Can this be expressed as adapter rules instead of hardcoded branch logic?"
- If a fallback is added, ask: "Is this a stable contract, or a hidden legacy assumption?"
- If vendor-specific terms appear in runtime behavior, ask: "Can this be renamed to bagakit-neutral execution semantics?"

## Local verification

```bash
./scripts/test.sh
```
