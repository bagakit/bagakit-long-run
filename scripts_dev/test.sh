#!/usr/bin/env bash
set -euo pipefail

dev_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill_root="$(cd "${dev_script_dir}/.." && pwd)"
runtime_scripts_dir="${skill_root}/scripts"

tmp="$(mktemp -d -t bagakit-long-run-test.XXXXXX)"
trap 'rm -rf "$tmp"' EXIT

project="${tmp}/project"
mkdir -p "$project"
harness_dir="${project}/.bagakit/long-run"
ft_harness_dir="${project}/.bagakit/ft-harness"

echo "[test] docs + template policy audit"
python3 - <<PY
import json
from pathlib import Path

root = Path(r"${skill_root}")
doc = (root / "docs" / "notes-long-run-agent-first-detect.md").read_text(encoding="utf-8")
required_phrases = [
    "no hard dependency on external systems",
    "optional adapters",
]
for phrase in required_phrases:
    if phrase not in doc:
        raise SystemExit(f"missing policy phrase in docs/notes-long-run-agent-first-detect.md: {phrase}")

resume_doc = (root / "docs" / "guidelines-long-run-resume.md").read_text(encoding="utf-8")
for phrase in ("bash .bagakit/long-run/check_and_resume.sh", "LongRunStop:"):
    if phrase not in resume_doc:
        raise SystemExit(f"missing resume/stop contract phrase in docs/guidelines-long-run-resume.md: {phrase}")

table = json.loads((root / "references" / "bk-execution-table-template.json").read_text(encoding="utf-8"))
selection = table.get("selection", {})
if selection.get("strategy") != "status_confidence_evidence_priority":
    raise SystemExit("unexpected selection.strategy in execution table template")
adapters = table.get("adapters", [])
kinds = {str(a.get("kind", "")) for a in adapters if isinstance(a, dict)}
for kind in ("bagakit-ft", "openspec", "manual"):
    if kind not in kinds:
        raise SystemExit(f"missing built-in adapter kind in template: {kind}")

detect_prompt = (root / "references" / "detect-prompt-template.md").read_text(encoding="utf-8")
for phrase in ("confidence", "evidence"):
    if phrase not in detect_prompt:
        raise SystemExit(f"missing phrase in detect prompt template: {phrase}")
PY

echo "[test] apply harness"
bash "${runtime_scripts_dir}/apply-long-run.sh" "$project"

[[ -f "${harness_dir}/bk-execution-handoff.md" ]]
[[ -f "${harness_dir}/bk-execution-table.json" ]]
[[ -f "${harness_dir}/detect_prompt.md" ]]
[[ -f "${harness_dir}/check_and_resume.sh" ]]
[[ ! -e "${harness_dir}/init.sh" ]]
[[ ! -e "${harness_dir}/initial_prompt.md" ]]
[[ -f "${project}/AGENTS.md" ]]
grep -q "<!-- BAGAKIT:LONGRUN:START -->" "${project}/AGENTS.md"
grep -q "<!-- BAGAKIT:LONGRUN:END -->" "${project}/AGENTS.md"
grep -q "\[\[BAGAKIT\]\]" "${project}/AGENTS.md"
grep -q "LongRun:" "${project}/AGENTS.md"
grep -q "Confidence=" "${project}/AGENTS.md"
grep -q "LongRunStop:" "${project}/AGENTS.md"
grep -q "\[\[BAGAKIT\]\]" "${harness_dir}/detect_prompt.md"
grep -q "LongRun:" "${harness_dir}/detect_prompt.md"
grep -q "Confidence=" "${harness_dir}/detect_prompt.md"
grep -q "LongRunStop:" "${harness_dir}/detect_prompt.md"
grep -q "\[\[BAGAKIT\]\]" "${harness_dir}/initializer_prompt.md"
grep -q "LongRun:" "${harness_dir}/initializer_prompt.md"
grep -q "Confidence=" "${harness_dir}/initializer_prompt.md"
grep -q "LongRunStop:" "${harness_dir}/initializer_prompt.md"
grep -q "\[\[BAGAKIT\]\]" "${harness_dir}/coding_prompt.md"
grep -q "LongRun:" "${harness_dir}/coding_prompt.md"
grep -q "Confidence=" "${harness_dir}/coding_prompt.md"
grep -q "LongRunStop:" "${harness_dir}/coding_prompt.md"
grep -q "\[\[BAGAKIT\]\]" "${harness_dir}/bk-execution-handoff.md"
grep -q "^- LongRun:" "${harness_dir}/bk-execution-handoff.md"
grep -q "Confidence=" "${harness_dir}/bk-execution-handoff.md"
grep -q "LongRunStop:" "${harness_dir}/bk-execution-handoff.md"

echo "[test] detect quality gate should fail when draft"
if python3 "${runtime_scripts_dir}/bagakit_long_run_execution.py" validate-table "${project}" --table "${harness_dir}/bk-execution-table.json" >/dev/null 2>&1; then
  echo "[test] expected validate-table to fail when detection.status=draft" >&2
  exit 1
fi

echo "[test] mark detection review ready"
python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
p = Path(r"${harness_dir}/bk-execution-table.json")
data = json.loads(p.read_text(encoding="utf-8"))
det = data.setdefault("detection", {})
det["status"] = "ready"
det["last_reviewed_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
det["reviewed_by"] = "test"
det["upstream_systems"] = ["bagakit-ft"]
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

echo "[test] validate harness"
bash "${runtime_scripts_dir}/validate-long-run.sh" "$project"

echo "[test] execution adapters: seed bagakit-ft + openspec"
mkdir -p "${ft_harness_dir}/index" "${ft_harness_dir}/feats/f-20260215-sync-sample" "${project}/openspec/changes/add-health-check"
cat > "${ft_harness_dir}/index/feats.json" <<'EOF'
{
  "version": 1,
  "feats": [
    {
      "feat_id": "f-20260215-sync-sample",
      "status": "in_progress",
      "priority": 1
    }
  ]
}
EOF
cat > "${ft_harness_dir}/feats/f-20260215-sync-sample/state.json" <<'EOF'
{
  "feat_id": "f-20260215-sync-sample",
  "title": "Sync Sample Feat",
  "status": "in_progress",
  "branch": "feat/f-20260215-sync-sample",
  "worktree_path": ".worktrees/wt-f-20260215-sync-sample"
}
EOF
cat > "${ft_harness_dir}/feats/f-20260215-sync-sample/tasks.json" <<'EOF'
{
  "tasks": [
    {
      "id": "T-001",
      "title": "Implement sync",
      "status": "in_progress"
    }
  ]
}
EOF
cat > "${project}/openspec/changes/add-health-check/proposal.md" <<'EOF'
# Add health check endpoint
EOF
cat > "${project}/openspec/changes/add-health-check/tasks.md" <<'EOF'
- [ ] Define endpoint contract
- [ ] Implement endpoint
EOF

echo "[test] execution plan + sync"
python3 "${runtime_scripts_dir}/bagakit_long_run_execution.py" detect "${project}" --table "${harness_dir}/bk-execution-table.json" >/dev/null
python3 "${runtime_scripts_dir}/bagakit_long_run_execution.py" plan "${project}" --table "${harness_dir}/bk-execution-table.json" >/dev/null
python3 "${runtime_scripts_dir}/bagakit_long_run_execution.py" next-action "${project}" --table "${harness_dir}/bk-execution-table.json" --feature-file "${harness_dir}/feature-list.json" --json >/dev/null
python3 "${runtime_scripts_dir}/bagakit_long_run_execution.py" guide "${project}" --table "${harness_dir}/bk-execution-table.json" >/dev/null
python3 "${runtime_scripts_dir}/bagakit_long_run_execution.py" sync-feature-list "${project}" --table "${harness_dir}/bk-execution-table.json" --feature-file "${harness_dir}/feature-list.json" >/dev/null

echo "[test] check+resume should emit structured next-action contract"
export BAGAKIT_LONG_RUN_SKILL_DIR="${skill_root}"
bash "${harness_dir}/check_and_resume.sh" >/dev/null
[[ -f "${harness_dir}/next-action.json" ]]
python3 - <<PY
import json
from pathlib import Path
p = Path(r"${harness_dir}/next-action.json")
data = json.loads(p.read_text(encoding="utf-8"))
for key in ("resume_command", "selection_strategy", "footer_line"):
    if key not in data:
        raise SystemExit(f"missing next-action key: {key}")
if "Confidence=" not in str(data.get("footer_line", "")):
    raise SystemExit("next-action footer_line missing Confidence signal")
PY

echo "[test] doctor"
bash "${runtime_scripts_dir}/bagakit_long_run_doctor.sh" "$project"

echo "[test] idempotent apply"
bash "${runtime_scripts_dir}/apply-long-run.sh" "$project"

echo "[test] python tool summary"
python3 "${runtime_scripts_dir}/bagakit_long_run_features.py" summary "${harness_dir}/feature-list.json" >/dev/null

echo "[test] pass (${skill_root})"
