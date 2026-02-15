# Guidebook (Template)

This guidebook is a reading map. Keep it stable and index-style; do not duplicate volatile details.

## How to Use
- First-time: read in order.
- Every work session: re-open the system docs below (do not rely on memory). System docs are `docs/must-*.md` (all `must-*` are mandatory reading).
- Tooling: resolve the installed skill dir as `export BAGAKIT_SKILL_DIR="${BAGAKIT_SKILL_DIR:-${BAGAKIT_HOME:-$HOME/.bagakit}/skills/bagakit-living-docs}"`.
- If you adopt reusable-items governance: follow `docs/norms-maintaining-reusable-items.md` and update the relevant `docs/notes-reusable-items-*.md` catalogs when adding/deprecating reusable items.
- If you adopt reusable-items catalogs: when you need to find a reusable item quickly, check the `notes-reusable-items-*.md` catalogs (or run `sh "$BAGAKIT_SKILL_DIR/scripts/bagakit_reusable_items.sh" search '<query>' --root .`).
- If your project defines response directives (`directives:` in frontmatter, visible in `docs/must-sop.md`): apply them and include directive outputs in the `[[BAGAKIT]]` footer when applicable.
- When in doubt: follow system docs first; prefer updating an existing canonical doc/memory entry over creating duplicates.
- When answering “what did we decide/why/todos”: follow the recall workflow in `must-memory.md` (search → quote → answer).

## Fast Path
1) System docs
- `must-guidebook.md`
- `must-docs-taxonomy.md`
- `must-sop.md`
- `must-memory.md`
- Any other `must-*.md` docs in this repo (if present).

2) Project intent and constraints
- Link to the most authoritative spec or README.
- Consider adding a suggested charter doc (e.g. `docs/notes-project-charter.md`) if the project lacks a stable intent/scope reference.
- If this repo already has many docs and you're adopting Bagakit: consider adding/reading `docs/notes-adopting-living-docs.md` (adoption playbook).

3) Current changes or proposals
- Link to active proposals or change logs.

4) Build/run entrypoints
- Link to the primary entrypoints and scripts.

## Memory (Project Knowledge Base)
- Curated: `docs/.bagakit/memory/**/*.md`
- Inbox: `docs/.bagakit/inbox/**/*.md`

Use memory for:
- Reusable facts and decisions you want the agent/team to recall quickly.
- Gotchas and “this bit me before” notes with pointers to code/PRs/issues.

Continuous learning:
- Follow `must-sop.md` (and `docs/notes-continuous-learning.md` if present) to capture session learnings into `docs/.bagakit/inbox/` and promote them into curated memory.

Promotion rule:
- Inbox → curated memory for durable items; curated memory → `docs/*.md` when it becomes a stable policy or deep guide.

## Deep Dives
- Add domain-specific docs by category (norms, guidelines, notes).
- Use taxonomy suffixes and keep ordering consistent.
- Start with `docs/norms-maintaining-reusable-items.md` if present.

## Docs Maintenance
- This guidebook must reference `must-docs-taxonomy.md`.
- When docs are added/renamed, update this guidebook.
- Do not move system docs without updating AGENTS.md.

## Response Footer
- Every task response must end with:
  - `[[BAGAKIT]]`
  - `- LivingDoc: ...`
  - Optional: directive outputs when applicable (e.g. `  - (DEBUG) ...`).
