# Project SOP

This SOP is generated from docs frontmatter. Do not edit manually.

## Update Requirements
- When a document with SOP frontmatter changes, regenerate this file and commit the result:
  - `export BAGAKIT_SKILL_DIR="${BAGAKIT_SKILL_DIR:-${CODEX_HOME:-$HOME/.codex}/skills/bagakit-living-docs}"`
  - `sh "$BAGAKIT_SKILL_DIR/scripts/bagakit_generate_sop.sh" .`
- Add new SOP items by updating the `sop` list in the source document frontmatter.
- Keep SOP items small and actionable; use the source document for details.

## SOP Items

### Maintaining Reusable Items (可复用项维护)
Source: `docs/norms-maintaining-reusable-items.md`
- At the start of each iteration, check whether the project needs a new reusable-items catalog for an active domain (coding/design/writing/knowledge) and create/update it.
- When introducing or updating a reusable item (component/library/mechanism/token/style pattern/index; including API/behavior/ownership/deprecation), verify the relevant catalog entry is correct and update it in the same change.
- When SOP/frontmatter changes in these docs, regenerate `docs/must-sop.md` with `sh "$BAGAKIT_SKILL_DIR/scripts/bagakit_generate_sop.sh" .`.

### Continuous Learning (Default)
Source: `docs/notes-continuous-learning.md`
- At the end of a Codex work session, capture a draft learning note into `docs/.bagakit/inbox/` (manual or via `sh "$BAGAKIT_SKILL_DIR/scripts/bagakit_learning.sh" extract --root . --last`). The default extractor upserts into a daily file to avoid fragmentation.
- Weekly (or before major releases), review `docs/.bagakit/inbox/` and promote durable items into `docs/.bagakit/memory/`.
- When promoting, keep entries short and source-linked; prefer `decision-*`/`preference-*`/`gotcha-*`/`howto-*` over long narratives. If the curated target already exists, merge instead of creating duplicates.

