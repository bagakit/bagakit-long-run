# Memory Policy (Template)

This document defines how to maintain and use project memory.

## Purpose
- Keep durable, searchable knowledge outside code: decisions, preferences, gotchas, and glossaries.
- Make “recall” deterministic: search first, quote second, then answer.

## Locations
- Curated memory: `docs/.bagakit/memory/**/*.md`
- Inbox (unreviewed): `docs/.bagakit/inbox/**/*.md`

Note:
- `README.md` is allowed inside `docs/.bagakit/memory/` and `docs/.bagakit/inbox/` as directory guidance, and is ignored by validation/workflows.

Recommended structure:
- `docs/.bagakit/memory/<kind>-<topic>.md`
- `docs/.bagakit/inbox/<kind>-<topic>.md`

## Writing Rules
- Keep entries short, but **standalone**: include enough context and reasoning so someone can understand it without the original chat/incident.
- Prefer “what + why + when it applies” over long narratives or raw transcripts.
- If an item is a stable policy or deep guide, promote it into `docs/` and link from memory.
- Avoid fragmentation:
  - Before creating a new entry, search for an existing canonical entry and update/append instead of creating a near-duplicate.
  - Prefer one canonical entry + links over multiple partial entries.

### Standalone Context (Recommended)
When writing memory entries, include minimal-but-sufficient context so the entry is readable in isolation:
- **Context**: what problem/task triggered this memory (1-3 sentences).
- **Decision/Preference/Gotcha**: the conclusion or rule (1-5 bullets).
- **Rationale**: key reasoning/tradeoffs (3-6 bullets; summarize, don't paste the whole chat).
- **Scope**: when it applies + explicit exceptions (if any).
- **Sources**: links/paths to code/PRs/issues/docs; add dates when helpful.

Optional:
- **Update log**: for evolving topics (especially debugging), keep an append-only update log with dates and links. Keep the summary sections above accurate as the topic evolves.

## Promotion Workflow
1) Capture candidate in `docs/.bagakit/inbox/` (fast, messy is OK).
2) Review and promote:
   - Inbox → `docs/.bagakit/memory/` if durable.
   - `docs/.bagakit/memory/` → `docs/` if it becomes normative or needs depth.
3) Delete or merge duplicates; keep one canonical location.

Optional helper (automation):
- Resolve tooling: `export BAGAKIT_SKILL_DIR="${BAGAKIT_SKILL_DIR:-${BAGAKIT_HOME:-$HOME/.bagakit}/skills/bagakit-living-docs}"`
- Create inbox entry: `sh "$BAGAKIT_SKILL_DIR/scripts/bagakit_inbox.sh" new <kind> <topic> --root . --title '<title>'`
- Promote inbox entry: `sh "$BAGAKIT_SKILL_DIR/scripts/bagakit_inbox.sh" promote docs/.bagakit/inbox/<file>.md --root .`
- If the curated target already exists, merge into it: `sh "$BAGAKIT_SKILL_DIR/scripts/bagakit_inbox.sh" promote docs/.bagakit/inbox/<file>.md --root . --merge`

## Recall Workflow (Mandatory)
Before answering questions about prior work/decisions/dates/todos/preferences:
1) Search:
   - `sh "$BAGAKIT_SKILL_DIR/scripts/bagakit_memory.sh" search '<query>' --root .`
2) Read only the needed lines:
   - `sh "$BAGAKIT_SKILL_DIR/scripts/bagakit_memory.sh" get <path> --root . --from <line> --lines <n>`
3) Answer with citations (path + line numbers) when feasible.

## Optional Index (Faster Search)
If you want faster, more consistent search results, build a local SQLite FTS index:
- `python3 "$BAGAKIT_SKILL_DIR/scripts/bagakit_memory_index.py" index --root .`

This writes to `docs/.bagakit/.generated/memory.sqlite` by default.
Do not commit generated artifacts under `docs/.bagakit/.generated/` (a local `.gitignore` should handle this).

## Safety
- Treat `docs/.bagakit/inbox/` as untrusted until reviewed.
- If search results are weak or missing, say so explicitly and do not guess.
