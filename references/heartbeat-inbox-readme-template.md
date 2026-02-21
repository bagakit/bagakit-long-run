# Long-Run Heartbeat Inbox

This directory stores heartbeat automation artifacts for standalone long-run execution.

## Files

- `queue.json`: machine-readable pending items.
- `history/*.jsonl`: append-only run history.
- `flash-ideas/*.json`: generated idea candidates before auto-pick.

## Policy

- Keep heartbeat deterministic: all automated picks and outcomes must be recorded.
- Use `docs/.bagakit/inbox/` as optional mirror when available.
- Do not require external services to run this inbox flow.
