#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$(basename "$script_dir")" == ".gen" ]]; then
  harness_dir="$(cd "${script_dir}/.." && pwd)"
else
  harness_dir="$script_dir"
fi
project_root="$(cd "${harness_dir}/../.." && pwd)"
skill_dir="${BAGAKIT_LONG_RUN_SKILL_DIR:-}"
if [[ -z "$skill_dir" ]]; then
  echo "error: BAGAKIT_LONG_RUN_SKILL_DIR is required and must point to the bagakit-long-run skill root." >&2
  exit 1
fi
loop_tool="${skill_dir}/scripts/long-run-loop.py"

usage() {
  cat >&2 <<'EOF'
Usage:
  bash .bagakit/long-run/ralphloop.sh pulse [--endless] [--json]
  bash .bagakit/long-run/ralphloop.sh run [--endless] [--json]
  bash .bagakit/long-run/ralphloop.sh plan [--json]
  bash .bagakit/long-run/ralphloop.sh preflight [--json]
EOF
  exit 1
}

if [[ $# -lt 1 ]]; then
  usage
fi

if [[ ! -f "$loop_tool" ]]; then
  echo "error: missing long-run loop tool at ${loop_tool}" >&2
  echo "set BAGAKIT_LONG_RUN_SKILL_DIR to a valid bagakit-long-run skill root." >&2
  exit 1
fi

msg_file="${harness_dir}/ralph-msg.md"
if [[ ! -f "$msg_file" ]]; then
  : > "$msg_file"
fi

command="$1"
shift || true

case "$command" in
  pulse|run|plan|preflight)
    python3 "$loop_tool" "$command" "$project_root" "$@"
    ;;
  *)
    usage
    ;;
esac
