#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $(basename "$0") <project_root>" >&2
  exit 1
}

if [[ $# -ne 1 ]]; then
  usage
fi

project_root="$1"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
harness_dir="${project_root}/.bagakit/long-run"
feature_file="${harness_dir}/feature-list.json"
handoff_file="${harness_dir}/bk-execution-handoff.md"
execution_table_file="${harness_dir}/bk-execution-table.json"
feature_tool="${script_dir}/long-run-features.py"
execution_tool="${script_dir}/long-run-execution.py"

warnings=0

warn() {
  echo "warn: $1" >&2
  warnings=$((warnings + 1))
}

echo "== doctor: validating harness =="
if ! bash "${script_dir}/validate-long-run.sh" "$project_root"; then
  echo "doctor: validation failed; fix required errors first." >&2
  echo "doctor: re-apply long-run if AGENTS managed block is missing: bash \"${script_dir}/apply-long-run.sh\" \"${project_root}\"" >&2
  echo "doctor: if detect quality is not ready, run .bagakit/long-run/detect_prompt.md first." >&2
  exit 1
fi

echo
echo "== doctor: feature summary =="
python3 "$feature_tool" summary "$feature_file"

active_id="$(python3 "$feature_tool" pick "$feature_file" --id-only 2>/dev/null || true)"
handoff_item_id=""
if [[ -f "$handoff_file" ]]; then
  handoff_item_id="$(grep -E '^- Execution Item ID:' "$handoff_file" | head -n 1 | sed 's/^- Execution Item ID:[[:space:]]*//' || true)"
fi

if [[ -n "$active_id" && -n "$handoff_item_id" && "$handoff_item_id" != "<set-by-initializer>" && "$active_id" != "$handoff_item_id" ]]; then
  warn "handoff item (${handoff_item_id}) differs from active feature (${active_id})"
fi

echo
echo "== doctor: execution adapters =="
python3 "$execution_tool" detect "$project_root" --table "$execution_table_file" || true
detect_warnings="$(python3 - "$execution_tool" "$project_root" "$execution_table_file" <<'PY'
import json
import subprocess
import sys

tool, root, table = sys.argv[1], sys.argv[2], sys.argv[3]
raw = subprocess.check_output(
    ["python3", tool, "detect", root, "--table", table, "--json"],
    text=True,
)
payload = json.loads(raw)
for adapter in payload.get("adapters", []):
    if not isinstance(adapter, dict):
        continue
    name = str(adapter.get("name", "adapter"))
    for warning in adapter.get("warnings", []):
        print(f"{name}: {warning}")
PY
)" || true
if [[ -n "${detect_warnings}" ]]; then
  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    warn "execution detect: ${line}"
  done <<<"$detect_warnings"
fi
echo
echo "== doctor: execution rows (top) =="
python3 "$execution_tool" plan "$project_root" --table "$execution_table_file" --limit 8 || true

blocked_count="$(python3 - "$feature_file" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
features = data.get("features", [])
blocked = sum(1 for i in features if i.get("status") == "blocked")
todo = sum(1 for i in features if i.get("status") == "todo")
print(f"{blocked}:{todo}")
PY
)"
blocked="${blocked_count%%:*}"
todo="${blocked_count##*:}"
if [[ "$blocked" -gt 0 && "$todo" -eq 0 ]]; then
  warn "all remaining work is blocked; add explicit unblock tasks"
fi

echo
echo "doctor complete: ${warnings} warning(s)"
rel_harness="${harness_dir#${project_root}/}"
echo "recommended loop:"
echo "  1) bash ${rel_harness}/check_and_resume.sh"
echo "  2) initializer pass"
echo "  3) coding pass"
echo "  4) validate + doctor"
