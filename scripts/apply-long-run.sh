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
harness_dir="${project_root}/.bagakit/long-run"
agents_file="${project_root}/AGENTS.md"
block_file="${refs_dir}/agents-block-template.md"
start_tag="<!-- BAGAKIT:LONGRUN:START -->"
end_tag="<!-- BAGAKIT:LONGRUN:END -->"
mkdir -p "${project_root}/.bagakit"

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

copy_managed_template() {
  local src="$1"
  local dest="$2"
  local existed=0
  if [[ -e "$dest" ]]; then
    existed=1
  fi
  if [[ -f "$dest" ]] && cmp -s "$src" "$dest" 2>/dev/null; then
    echo "skip: ${dest} (unchanged)"
    return 0
  fi
  cp "$src" "$dest"
  if [[ $existed -eq 1 ]]; then
    echo "update: ${dest}"
  else
    echo "write: ${dest}"
  fi
}

if [[ ! -d "$refs_dir" ]]; then
  echo "missing references dir: ${refs_dir}" >&2
  exit 1
fi
if [[ ! -f "$block_file" ]]; then
  echo "missing agents block template: ${block_file}" >&2
  exit 1
fi

mkdir -p "$harness_dir"

copy_template "${refs_dir}/initial-prompt-template.md" "${harness_dir}/initial_prompt.md"
copy_template "${refs_dir}/coding-prompt-template.md" "${harness_dir}/coding_prompt.md"
copy_template "${refs_dir}/feature-list-template.json" "${harness_dir}/feature-list.json"
copy_template "${refs_dir}/bk-execution-handoff-template.md" "${harness_dir}/bk-execution-handoff.md"
copy_template "${refs_dir}/bk-execution-table-template.json" "${harness_dir}/bk-execution-table.json"
copy_template "${refs_dir}/detect-prompt-template.md" "${harness_dir}/detect_prompt.md"
copy_managed_template "${refs_dir}/init-sh-template.sh" "${harness_dir}/init.sh"

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

if [[ -f "$agents_file" ]]; then
  if grep -q "${start_tag}" "$agents_file" && ! grep -q "${end_tag}" "$agents_file"; then
    echo "error: found long-run managed block start without end in ${agents_file}" >&2
    exit 1
  fi
  if grep -q "${start_tag}" "$agents_file"; then
    awk -v start="$start_tag" -v end="$end_tag" -v blockFile="$block_file" '
      function print_block() {
        while ((getline line < blockFile) > 0) {
          print line
        }
        close(blockFile)
      }
      BEGIN { in_block = 0 }
      $0 == start {
        print_block()
        in_block = 1
        next
      }
      in_block {
        if ($0 == end) {
          in_block = 0
        }
        next
      }
      { print }
    ' "$agents_file" > "${agents_file}.tmp"
    mv "${agents_file}.tmp" "$agents_file"
    echo "update: ${agents_file} (replaced long-run block)"
  else
    printf "\n" >> "$agents_file"
    cat "$block_file" >> "$agents_file"
    printf "\n" >> "$agents_file"
    echo "update: ${agents_file} (appended long-run block)"
  fi
else
  cat "$block_file" > "$agents_file"
  echo "write: ${agents_file}"
fi

echo
rel_harness="${harness_dir#${project_root}/}"
echo "bagakit-long-run harness ready at: ${harness_dir}"
echo "agents block: BAGAKIT:LONGRUN in ${agents_file}"
echo "next:"
echo "  0) run detect pass with ${rel_harness}/detect_prompt.md and mark table detection.status=ready"
echo "  1) sh ${rel_harness}/init.sh"
echo "  2) run initializer -> coding loop"
