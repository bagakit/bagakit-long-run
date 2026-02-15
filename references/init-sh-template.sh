#!/usr/bin/env bash
set -euo pipefail

harness_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "${harness_dir}/.." && pwd)"
skill_home="${BAGAKIT_HOME:-$HOME/.bagakit}"
skill_dir="${BAGAKIT_LONG_RUN_SKILL_DIR:-${skill_home}/skills/bagakit-long-run}"
validate_script="${skill_dir}/scripts/validate-long-run.sh"
feature_tool="${skill_dir}/scripts/bagakit_long_run_features.py"
execution_tool="${skill_dir}/scripts/bagakit_long_run_execution.py"
feature_file="${harness_dir}/feature-list.json"
handoff_file="${harness_dir}/bk-execution-handoff.md"
execution_table="${harness_dir}/bk-execution-table.json"

echo "== Bagakit Long Run: session init =="

if [[ ! -f "$validate_script" ]]; then
  echo "error: missing validate script at ${validate_script}" >&2
  echo "set BAGAKIT_LONG_RUN_SKILL_DIR to your installed skill path." >&2
  exit 1
fi

bash "$validate_script" "$project_root"

if command -v python3 >/dev/null 2>&1 && [[ -f "$execution_tool" && -f "$execution_table" ]]; then
  echo
  echo "== Execution adapters =="
  python3 "$execution_tool" detect "$project_root" --table "$execution_table" || true

  echo
  echo "== Execution rows (top) =="
  python3 "$execution_tool" plan "$project_root" --table "$execution_table" --limit 8 || true

  echo
  echo "== Guidance for next item =="
  python3 "$execution_tool" guide "$project_root" --table "$execution_table" || true

  echo
  echo "== Sync feature list from execution rows =="
  python3 "$execution_tool" sync-feature-list "$project_root" --table "$execution_table" --feature-file "$feature_file" || true
fi

if command -v python3 >/dev/null 2>&1 && [[ -f "$feature_tool" ]]; then
  echo
  echo "== Feature summary =="
  python3 "$feature_tool" summary "$feature_file"

  echo
  echo "== Suggested current item =="
  if next_feature="$(python3 "$feature_tool" pick "$feature_file" 2>/dev/null)"; then
    echo "$next_feature"
  else
    echo "(none: no actionable item found)"
  fi
else
  echo "warn: python3 or feature tool missing; skipping feature summary." >&2
fi

echo
echo "Use:"
echo "1) .bagakit-long-run/initial_prompt.md for initializer pass"
echo "2) .bagakit-long-run/coding_prompt.md for coding pass"
echo "3) update ${handoff_file} every pass"
