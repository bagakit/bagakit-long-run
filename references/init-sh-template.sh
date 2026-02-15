#!/usr/bin/env bash
set -euo pipefail

harness_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "${harness_dir}/.." && pwd)"
skill_dir="${BAGAKIT_LONG_RUN_SKILL_DIR:-${CODEX_HOME:-$HOME/.codex}/skills/bagakit-long-run}"
validate_script="${skill_dir}/scripts/validate-long-run.sh"
feature_tool="${skill_dir}/scripts/bagakit_long_run_features.py"
feature_file="${harness_dir}/feature-list.json"
progress_file="${harness_dir}/claude-progress.md"

echo "== Bagakit Long Run: session init =="

if [[ ! -f "$validate_script" ]]; then
  echo "error: missing validate script at ${validate_script}" >&2
  echo "set BAGAKIT_LONG_RUN_SKILL_DIR to your installed skill path." >&2
  exit 1
fi

bash "$validate_script" "$project_root"

if command -v python3 >/dev/null 2>&1 && [[ -f "$feature_tool" ]]; then
  echo
  echo "== Feature summary =="
  python3 "$feature_tool" summary "$feature_file"

  echo
  echo "== Suggested current feature =="
  if next_feature="$(python3 "$feature_tool" pick "$feature_file" 2>/dev/null)"; then
    echo "$next_feature"
  else
    echo "(none: no todo/in_progress feature found)"
  fi
else
  echo "warn: python3 or feature tool missing; skipping feature summary." >&2
fi

echo
echo "Use:"
echo "1) .bagakit-long-run/initial_prompt.md for initializer pass"
echo "2) .bagakit-long-run/coding_prompt.md for coding pass"
echo "3) update ${progress_file} every pass"
