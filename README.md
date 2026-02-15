# bagakit-long-run

A Codex skill for building durable harnesses for long-running agent work.

This skill turns the "initializer + coding loop" pattern into reusable project files:
- stable prompts
- machine-readable feature list
- progress handoff log
- repeatable pre-session checks

Reference article:
- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

## What this repo contains

- `SKILL.md`: skill entrypoint loaded by Codex
- `references/`: templates copied into target projects
- `scripts/`: apply/validate/doctor/test tooling

## Install skill locally

```bash
make install-skill CODEX_HOME=~/.codex
```

After install, restart Codex so the skill is reloaded.

## Apply harness to a target project

```bash
export BAGAKIT_LONG_RUN_SKILL_DIR="${BAGAKIT_LONG_RUN_SKILL_DIR:-${CODEX_HOME:-$HOME/.codex}/skills/bagakit-long-run}"
bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/apply-long-run.sh" .
```

This creates:
- `.bagakit-long-run/initial_prompt.md`
- `.bagakit-long-run/coding_prompt.md`
- `.bagakit-long-run/feature-list.json`
- `.bagakit-long-run/claude-progress.md`
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

Each coding session should complete exactly one feature (or mark it blocked).

## Local verification

```bash
./scripts/test.sh
```
