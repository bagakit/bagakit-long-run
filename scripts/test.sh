#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill_root="$(cd "${script_dir}/.." && pwd)"

tmp="$(mktemp -d -t bagakit-long-run-test.XXXXXX)"
trap 'rm -rf "$tmp"' EXIT

project="${tmp}/project"
mkdir -p "$project"

echo "[test] apply harness"
bash "${script_dir}/apply-long-run.sh" "$project"

[[ -f "${project}/.bagakit-long-run/bk-execution-handoff.md" ]]
[[ -f "${project}/.bagakit-long-run/bk-execution-table.json" ]]

echo "[test] validate harness"
bash "${script_dir}/validate-long-run.sh" "$project"

echo "[test] execution adapters: seed bagakit-ft + openspec"
mkdir -p "${project}/.bagakit-ft/index" "${project}/.bagakit-ft/feats/f-20260215-sync-sample" "${project}/openspec/changes/add-health-check"
cat > "${project}/.bagakit-ft/index/feats.json" <<'EOF'
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
cat > "${project}/.bagakit-ft/feats/f-20260215-sync-sample/state.json" <<'EOF'
{
  "feat_id": "f-20260215-sync-sample",
  "title": "Sync Sample Feat",
  "status": "in_progress",
  "branch": "feat/f-20260215-sync-sample",
  "worktree_path": ".worktrees/wt-f-20260215-sync-sample"
}
EOF
cat > "${project}/.bagakit-ft/feats/f-20260215-sync-sample/tasks.json" <<'EOF'
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
python3 "${script_dir}/bagakit_long_run_execution.py" detect "${project}" --table "${project}/.bagakit-long-run/bk-execution-table.json" >/dev/null
python3 "${script_dir}/bagakit_long_run_execution.py" plan "${project}" --table "${project}/.bagakit-long-run/bk-execution-table.json" >/dev/null
python3 "${script_dir}/bagakit_long_run_execution.py" guide "${project}" --table "${project}/.bagakit-long-run/bk-execution-table.json" >/dev/null
python3 "${script_dir}/bagakit_long_run_execution.py" sync-feature-list "${project}" --table "${project}/.bagakit-long-run/bk-execution-table.json" --feature-file "${project}/.bagakit-long-run/feature-list.json" >/dev/null

echo "[test] doctor"
bash "${script_dir}/bagakit_long_run_doctor.sh" "$project"

echo "[test] idempotent apply"
bash "${script_dir}/apply-long-run.sh" "$project"

echo "[test] python tool summary"
python3 "${script_dir}/bagakit_long_run_features.py" summary "${project}/.bagakit-long-run/feature-list.json" >/dev/null

echo "[test] pass (${skill_root})"
