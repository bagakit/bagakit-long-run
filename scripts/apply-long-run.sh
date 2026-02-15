#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $(basename "$0") <project_root> [--force]" >&2
  exit 1
}

if [[ $# -lt 1 ]]; then
  usage
fi

project_root="$1"
shift
force=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      force=1
      ;;
    *)
      usage
      ;;
  esac
  shift
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill_root="$(cd "${script_dir}/.." && pwd)"
refs_dir="${skill_root}/references"
harness_dir="${project_root}/.bagakit-long-run"

copy_template() {
  local src="$1"
  local dest="$2"

  if [[ -f "$dest" ]] && cmp -s "$src" "$dest" 2>/dev/null; then
    echo "skip: ${dest} (unchanged)"
    return 0
  fi

  if [[ -f "$dest" && $force -eq 0 ]]; then
    echo "skip: ${dest} already exists"
    return 0
  fi

  cp "$src" "$dest"
  echo "write: ${dest}"
}

if [[ ! -d "$refs_dir" ]]; then
  echo "missing references dir: ${refs_dir}" >&2
  exit 1
fi

mkdir -p "$harness_dir"

copy_template "${refs_dir}/initial-prompt-template.md" "${harness_dir}/initial_prompt.md"
copy_template "${refs_dir}/coding-prompt-template.md" "${harness_dir}/coding_prompt.md"
copy_template "${refs_dir}/feature-list-template.json" "${harness_dir}/feature-list.json"
copy_template "${refs_dir}/claude-progress-template.md" "${harness_dir}/claude-progress.md"
copy_template "${refs_dir}/init-sh-template.sh" "${harness_dir}/init.sh"

if [[ -f "${harness_dir}/init.sh" ]]; then
  chmod +x "${harness_dir}/init.sh" 2>/dev/null || true
fi

gitignore_file="${harness_dir}/.gitignore"
if [[ ! -f "$gitignore_file" || $force -eq 1 ]]; then
  cat >"$gitignore_file" <<'EOF'
# Keep harness files in git by default.
# Add local-only artifacts here if needed.
EOF
  echo "write: ${gitignore_file}"
fi

echo
echo "bagakit-long-run harness ready at: ${harness_dir}"
echo "next:"
echo "  sh .bagakit-long-run/init.sh"
echo "  then run initializer -> coding loop"
