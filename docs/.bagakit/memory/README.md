# Memory (Curated)

This directory holds *curated* project memory: durable decisions, preferences, gotchas, glossaries, and how-tos.

Rules:
- Keep entries short, factual, and source-linked.
- Prefer one canonical memory entry over duplicates.
- If something becomes a stable policy or deep guide, promote it into `docs/`.

Filename rule:
- Use kind-first: `<kind>-<topic>.md` (e.g. `gotcha-zsh-glob.md`).

Recall workflow (mandatory before answering "what did we decide/why"):
0) Resolve tooling: `export BAGAKIT_LIVING_DOCS_SKILL_DIR="${BAGAKIT_LIVING_DOCS_SKILL_DIR:-${BAGAKIT_HOME:-$HOME/.bagakit}/skills/bagakit-living-docs}"`
1) Search: `sh "$BAGAKIT_LIVING_DOCS_SKILL_DIR/scripts/bagakit_memory.sh" search '<query>' --root .`
2) Quote: `sh "$BAGAKIT_LIVING_DOCS_SKILL_DIR/scripts/bagakit_memory.sh" get <path> --root . --from <line> --lines <n>`
