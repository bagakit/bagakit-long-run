#!/usr/bin/env bash
set -euo pipefail

harness_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "${harness_dir}/../.." && pwd)"
skill_dir="${BAGAKIT_LONG_RUN_SKILL_DIR:-${BAGAKIT_HOME:-$HOME/.bagakit}/skills/bagakit-long-run}"
loop_tool="${skill_dir}/scripts/long-run-loop.py"

usage() {
  cat >&2 <<'EOF'
Usage:
  bash .bagakit/long-run/ralphloop.sh pulse [--endless] [--json]
  bash .bagakit/long-run/ralphloop.sh run [--endless] [--json]
  bash .bagakit/long-run/ralphloop.sh plan [--json]
EOF
  exit 1
}

if [[ $# -lt 1 ]]; then
  usage
fi

if [[ ! -f "$loop_tool" ]]; then
  echo "error: missing long-run loop tool at ${loop_tool}" >&2
  echo "set BAGAKIT_LONG_RUN_SKILL_DIR (or BAGAKIT_HOME) to your installed skill path." >&2
  exit 1
fi

command="$1"
shift || true

case "$command" in
  pulse|run|plan)
    python3 "$loop_tool" "$command" "$project_root" "$@"
    ;;
  *)
    usage
    ;;
esac
