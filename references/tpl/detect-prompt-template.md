# Detect Prompt (Agent-First Execution Mapping)

You are the detect agent for long-run.

Goal: map this project's upstream execution systems into `.bagakit/long-run/bk-execution-table.json` with production-quality planning fields.

## Inputs

- `.bagakit/long-run/bk-execution-table.json`
- repository files and active trackers/specs
- optional upstream systems (examples: OpenSpec, bagakit ft-harness, ticket trackers, custom markdown plans)

## Required Output

Update `bk-execution-table.json` so that:

1. `detection.status=ready`
2. `detection.last_reviewed_at` and `detection.reviewed_by` are filled
3. `detection.upstream_systems` lists all detected systems
4. at least one adapter is enabled and actually matches project artifacts
5. guidance is specific enough to produce high-quality single-item coding handoffs
6. final response ends with `[[BAGAKIT]]` and includes a peer footer line:
   - `- LongRun: Item=detect; Status=ready|blocked; Confidence=0.00~1.00; Evidence=validate-table result; Next=bash .bagakit/long-run/check_and_resume.sh` (or detect rerun command when blocked)
   - If you stop this session without continuing the loop, also add:
     - `- LongRunStop: Reason=<done|blocked|paused>; Retro=<if not done: why not fully complete + unblock/next step>`

## Adapter Rules

- For built-in systems, prefer built-in kinds:
  - `bagakit-ft`
  - `openspec`
- For any other system, use `kind=manual` and map rows manually in `rows[]`.
- Do not hardcode one project/system name into scripts; keep mapping in this table.

Manual rows must include:

- `id`
- `title`
- `status`
- `source_ref`
- `why_now`
- `acceptance_criteria` (at least 2 binary checks)
- `files_to_touch` (at least 1 path)
- `commands` (at least 1 executable command)
- `confidence` (0~1 confidence score for execution success if picked now)
- `evidence` (at least 1 concrete evidence line explaining confidence)
- optional `risks`

## Quality Bar (must satisfy)

Planning fields must make the coding pass deterministic:

- Why this item now
- Exact files to touch
- Commands/checks to run
- Verification/gate expectation
- Risk/rollback note
- Explicit unblock action if blocked

## Validation Command

Run:

```bash
python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-execution.py" validate-table .
```

If validation fails, fix the table and re-run until it passes.
