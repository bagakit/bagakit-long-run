# Migration: Evidence-Gated Long-Run Loop

This migration switches `long-run` from RC-only success to outcome-evidence gating.

## What changed

- `run` now executes exactly one pass per round.
- Pass success requires outcome JSON markers and schema-valid content.
- Environment preflight (`workspace/tmp/cache writable`) runs before prompt dispatch.
- Semantic `blocked/retry/no_action` no longer counts as `run_completed`.
- Failure JSON now includes `anomaly_codes` + deterministic `anomaly_action` (`blocked_stop|retryable|needs_detect`).

## Required executor output

At the end of each pass response (initializer/coding/endless_expand), append:

- `<!-- LONG_RUN_OUTCOME_JSON:START -->`
- JSON object matching `references/schema/long-run-outcome.schema.json`
- `<!-- LONG_RUN_OUTCOME_JSON:END -->`

## Rollout steps

1. Re-apply harness files:
   - `bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/apply-long-run.sh" . --force`
2. Run self-check + resume:
   - `bash .bagakit/long-run/check_and_resume.sh`
3. Validate preflight:
   - `python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-loop.py" preflight . --json`
4. Smoke test one round:
   - `bash .bagakit/long-run/ralphloop.sh run --endless --dry-run --json`

## Temporary compatibility mode

If your executor has not emitted outcome JSON yet, use temporary rollback mode:

- `export BAGAKIT_LONG_RUN_LEGACY_RC_ONLY=1`

Then fix executor output and remove this env as soon as possible.
