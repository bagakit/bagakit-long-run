#!/usr/bin/env bash
set -euo pipefail

harness_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bagakit_dir="$(cd "${harness_dir}/.." && pwd)"
if [[ "$(basename "$bagakit_dir")" == ".bagakit" ]]; then
  project_root="$(cd "${bagakit_dir}/.." && pwd)"
else
  project_root="$bagakit_dir"
fi
resolve_skill_dir() {
  if [[ -n "${BAGAKIT_LONG_RUN_SKILL_DIR:-}" ]]; then
    printf '%s\n' "${BAGAKIT_LONG_RUN_SKILL_DIR}"
    return 0
  fi
  if [[ -n "${BAGAKIT_HOME:-}" && -d "${BAGAKIT_HOME}/skills/bagakit-long-run" ]]; then
    printf '%s\n' "${BAGAKIT_HOME}/skills/bagakit-long-run"
    return 0
  fi
  if [[ -d "$HOME/.claude/skills/bagakit-long-run" ]]; then
    printf '%s\n' "$HOME/.claude/skills/bagakit-long-run"
    return 0
  fi
  if [[ -d "$HOME/.bagakit/skills/bagakit-long-run" ]]; then
    printf '%s\n' "$HOME/.bagakit/skills/bagakit-long-run"
    return 0
  fi
  if [[ -n "${BAGAKIT_HOME:-}" ]]; then
    printf '%s\n' "${BAGAKIT_HOME}/skills/bagakit-long-run"
    return 0
  fi
  printf '%s\n' "$HOME/.claude/skills/bagakit-long-run"
}

skill_dir="$(resolve_skill_dir)"
validate_script="${skill_dir}/scripts/validate-long-run.sh"
feature_tool="${skill_dir}/scripts/bagakit_long_run_features.py"
execution_tool="${skill_dir}/scripts/bagakit_long_run_execution.py"
feature_file="${harness_dir}/feature-list.json"
handoff_file="${harness_dir}/bk-execution-handoff.md"
execution_table="${harness_dir}/bk-execution-table.json"
detect_prompt="${harness_dir}/detect_prompt.md"

echo "== Bagakit Long Run: session init =="

if [[ ! -f "$validate_script" ]]; then
  echo "error: missing validate script at ${validate_script}" >&2
  echo "set BAGAKIT_LONG_RUN_SKILL_DIR to your installed skill path (example: \$HOME/.claude/skills/bagakit-long-run)." >&2
  exit 1
fi

bash "$validate_script" "$project_root"

if command -v python3 >/dev/null 2>&1 && [[ -f "$execution_tool" && -f "$execution_table" ]]; then
  echo
  echo "== Execution table quality =="
  if ! python3 "$execution_tool" validate-table "$project_root" --table "$execution_table"; then
    echo "error: execution table is not ready for long-run." >&2
    if [[ -f "$detect_prompt" ]]; then
      echo "next: run agent detect pass with ${detect_prompt}" >&2
    fi
    exit 1
  fi

  echo
  echo "== Execution adapters =="
  python3 "$execution_tool" detect "$project_root" --table "$execution_table"

  echo
  echo "== Execution rows (top) =="
  python3 "$execution_tool" plan "$project_root" --table "$execution_table" --limit 8

  echo
  echo "== Guidance for next item =="
  if ! python3 "$execution_tool" guide "$project_root" --table "$execution_table"; then
    echo "warn: no target system rows available for guidance." >&2
    echo "next: add upstream tasks/spec items, run detect prompt, then re-run init." >&2
  fi

  echo
  echo "== Sync feature list from execution rows =="
  python3 "$execution_tool" sync-feature-list "$project_root" --table "$execution_table" --feature-file "$feature_file"
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
rel_harness="${harness_dir#${project_root}/}"
echo "Use:"
echo "0) ${rel_harness}/detect_prompt.md (when adding/changing upstream systems)"
echo "1) ${rel_harness}/initial_prompt.md for initializer pass"
echo "2) ${rel_harness}/coding_prompt.md for coding pass"
echo "3) update ${handoff_file} every pass"
