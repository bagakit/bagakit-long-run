#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill_root="$(cd "${script_dir}/.." && pwd)"

tmp="$(mktemp -d -t bagakit-long-run-test.XXXXXX)"
trap 'rm -rf "$tmp"' EXIT

project="${tmp}/project"
mkdir -p "$project"

echo "[test] apply harness"
bash "${script_dir}/apply-long-run.sh" "$project"

echo "[test] validate harness"
bash "${script_dir}/validate-long-run.sh" "$project"

echo "[test] doctor"
bash "${script_dir}/bagakit_long_run_doctor.sh" "$project"

echo "[test] idempotent apply"
bash "${script_dir}/apply-long-run.sh" "$project"

echo "[test] python tool summary"
python3 "${script_dir}/bagakit_long_run_features.py" summary "${project}/.bagakit-long-run/feature-list.json" >/dev/null

echo "[test] pass (${skill_root})"
