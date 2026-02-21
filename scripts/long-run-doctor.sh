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
heartbeat_tool="${script_dir}/long-run-heartbeat.py"
heartbeat_config_file="${harness_dir}/heartbeat.config.json"
heartbeat_state_file="${harness_dir}/heartbeat.state.json"
heartbeat_schedules_file="${harness_dir}/heartbeat-schedules.json"

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
echo "== doctor: heartbeat health =="
if [[ ! -f "$heartbeat_config_file" ]]; then
  warn "heartbeat config not found (${heartbeat_config_file}); run apply-long-run.sh to scaffold heartbeat v1"
else
  if [[ ! -f "$heartbeat_tool" ]]; then
    warn "heartbeat tool missing: ${heartbeat_tool}"
  else
    if ! python3 "$heartbeat_tool" validate-config "$project_root" >/dev/null; then
      warn "heartbeat config validation failed"
    else
      echo "heartbeat config: ok"
    fi
    if [[ -f "$heartbeat_schedules_file" ]]; then
      if ! python3 "$heartbeat_tool" validate-schedules "$project_root" >/dev/null; then
        warn "heartbeat schedules validation failed"
      fi
    fi
  fi

  heartbeat_warnings="$(python3 - "$heartbeat_config_file" "$heartbeat_state_file" "$heartbeat_schedules_file" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

cfg_path, state_path, schedules_path = [Path(p) for p in sys.argv[1:4]]

def parse_ts(text: str):
    text = (text or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None

warnings = []
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
schedules = json.loads(schedules_path.read_text(encoding="utf-8")) if schedules_path.exists() else {"schedules": []}

enabled = bool(cfg.get("enabled", True))
interval = int(cfg.get("interval_minutes", 30))
rows = state.get("recent_executions", [])
if not isinstance(rows, list):
    rows = []

streak = 0
for row in reversed(rows[-12:]):
    if not isinstance(row, dict):
        continue
    if str(row.get("outcome", "")).startswith("failed"):
        streak += 1
    else:
        break
if streak >= 3:
    warnings.append(f"heartbeat has {streak} consecutive failed ticks")

last_success = parse_ts(str(state.get("last_success_at", "")))
if enabled and last_success is not None:
    minutes = (datetime.now(timezone.utc) - last_success.astimezone(timezone.utc)).total_seconds() / 60
    if minutes > interval * 4:
        warnings.append(f"last heartbeat success is stale ({int(minutes)} minutes ago)")

schedule_items = schedules.get("schedules", [])
if enabled:
    if not isinstance(schedule_items, list) or not schedule_items:
        warnings.append("heartbeat enabled but no schedules are configured (use external scheduler + schedule-render)")
    else:
        active = [s for s in schedule_items if isinstance(s, dict) and bool(s.get("enabled", True))]
        if not active:
            warnings.append("heartbeat schedules exist but all are disabled")

for warning in warnings:
    print(warning)
PY
)" || true
  if [[ -n "${heartbeat_warnings}" ]]; then
    while IFS= read -r line; do
      [[ -n "$line" ]] || continue
      warn "$line"
    done <<<"$heartbeat_warnings"
  fi
fi

echo
echo "doctor complete: ${warnings} warning(s)"
rel_harness="${harness_dir#${project_root}/}"
echo "recommended loop:"
echo "  1) bash ${rel_harness}/check_and_resume.sh"
echo "  2) initializer pass"
echo "  3) coding pass"
echo "  4) validate + doctor"
echo "  5) heartbeat tick: python3 \"\$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-heartbeat.py\" tick . --json"
