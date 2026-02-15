#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target="${script_dir}/bagakit_long_run_doctor.sh"

if [[ ! -x "$target" ]]; then
  echo "missing doctor implementation: ${target}" >&2
  exit 1
fi

exec "$target" "$@"
