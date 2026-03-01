#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$(basename "$script_dir")" == ".gen" ]]; then
  harness_dir="$(cd "${script_dir}/.." && pwd)"
else
  harness_dir="$script_dir"
fi
project_root="$(cd "${harness_dir}/../.." && pwd)"
gen_dir="${harness_dir}/.gen"
skill_dir="${BAGAKIT_LONG_RUN_SKILL_DIR:-}"
if [[ -z "$skill_dir" ]]; then
  echo "error: BAGAKIT_LONG_RUN_SKILL_DIR is required and must point to the bagakit-long-run skill root." >&2
  exit 1
fi
validate_script="${skill_dir}/scripts/validate-long-run.sh"
feature_tool="${skill_dir}/scripts/long-run-features.py"
execution_tool="${skill_dir}/scripts/long-run-execution.py"
feature_file="${harness_dir}/feature-list.json"
handoff_file="${harness_dir}/bk-execution-handoff.md"
execution_table="${harness_dir}/bk-execution-table.json"
detect_prompt="${gen_dir}/detect_prompt.md"
initializer_prompt="${gen_dir}/initializer_prompt.md"
coding_prompt="${gen_dir}/coding_prompt.md"
next_action_json="${harness_dir}/next-action.json"
archive_disabled="${BAGAKIT_LONG_RUN_ARCHIVE_DISABLED:-0}"
archive_file_override="${BAGAKIT_LONG_RUN_ARCHIVE_FILE:-}"
archive_done_keep="${BAGAKIT_LONG_RUN_ARCHIVE_DONE_KEEP:-120}"
archive_max_per_run="${BAGAKIT_LONG_RUN_ARCHIVE_MAX_PER_RUN:-60}"

echo "== Bagakit Long Run: check + resume =="

if [[ ! -f "$validate_script" ]]; then
  echo "error: missing validate script at ${validate_script}" >&2
  echo "set BAGAKIT_LONG_RUN_SKILL_DIR to a valid bagakit-long-run skill root." >&2
  exit 1
fi
if [[ ! -f "$execution_tool" ]]; then
  echo "error: missing execution tool at ${execution_tool}" >&2
  exit 1
fi
if [[ ! -f "$feature_tool" ]]; then
  echo "error: missing feature tool at ${feature_tool}" >&2
  exit 1
fi

echo
echo "== Startup self-check (migration) =="
missing_managed_runtime=0
for required in \
  "${gen_dir}/detect_prompt.md" \
  "${gen_dir}/initializer_prompt.md" \
  "${gen_dir}/coding_prompt.md" \
  "${gen_dir}/check_and_resume.sh" \
  "${gen_dir}/ralphloop.sh" \
  "${gen_dir}/ralphloop-runner.sh"; do
  if [[ ! -f "$required" ]]; then
    echo "warn: missing managed runtime file: ${required}" >&2
    missing_managed_runtime=1
  fi
done
if [[ "$missing_managed_runtime" == "1" ]]; then
  echo "error: long-run runtime is not in final managed layout (.gen)." >&2
  echo "migration: bash \"${skill_dir}/scripts/apply-long-run.sh\" \"${project_root}\" --force" >&2
  exit 1
fi
if [[ -e "${harness_dir}/init.sh" || -e "${harness_dir}/initial_prompt.md" ]]; then
  echo "warn: legacy long-run files detected (init.sh/initial_prompt.md); re-run apply with --force." >&2
fi
echo "self-check: managed runtime layout ok"

bash "$validate_script" "$project_root"

echo
echo "== Execution table archive maintenance =="
if [[ "$archive_disabled" == "1" ]]; then
  echo "archive: disabled by BAGAKIT_LONG_RUN_ARCHIVE_DISABLED=1"
else
  archive_args=(
    "$execution_tool"
    archive-table
    "$project_root"
    --table
    "$execution_table"
    --manual-done-keep
    "$archive_done_keep"
    --manual-done-max-archive
    "$archive_max_per_run"
  )
  if [[ -n "$archive_file_override" ]]; then
    archive_args+=(--archive-file "$archive_file_override")
  fi
  if ! python3 "${archive_args[@]}"; then
    echo "warn: execution table archive step failed; continue without compaction." >&2
  fi
fi

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
  echo "warn: no actionable row available for guidance." >&2
  echo "next: add upstream tasks/spec items, run detect prompt, then re-run: bash .bagakit/long-run/check_and_resume.sh" >&2
fi

echo
echo "== Sync feature list from execution rows =="
python3 "$execution_tool" sync-feature-list "$project_root" --table "$execution_table" --feature-file "$feature_file"

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

echo
echo "== Next action contract (structured) =="
python3 "$execution_tool" next-action "$project_root" --table "$execution_table" --feature-file "$feature_file" --json > "$next_action_json"
cat "$next_action_json"
echo "next_action_file: ${next_action_json}"

echo
rel_harness="${harness_dir#${project_root}/}"
echo "Use:"
echo "setup) export BAGAKIT_AGENT_CMD='codex exec {prompt_text}'  # non-interactive required"
echo "setup) export RALPHLOOP_MAX_ROUNDS=50 RALPHLOOP_MAX_RUNTIME_SECONDS=7200 RALPHLOOP_MAX_INTERVAL_SECONDS=30"
echo "setup) export RALPHLOOP_LOG_FILE='.bagakit/long-run/logs/ralphloop-runner.log'"
echo "setup) export BAGAKIT_LONG_RUN_ARCHIVE_DONE_KEEP=120 BAGAKIT_LONG_RUN_ARCHIVE_MAX_PER_RUN=60"
echo "setup) optional rollback only: export BAGAKIT_LONG_RUN_LEGACY_RC_ONLY=1"
echo "0) ${rel_harness}/ralphloop-runner.sh (continuous loop; requires BAGAKIT_AGENT_CMD/BAGAKIT_AGENT_CLI)"
echo "0b) ${rel_harness}/ralphloop.sh pulse --endless (single pulse fallback)"
echo "0c) preflight check: python3 \"${skill_dir}/scripts/long-run-loop.py\" preflight \"${project_root}\" --json"
echo "1) ${rel_harness}/.gen/detect_prompt.md (when adding/changing upstream systems)"
echo "2) ${rel_harness}/.gen/initializer_prompt.md for initializer pass"
echo "3) ${rel_harness}/.gen/coding_prompt.md for coding pass"
echo "4) update ${handoff_file} every pass"
echo "5) optional async note inbox: write segments to ${rel_harness}/ralph-msg.md separated by ---"
