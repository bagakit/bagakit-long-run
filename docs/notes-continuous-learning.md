---
title: Continuous Learning (Default)
required: false
sop:
  - At the end of a Codex work session, capture a draft learning note into `docs/.bagakit/inbox/` (manual or via `sh "$BAGAKIT_SKILL_DIR/scripts/bagakit_learning.sh" extract --root . --last`). The default extractor upserts into a daily file to avoid fragmentation.
  - Weekly (or before major releases), review `docs/.bagakit/inbox/` and promote durable items into `docs/.bagakit/memory/`.
  - When promoting, keep entries short and source-linked; prefer `decision-*`/`preference-*`/`gotcha-*`/`howto-*` over long narratives. If the curated target already exists, merge instead of creating duplicates.
---

# Continuous Learning (Default)

This project uses Bagakit memory (`docs/.bagakit/{inbox,memory}/`) to capture reusable patterns from day-to-day work.

## Why SOP (no hooks)
Codex does not provide reliable stop hooks. The SOP above is the default trigger mechanism.
