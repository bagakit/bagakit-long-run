#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$(basename "$script_dir")" == ".gen" ]]; then
  harness_dir="$(cd "${script_dir}/.." && pwd)"
else
  harness_dir="$script_dir"
fi
sleep_seconds="${RALPHLOOP_SLEEP_SECONDS:-1}"
one_shot="${RALPHLOOP_ONE_SHOT:-0}"
max_rounds="${RALPHLOOP_MAX_ROUNDS:-0}"
max_runtime_seconds="${RALPHLOOP_MAX_RUNTIME_SECONDS:-0}"
max_interval_seconds="${RALPHLOOP_MAX_INTERVAL_SECONDS:-300}"
log_file="${RALPHLOOP_LOG_FILE:-${harness_dir}/logs/ralphloop-runner.log}"
json_mode="${RALPHLOOP_JSON_MODE:-0}"
log_enabled=1

is_nonneg_int() {
  [[ "$1" =~ ^[0-9]+$ ]]
}

timestamp_utc() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

runner_log() {
  local line
  line="[$(timestamp_utc)] $*"
  echo "$line" >&2
  if [[ "$log_enabled" == "1" ]]; then
    printf "%s\n" "$line" >> "$log_file" 2>/dev/null || true
  fi
}

if ! is_nonneg_int "$sleep_seconds"; then
  echo "error: RALPHLOOP_SLEEP_SECONDS must be a non-negative integer: ${sleep_seconds}" >&2
  exit 1
fi
if [[ "$one_shot" != "0" && "$one_shot" != "1" ]]; then
  echo "error: RALPHLOOP_ONE_SHOT must be 0 or 1: ${one_shot}" >&2
  exit 1
fi
if ! is_nonneg_int "$max_rounds"; then
  echo "error: RALPHLOOP_MAX_ROUNDS must be a non-negative integer: ${max_rounds}" >&2
  exit 1
fi
if ! is_nonneg_int "$max_runtime_seconds"; then
  echo "error: RALPHLOOP_MAX_RUNTIME_SECONDS must be a non-negative integer: ${max_runtime_seconds}" >&2
  exit 1
fi
if ! is_nonneg_int "$max_interval_seconds"; then
  echo "error: RALPHLOOP_MAX_INTERVAL_SECONDS must be a non-negative integer: ${max_interval_seconds}" >&2
  exit 1
fi
if [[ "$json_mode" != "0" && "$json_mode" != "1" ]]; then
  echo "error: RALPHLOOP_JSON_MODE must be 0 or 1: ${json_mode}" >&2
  exit 1
fi

if [[ "$one_shot" == "1" && "$max_rounds" == "0" ]]; then
  max_rounds="1"
fi

if [[ "$max_interval_seconds" -gt 0 ]] && [[ "$sleep_seconds" -gt "$max_interval_seconds" ]]; then
  echo "warn: clamp RALPHLOOP_SLEEP_SECONDS=${sleep_seconds} to RALPHLOOP_MAX_INTERVAL_SECONDS=${max_interval_seconds}" >&2
  sleep_seconds="$max_interval_seconds"
fi

if [[ -n "$log_file" ]]; then
  mkdir -p "$(dirname "$log_file")" 2>/dev/null || true
  if ! touch "$log_file" 2>/dev/null; then
    log_enabled=0
    echo "warn: cannot write log file (${log_file}); continue without file logging." >&2
  fi
else
  log_enabled=0
fi

if [[ -z "${BAGAKIT_AGENT_CMD:-}" && -z "${BAGAKIT_AGENT_CLI:-}" ]]; then
  runner_log "warn: BAGAKIT_AGENT_CMD/BAGAKIT_AGENT_CLI is not configured; fallback to one pulse."
  if [[ "$json_mode" == "1" ]]; then
    exec bash "${harness_dir}/ralphloop.sh" pulse --endless --json "$@"
  fi
  exec bash "${harness_dir}/ralphloop.sh" pulse --endless "$@"
fi

runner_log "info: outer orchestrator runner expects non-interactive agent command (for example: codex exec ...)."
runner_log "info: config sleep_seconds=${sleep_seconds} max_rounds=${max_rounds} max_runtime_seconds=${max_runtime_seconds} max_interval_seconds=${max_interval_seconds} json_mode=${json_mode} log_file=${log_file}"

start_epoch="$(date +%s)"
round=0

while true; do
  if [[ "$max_rounds" -gt 0 ]] && [[ "$round" -ge "$max_rounds" ]]; then
    runner_log "info: stop runner because max rounds reached (${max_rounds})."
    exit 0
  fi

  now_epoch="$(date +%s)"
  elapsed="$((now_epoch - start_epoch))"
  if [[ "$max_runtime_seconds" -gt 0 ]] && [[ "$elapsed" -ge "$max_runtime_seconds" ]]; then
    runner_log "info: stop runner because max runtime reached (${max_runtime_seconds}s)."
    exit 0
  fi

  round="$((round + 1))"
  runner_log "info: round=${round} start"

  set +e
  if [[ "$log_enabled" == "1" ]]; then
    if [[ "$json_mode" == "1" ]]; then
      bash "${harness_dir}/ralphloop.sh" run --endless --json "$@" 2>&1 | tee -a "$log_file"
    else
      bash "${harness_dir}/ralphloop.sh" run --endless "$@" 2>&1 | tee -a "$log_file"
    fi
    run_status="${PIPESTATUS[0]}"
  else
    if [[ "$json_mode" == "1" ]]; then
      bash "${harness_dir}/ralphloop.sh" run --endless --json "$@"
    else
      bash "${harness_dir}/ralphloop.sh" run --endless "$@"
    fi
    run_status="$?"
  fi
  set -e

  runner_log "info: round=${round} end exit=${run_status}"
  if [[ "$run_status" -ne 0 ]]; then
    runner_log "error: stop runner due to round failure; inspect logs and resume_stderr_tail before retry."
    exit "$run_status"
  fi

  now_epoch="$(date +%s)"
  elapsed="$((now_epoch - start_epoch))"
  if [[ "$max_runtime_seconds" -gt 0 ]] && [[ "$elapsed" -ge "$max_runtime_seconds" ]]; then
    runner_log "info: stop runner because max runtime reached (${max_runtime_seconds}s)."
    exit 0
  fi

  if [[ "$sleep_seconds" -gt 0 ]]; then
    runner_log "info: round=${round} sleep=${sleep_seconds}s"
    sleep "$sleep_seconds"
  fi
done
