---
title: Maintaining Reusable Items (可复用项维护)
required: false
sop:
  - At the start of each iteration, check whether the project needs a new reusable-items catalog for an active domain (coding/design/writing/knowledge) and create/update it.
  - When introducing or updating a reusable item (component/library/mechanism/token/style pattern/index; including API/behavior/ownership/deprecation), verify the relevant catalog entry is correct and update it in the same change.
  - When SOP/frontmatter changes in these docs, regenerate `docs/must-sop.md` with `sh "$BAGAKIT_SKILL_DIR/scripts/bagakit_generate_sop.sh" .`.
---

# Maintaining Reusable Items (可复用项维护)

## What
"Reusable items" are project-local assets that are worth **reusing and converging on** across iterations.

Important: "reusable" describes the *items/content* (assets you repeatedly apply), not that this document is a cross-project template to copy.
This document is a maintained, project-specific governance entrypoint for how reusable items are discovered, recorded, and iterated.

## Optional Mechanism
This mechanism is optional. If your project does not benefit from reusable-items governance:
- Delete this doc and any `docs/notes-reusable-items-*.md` catalogs, or keep them unused.
- Record the decision (and rationale) in project memory so it doesn't churn.

Examples by domain:
- Coding: reusable components, libraries/packages, mechanisms (error handling patterns, feature flags, logging/metrics conventions).
- Design: color/tokens, component library, design specs and workflows.
- Writing: paragraph patterns, terminology/style examples.
- Knowledge management: canonical indexes, high-signal flash cards/notes, reusable query patterns.

## What This Is Not
- A project charter (goals/scope/principles). Keep that in a separate "Project Charter" doc if needed.
- A checklist doc by itself. Checklists are one way to *apply* reusable rules, but catalogs are about *inventory and discoverability*.

## Reuse Levels (Must / Should / Nice To Have)
Not all reusable items should be treated equally. Use levels to keep the system practical:
- **MUST reuse**: the default standard for the project. If you don't use it, you must document an explicit exception (with rationale and risk).
- **SHOULD reuse**: preferred. If you don't use it, document the tradeoff briefly (no formal exception needed).
- **NICE TO HAVE**: optional/candidate. Encourage trial usage, but do not block work.

Promotion/demotion rule of thumb:
- NICE TO HAVE -> SHOULD/MUST when it is stable, repeatedly used, and reduces duplicated effort.
- MUST -> SHOULD when the constraint becomes too costly or a better standard emerges (record the replacement/migration).

## Where To Put Catalogs (Doc Types)
These catalogs are usually best as `notes-*` (informational inventories), while enforcement rules live in `norms-*`.

Recommended filenames:
- `notes-reusable-items-coding.md`
- `notes-reusable-items-design.md`
- `notes-reusable-items-writing.md`
- `notes-reusable-items-knowledge.md`

## Entry Format (Recommended)
In domain catalogs (`notes-reusable-items-*.md`), each reusable item entry should include:
- **Preferred**: use a Markdown table to keep the catalog compact and scannable.
- Columns to include (at minimum): Item, MUST/SHOULD/NICE, When to Use, Source of Truth.
- Optional columns: Owner, Status, Notes.

## Fast Path: When Reuse Doesn’t Cover Your Need
When you need something in the target project and the current reusable items don't cover it:
1) Check catalogs first (pick the closest domain):
   - `docs/notes-reusable-items-design.md` (design/UI assets, interaction patterns)
   - `docs/notes-reusable-items-coding.md` (components/libraries/mechanisms/tools)
2) If it fits: use it or do a small extension (prefer keeping API stable; document the change if behavior/contracts change).
3) If it doesn't fit: add a new catalog entry first (choose MUST/SHOULD/NICE, scope/when-to-use, and source-of-truth location), then implement.

## Maintenance Rules (How It Grows)
- Start small: create a catalog only when the domain becomes active.
- Each time something becomes "the standard", add one entry with:
  - What it is
  - Where it lives (paths/links)
  - When to use it (and when not to)
  - Owner/maintainer (optional but helpful)
- Each time you deprecate something, update the entry with the replacement and migration notes.
- Avoid duplication: one canonical entry per item; link elsewhere.
