#!/usr/bin/env bash
set -euo pipefail

harness_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sleep_seconds="${RALPHLOOP_SLEEP_SECONDS:-1}"
one_shot="${RALPHLOOP_ONE_SHOT:-0}"

if [[ -z "${BAGAKIT_AGENT_CMD:-}" && -z "${BAGAKIT_AGENT_CLI:-}" ]]; then
  echo "warn: BAGAKIT_AGENT_CMD/BAGAKIT_AGENT_CLI is not configured; fallback to one pulse." >&2
  exec bash "${harness_dir}/ralphloop.sh" pulse --endless "$@"
fi

echo "info: outer runner expects non-interactive agent command (for example: codex exec ...)." >&2

while true; do
  bash "${harness_dir}/ralphloop.sh" run --endless "$@"

  if [[ "$one_shot" == "1" ]]; then
    exit 0
  fi

  if [[ "$sleep_seconds" =~ ^[0-9]+$ ]] && [[ "$sleep_seconds" -gt 0 ]]; then
    sleep "$sleep_seconds"
  fi
done
