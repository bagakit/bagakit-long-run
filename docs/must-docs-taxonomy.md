# Docs Taxonomy Guidelines (Template)

## Scope
This document defines the `docs/` taxonomy: categories, naming rules, and frontmatter templates.

## Categories (Non-System Docs)
- Norms: `norms-*.md`
- Architecture: `architecture-*.md`
- Guidelines: `guidelines-*.md`
- Notes: `notes-*.md`
- Runbook (optional): `runbook-*.md`
- Manual test (optional): `manual-test-*.md`

## Memory (Project Knowledge Base)
Keep a lightweight, searchable "project memory" under `docs/.bagakit/` (Bagakit-internal), so projects don't need extra top-level directories:
- Curated memory: `docs/.bagakit/memory/**/*.md`
- Inbox (unreviewed): `docs/.bagakit/inbox/**/*.md`

Rules:
- Use `docs/.bagakit/memory/` for durable, reusable knowledge (decisions, preferences, gotchas, glossaries).
- Use `docs/.bagakit/inbox/` for raw candidates (from tasks/PRs/incidents). Promote to `docs/.bagakit/memory/` or a `docs/*.md` doc after review.
- Avoid duplicating long explanations: prefer a short memory entry + links to code/PR/issues/docs.

### Memory Naming Rules
Use type-first naming: `<kind>-<topic>.md`.
Allowed kinds:
- `decision-*.md`
- `preference-*.md`
- `gotcha-*.md`
- `glossary-*.md`
- `howto-*.md`

## System Docs
All system-level docs use the `must-` prefix to signal mandatory reading and prevent naming conflicts.
Treat all `docs/must-*.md` docs as mandatory reading (projects may add more `must-*` docs over time).

Required system docs:
- `must-guidebook.md`: reading map and doc index
- `must-sop.md`: generated SOP output (do not hand-edit)
- `must-docs-taxonomy.md`: this file
- `must-memory.md`: memory conventions (how to write, search, and promote memory)

## Naming Rules (Non-System Docs)
Use lowercase kebab-case filenames with the category first: `<type>-<topic>.md`.
Example: `norms-dev.md`, `notes-voice-input.md`, `guidelines-ui-components.md`.

### Reusable Items Catalogs (Topic Convention)
If you maintain "reusable items" catalogs, encode it in the topic (do not add a new doc type):
- `notes-reusable-items-<domain>.md`

Examples:
- `notes-reusable-items-coding.md`
- `notes-reusable-items-design.md`
- `notes-reusable-items-writing.md`
- `notes-reusable-items-knowledge.md`

## Canonicalization (Avoid Duplicate Docs)
- Before creating a new `docs/<type>-<topic>.md`, search for an existing doc or memory entry that already covers the topic and update it instead of creating a near-duplicate.
- Prefer one canonical doc per topic, and link from other docs instead of duplicating explanations.
- Avoid splitting the same `<topic>` across multiple doc types (e.g. both `notes-foo.md` and `guidelines-foo.md`) unless there is a clear reason and cross-links.

## Frontmatter Templates
All non-system docs must include frontmatter with `title`, `required`, and `sop` fields.

### Optional: Response Directives (Driver Statements)
Docs may optionally define response directives to guide agent output when a condition applies (e.g., debugging).

Frontmatter shape:
```
directives:
  - DEBUG: When debugging, include a final-response attempt summary, using `<problem> (try-<n>): <one-line approach>`.
```

Notes:
- `directives` are optional and do not replace `sop`.
- The response footer format is standardized under `[[BAGAKIT]]` (see AGENTS.md / must-guidebook.md).

### Norms
```
---
title: <Norms Title>
required: true
sop:
  - Read this doc before touching the affected area.
  - Update this doc when rules or constraints change.
  - Regenerate must-sop.md after updating this doc.
---
```

### Architecture
```
---
title: <Architecture Title>
required: false
sop:
  - Read this doc before architecture changes or refactors.
  - Update this doc when components or boundaries change.
  - Regenerate must-sop.md after updating this doc.
---
```

### Guidelines
```
---
title: <Guidelines Title>
required: false
sop:
  - Follow this doc when implementing or reviewing related UI/UX or engineering patterns.
  - Update this doc when conventions change.
  - Regenerate must-sop.md after updating this doc.
---
```

### Notes
```
---
title: <Notes Title>
required: false
sop:
  - Read this doc when working on the related feature area.
  - Update this doc when implementation details or gotchas change.
  - Regenerate must-sop.md after updating this doc.
---
```

### Runbook (optional)
```
---
title: <Runbook Title>
required: false
sop:
  - Read this doc before operational changes or incident response.
  - Update this doc when procedures or tooling change.
  - Regenerate must-sop.md after updating this doc.
---
```

### Manual Test (optional)
```
---
title: <Manual Test Title>
required: false
sop:
  - Run this checklist before release or when related features change.
  - Update this doc when verification steps change.
  - Regenerate must-sop.md after updating this doc.
---
```

## Memory Frontmatter (Recommended)
Memory entries are allowed to be short and iterative. Frontmatter is recommended to keep them searchable and reviewable.

```
---
title: <Short memory title>
kind: decision|preference|gotcha|glossary|howto
confidence: low|medium|high
tags:
  - <tag>
sources:
  - <path/to/file>
  - <link/to/pr-or-issue>
created: YYYY-MM-DDTHH:MM:SSZ
updated: YYYY-MM-DDTHH:MM:SSZ
---
```

## System Doc Frontmatter (Optional)
If the project enforces frontmatter on all docs, use:
```
---
title: <System Doc Title>
required: true
sop:
  - Keep this system doc aligned with doc taxonomy and project changes.
---
```
