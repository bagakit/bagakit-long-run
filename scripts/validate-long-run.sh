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
agents_file="${project_root}/AGENTS.md"
feature_file="${harness_dir}/feature-list.json"
handoff_file="${harness_dir}/bk-execution-handoff.md"
execution_table_file="${harness_dir}/bk-execution-table.json"
detect_prompt="${harness_dir}/detect_prompt.md"
initializer_prompt="${harness_dir}/initializer_prompt.md"
coding_prompt="${harness_dir}/coding_prompt.md"
resume_script="${harness_dir}/check_and_resume.sh"
ralphloop_script="${harness_dir}/ralphloop.sh"
project_profile_file="${harness_dir}/project-profile.json"
heartbeat_config_file="${harness_dir}/heartbeat.config.json"
heartbeat_schedules_file="${harness_dir}/heartbeat-schedules.json"
heartbeat_state_file="${harness_dir}/heartbeat.state.json"
heartbeat_queue_file="${harness_dir}/inbox/queue.json"
heartbeat_inbox_history_dir="${harness_dir}/inbox/history"
heartbeat_inbox_flash_dir="${harness_dir}/inbox/flash-ideas"
heartbeat_inbox_readme="${harness_dir}/inbox/README.md"
legacy_init_script="${harness_dir}/init.sh"
legacy_initial_prompt="${harness_dir}/initial_prompt.md"
feature_tool="${script_dir}/long-run-features.py"
execution_tool="${script_dir}/long-run-execution.py"
loop_tool="${script_dir}/long-run-loop.py"
heartbeat_tool="${script_dir}/long-run-heartbeat.py"

errors=0
warnings=0

fail() {
  echo "error: $1" >&2
  errors=$((errors + 1))
}

warn() {
  echo "warn: $1" >&2
  warnings=$((warnings + 1))
}

if ! command -v python3 >/dev/null 2>&1; then
  fail "python3 is required for long-run validation"
fi

if [[ ! -d "$harness_dir" ]]; then
  fail "missing harness dir: ${harness_dir}"
else
  for f in "$feature_file" "$initializer_prompt" "$coding_prompt" "$resume_script" "$ralphloop_script" "$project_profile_file" "$execution_table_file" "$detect_prompt"; do
    if [[ ! -f "$f" ]]; then
      fail "missing required harness file: ${f}"
    fi
  done
fi

if [[ ! -f "$handoff_file" ]]; then
  fail "missing required handoff file: ${handoff_file}"
fi

if [[ -f "$resume_script" && ! -x "$resume_script" ]]; then
  warn "resume script is not executable: ${resume_script}"
fi
if [[ -f "$ralphloop_script" && ! -x "$ralphloop_script" ]]; then
  warn "ralphloop script is not executable: ${ralphloop_script}"
fi
if [[ -f "$project_profile_file" ]]; then
  if ! python3 - "$project_profile_file" >/dev/null <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
if not isinstance(payload, dict):
    raise SystemExit(1)
launcher = payload.get("launcher", {})
if not isinstance(launcher, dict):
    raise SystemExit(1)
if not str(launcher.get("route", "")).strip():
    raise SystemExit(1)
if not str(launcher.get("command", "")).strip():
    raise SystemExit(1)
PY
  then
    fail "project profile validation failed: ${project_profile_file}"
  fi
fi
if [[ ! -f "$loop_tool" ]]; then
  fail "missing loop tool: ${loop_tool}"
fi

for legacy in "$legacy_init_script" "$legacy_initial_prompt"; do
  if [[ -e "$legacy" ]]; then
    fail "legacy harness artifact must be removed: ${legacy} (run apply-long-run.sh again)"
  fi
done

heartbeat_present=0
for heartbeat_path in "$heartbeat_config_file" "$heartbeat_schedules_file" "$heartbeat_state_file" "$heartbeat_queue_file"; do
  if [[ -e "$heartbeat_path" ]]; then
    heartbeat_present=$((heartbeat_present + 1))
  fi
done

if [[ "$heartbeat_present" -eq 0 ]]; then
  warn "heartbeat artifacts not found (migration hint: run apply-long-run.sh to scaffold heartbeat v1 files)"
elif [[ "$heartbeat_present" -lt 4 ]]; then
  fail "heartbeat artifacts are partially present; re-run apply-long-run.sh to repair"
else
  if [[ ! -f "$heartbeat_tool" ]]; then
    fail "missing heartbeat tool: ${heartbeat_tool}"
  else
    if ! python3 "$heartbeat_tool" validate-config "$project_root" >/dev/null; then
      fail "heartbeat config validation failed: ${heartbeat_config_file}"
    fi
    if ! python3 "$heartbeat_tool" validate-schedules "$project_root" >/dev/null; then
      fail "heartbeat schedules validation failed: ${heartbeat_schedules_file}"
    fi
  fi

  if [[ ! -d "$heartbeat_inbox_history_dir" ]]; then
    fail "missing heartbeat inbox history dir: ${heartbeat_inbox_history_dir}"
  fi
  if [[ ! -d "$heartbeat_inbox_flash_dir" ]]; then
    fail "missing heartbeat inbox flash-ideas dir: ${heartbeat_inbox_flash_dir}"
  fi
  if [[ ! -f "$heartbeat_inbox_readme" ]]; then
    warn "missing heartbeat inbox README: ${heartbeat_inbox_readme}"
  fi

  heartbeat_contract_errors="$(python3 - "$heartbeat_config_file" "$heartbeat_state_file" "$heartbeat_queue_file" <<'PY'
import json
import sys
from pathlib import Path

cfg_path, state_path, queue_path = [Path(p) for p in sys.argv[1:4]]
errors = []

try:
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
except Exception as exc:
    cfg = {}
    errors.append(f"heartbeat.config.json parse failed: {exc}")

guard = cfg.get("guardrails", {}) if isinstance(cfg, dict) else {}
allowlist = guard.get("allowlist_prefixes")
if not isinstance(allowlist, list) or not [s for s in allowlist if isinstance(s, str) and s.strip()]:
    errors.append("heartbeat guardrails.allowlist_prefixes must include at least one prefix")

timeout = guard.get("command_timeout_seconds")
if not isinstance(timeout, int) or timeout < 1 or timeout > 7200:
    errors.append("heartbeat guardrails.command_timeout_seconds must be int within [1, 7200]")

budget = guard.get("max_commands_per_tick")
if not isinstance(budget, int) or budget < 1 or budget > 32:
    errors.append("heartbeat guardrails.max_commands_per_tick must be int within [1, 32]")

try:
    state = json.loads(state_path.read_text(encoding="utf-8"))
except Exception as exc:
    state = {}
    errors.append(f"heartbeat.state.json parse failed: {exc}")
cooldown = state.get("cooldown_minutes")
if not isinstance(cooldown, int) or cooldown < 1 or cooldown > 10080:
    errors.append("heartbeat.state.json cooldown_minutes must be int within [1, 10080]")
recent = state.get("recent_executions")
if not isinstance(recent, list):
    errors.append("heartbeat.state.json recent_executions must be list")

try:
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
except Exception as exc:
    queue = {}
    errors.append(f"inbox queue parse failed: {exc}")
items = queue.get("items")
if not isinstance(items, list):
    errors.append("inbox queue items must be list")

for err in errors:
    print(err)
PY
)" || true
  if [[ -n "${heartbeat_contract_errors}" ]]; then
    while IFS= read -r line; do
      [[ -n "$line" ]] || continue
      fail "$line"
    done <<<"$heartbeat_contract_errors"
  fi
fi

if [[ -f "$feature_file" ]]; then
  if [[ ! -f "$feature_tool" ]]; then
    fail "missing feature tool: ${feature_tool}"
  else
    if ! python3 "$feature_tool" validate "$feature_file" >/dev/null; then
      fail "feature list validation failed: ${feature_file}"
    fi
  fi
fi

if [[ -f "$handoff_file" ]]; then
  grep -q "^## Current Execution Item" "$handoff_file" || warn "handoff missing '## Current Execution Item' section"
  grep -q "^- Execution Item ID:" "$handoff_file" || warn "handoff missing '- Execution Item ID:' line"
  grep -q "^## Next Run" "$handoff_file" || warn "handoff missing '## Next Run' section"
  grep -q "\[\[BAGAKIT\]\]" "$handoff_file" || warn "handoff missing [[BAGAKIT]] response snapshot"
  grep -q "^- LongRun:" "$handoff_file" || warn "handoff missing '- LongRun:' response snapshot line"
  grep -q "Confidence=" "$handoff_file" || warn "handoff LongRun snapshot should include Confidence="
fi

for f in "$detect_prompt" "$initializer_prompt" "$coding_prompt"; do
  if [[ -f "$f" ]]; then
    grep -q "\[\[BAGAKIT\]\]" "$f" || fail "prompt missing [[BAGAKIT]] footer contract: ${f}"
    grep -q "LongRun:" "$f" || fail "prompt missing '- LongRun:' footer contract: ${f}"
    grep -q "Confidence=" "$f" || fail "prompt missing 'Confidence=' in '- LongRun:' contract: ${f}"
    grep -q "LongRunStop:" "$f" || fail "prompt missing stop-reason contract '- LongRunStop:': ${f}"
  fi
done

if [[ ! -f "$agents_file" ]]; then
  fail "missing AGENTS.md: ${agents_file}"
else
  grep -q "<!-- BAGAKIT:LONGRUN:START -->" "$agents_file" || fail "missing BAGAKIT long-run managed block start in ${agents_file}"
  grep -q "<!-- BAGAKIT:LONGRUN:END -->" "$agents_file" || fail "missing BAGAKIT long-run managed block end in ${agents_file}"
  grep -q "ralphloop.sh pulse --endless" "$agents_file" || fail "AGENTS long-run block missing preferred ralphloop endless entry command"
  grep -q "check_and_resume.sh" "$agents_file" || fail "AGENTS long-run block missing explicit resume loop command"
  grep -q "\[\[BAGAKIT\]\]" "$agents_file" || fail "AGENTS long-run block missing [[BAGAKIT]] response contract"
  grep -q "LongRun:" "$agents_file" || fail "AGENTS long-run block missing '- LongRun:' response contract"
  grep -q "Confidence=" "$agents_file" || fail "AGENTS long-run block missing Confidence contract in '- LongRun:' line"
  grep -q "LongRunStop:" "$agents_file" || fail "AGENTS long-run block missing '- LongRunStop:' stop-reason contract"
fi

if [[ -f "$execution_table_file" ]]; then
  if [[ ! -f "$execution_tool" ]]; then
    fail "missing execution tool: ${execution_tool}"
  else
    if ! python3 "$execution_tool" validate-table "$project_root" --table "$execution_table_file" >/dev/null; then
      fail "execution table quality validation failed: ${execution_table_file}"
    fi
    if ! python3 "$execution_tool" plan "$project_root" --table "$execution_table_file" >/dev/null; then
      fail "execution table plan failed: ${execution_table_file}"
    fi
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
  fi
fi

if [[ $errors -gt 0 ]]; then
  echo "failed: ${errors} error(s), ${warnings} warning(s)" >&2
  exit 1
fi

echo "ok: harness validation passed (${warnings} warning(s))"
