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
tpl_dir="${refs_dir}/tpl"
harness_dir="${project_root}/.bagakit/long-run"
inbox_dir="${harness_dir}/inbox"
agents_file="${project_root}/AGENTS.md"
block_file="${tpl_dir}/agents-block-template.md"
heartbeat_config_template="${tpl_dir}/heartbeat-config-template.json"
heartbeat_schedules_template="${tpl_dir}/heartbeat-schedules-template.json"
heartbeat_inbox_readme_template="${tpl_dir}/heartbeat-inbox-readme-template.md"
ralphloop_template="${tpl_dir}/ralphloop-sh-template.md"
ralphloop_runner_template="${tpl_dir}/ralphloop-runner-sh-template.md"
start_tag="<!-- BAGAKIT:LONGRUN:START -->"
end_tag="<!-- BAGAKIT:LONGRUN:END -->"
launcher_start="# BAGAKIT:LONGRUN:LAUNCHER:START"
launcher_end="# BAGAKIT:LONGRUN:LAUNCHER:END"
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

remove_legacy_file() {
  local path="$1"
  if [[ -e "$path" ]]; then
    rm -rf "$path"
    echo "remove: ${path} (legacy)"
  fi
}

wire_package_json_launcher() {
  local package_file="${project_root}/package.json"
  if [[ ! -f "$package_file" ]]; then
    return 1
  fi

  local result
  if ! result="$(
    python3 - "$package_file" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception as exc:  # noqa: BLE001
    print(f"error: cannot parse {path}: {exc}", file=sys.stderr)
    raise SystemExit(1)

if not isinstance(data, dict):
    print(f"error: package file is not a JSON object: {path}", file=sys.stderr)
    raise SystemExit(1)

scripts = data.get("scripts")
if not isinstance(scripts, dict):
    scripts = {}

command = "bash .bagakit/long-run/ralphloop-runner.sh"
if scripts.get("ralphloop") == command:
    print("skip")
    raise SystemExit(0)

scripts["ralphloop"] = command
data["scripts"] = scripts
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("update")
PY
  )"; then
    return 1
  fi

  if [[ "$result" == "update" ]]; then
    echo "update: ${package_file} (scripts.ralphloop)"
  else
    echo "skip: ${package_file} (scripts.ralphloop unchanged)"
  fi
  return 0
}

wire_makefile_launcher() {
  local makefile="${project_root}/Makefile"
  if [[ ! -f "$makefile" ]]; then
    return 1
  fi

  if grep -q "${launcher_start}" "$makefile" && ! grep -q "${launcher_end}" "$makefile"; then
    echo "error: found launcher block start without end in ${makefile}" >&2
    exit 1
  fi

  local tmp="${makefile}.tmp"
  local block
  block="$(cat <<EOF
${launcher_start}
ralphloop:
	bash .bagakit/long-run/ralphloop-runner.sh
.PHONY: ralphloop
${launcher_end}
EOF
)"

  if grep -q "${launcher_start}" "$makefile"; then
    awk -v start="$launcher_start" -v end="$launcher_end" -v block="$block" '
      BEGIN { in_block = 0; replaced = 0 }
      $0 == start {
        print block
        in_block = 1
        replaced = 1
        next
      }
      in_block {
        if ($0 == end) {
          in_block = 0
        }
        next
      }
      { print }
      END {
        if (replaced == 0) {
          print ""
          print block
        }
      }
    ' "$makefile" > "$tmp"
    mv "$tmp" "$makefile"
    echo "update: ${makefile} (managed ralphloop target)"
    return 0
  fi

  printf "\n%s\n" "$block" >> "$makefile"
  echo "update: ${makefile} (appended ralphloop target)"
  return 0
}

wire_shell_launcher() {
  local launcher="${project_root}/ralphloop"
  local expected
expected="$(cat <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exec bash .bagakit/long-run/ralphloop-runner.sh "$@"
EOF
)"

  if [[ -f "$launcher" ]]; then
    if [[ "$(cat "$launcher")" == "$expected" ]]; then
      echo "skip: ${launcher} (unchanged)"
      return 0
    fi
    if [[ $force -eq 0 ]]; then
      echo "skip: ${launcher} already exists"
      return 0
    fi
  fi

  printf "%s\n" "$expected" > "$launcher"
  chmod +x "$launcher" 2>/dev/null || true
  echo "write: ${launcher}"
  return 0
}

write_project_profile() {
  local launcher_route="$1"
  local profile_file="${harness_dir}/project-profile.json"

  python3 - "$project_root" "$profile_file" "$launcher_route" <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys

project_root = Path(sys.argv[1]).resolve()
profile_file = Path(sys.argv[2])
launcher_route = sys.argv[3].strip()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def exists(path: str) -> bool:
    return (project_root / path).exists()


def detect_stack() -> tuple[str, list[str]]:
    signals: list[str] = []
    if exists("package.json"):
        signals.append("package.json")
    if exists("pyproject.toml") or exists("requirements.txt"):
        signals.append("python")
    if exists("go.mod"):
        signals.append("go.mod")
    if exists("Cargo.toml"):
        signals.append("Cargo.toml")
    if exists("pom.xml") or exists("build.gradle") or exists("build.gradle.kts"):
        signals.append("jvm-build")
    if exists("Gemfile"):
        signals.append("gemfile")

    if "package.json" in signals:
        return "node", signals
    if "python" in signals:
        return "python", signals
    if "go.mod" in signals:
        return "go", signals
    if "Cargo.toml" in signals:
        return "rust", signals
    if "jvm-build" in signals:
        return "jvm", signals
    if "gemfile" in signals:
        return "ruby", signals
    return "unknown", signals


def detect_package_manager() -> str:
    if exists("pnpm-lock.yaml"):
        return "pnpm"
    if exists("yarn.lock"):
        return "yarn"
    if exists("bun.lockb") or exists("bun.lock"):
        return "bun"
    return "npm"


def script_command(manager: str, script_name: str) -> str:
    if manager == "yarn":
        return f"yarn {script_name}"
    if manager == "bun":
        return f"bun run {script_name}"
    return f"{manager} run {script_name}"


def detect_package_commands() -> list[str]:
    package_file = project_root / "package.json"
    if not package_file.exists():
        return []

    try:
        data = json.loads(package_file.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    scripts = data.get("scripts")
    if not isinstance(scripts, dict):
        return []

    manager = detect_package_manager()
    ordered = [
        "test",
        "lint",
        "typecheck",
        "check",
        "validate",
        "build",
        "ci",
    ]
    commands: list[str] = []
    for key in ordered:
        if key in scripts:
            commands.append(script_command(manager, key))
    return commands


def detect_make_commands() -> list[str]:
    makefile = project_root / "Makefile"
    if not makefile.exists():
        return []
    text = makefile.read_text(encoding="utf-8", errors="ignore")
    targets: set[str] = set()
    for line in text.splitlines():
        if line.startswith("\t") or not line.strip() or line.strip().startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)\s*:", line)
        if not match:
            continue
        target = match.group(1)
        if "%" in target:
            continue
        targets.add(target)

    ordered = ["test", "lint", "check", "validate", "build", "ci"]
    return [f"make {name}" for name in ordered if name in targets]


def detect_stack_commands(stack: str) -> list[str]:
    if stack == "python":
        if exists("pytest.ini") or exists("pyproject.toml") or exists("tests"):
            return ["pytest -q"]
        return []
    if stack == "go":
        return ["go test ./..."]
    if stack == "rust":
        return ["cargo test"]
    return []


def detect_analysis_paths() -> list[str]:
    ordered = [
        "src",
        "app",
        "lib",
        "pkg",
        "internal",
        "cmd",
        "tests",
        "test",
        "docs",
        ".bagakit",
    ]
    out: list[str] = []
    for rel in ordered:
        if (project_root / rel).exists():
            out.append(rel)
    return out


def launcher_command(route: str) -> str:
    if route.startswith("package.json"):
        return script_command(detect_package_manager(), "ralphloop")
    if route.startswith("Makefile"):
        return "make ralphloop"
    return "./ralphloop"


def detect_agent_hint() -> str:
    for key in ("BAGAKIT_AGENT_CLI", "BAGAKIT_AGENT_CMD"):
        value = os.environ.get(key, "").strip()
        if value:
            return value

    ppid = os.getppid()
    proc = subprocess.run(
        ["ps", "-o", "comm=", "-p", str(ppid)],
        text=True,
        capture_output=True,
    )
    hint = proc.stdout.strip()
    return hint or "agent-cli"


def detect_agent_command() -> str:
    for key in ("BAGAKIT_AGENT_CMD", "BAGAKIT_AGENT_CLI"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""


stack, signals = detect_stack()
quality_commands = detect_package_commands()
for cmd in detect_make_commands():
    if cmd not in quality_commands:
        quality_commands.append(cmd)
for cmd in detect_stack_commands(stack):
    if cmd not in quality_commands:
        quality_commands.append(cmd)

payload = {
    "version": 1,
    "generated_at": utc_now(),
    "stack": {
        "primary": stack,
        "signals": signals,
    },
    "launcher": {
        "route": launcher_route,
        "command": launcher_command(launcher_route),
    },
    "agent": {
        "hint": detect_agent_hint(),
        "command": detect_agent_command(),
    },
    "analysis_paths": detect_analysis_paths(),
    "quality_commands": quality_commands,
}

content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
if profile_file.exists() and profile_file.read_text(encoding="utf-8") == content:
    print(f"skip: {profile_file} (unchanged)")
else:
    profile_file.write_text(content, encoding="utf-8")
    print(f"write: {profile_file}")
PY
}

if [[ ! -d "$refs_dir" ]]; then
  echo "missing references dir: ${refs_dir}" >&2
  exit 1
fi
if [[ ! -d "$tpl_dir" ]]; then
  echo "missing templates dir: ${tpl_dir}" >&2
  exit 1
fi
if [[ ! -f "$block_file" ]]; then
  echo "missing agents block template: ${block_file}" >&2
  exit 1
fi
for required_ref in "$heartbeat_config_template" "$heartbeat_schedules_template" "$heartbeat_inbox_readme_template" "$ralphloop_template" "$ralphloop_runner_template"; do
  if [[ ! -f "$required_ref" ]]; then
    echo "missing reference template: ${required_ref}" >&2
    exit 1
  fi
done

mkdir -p "$harness_dir"
mkdir -p "${inbox_dir}/history" "${inbox_dir}/flash-ideas" "${harness_dir}/schedules/generated"

copy_managed_template "${tpl_dir}/detect-prompt-template.md" "${harness_dir}/detect_prompt.md"
copy_managed_template "${tpl_dir}/initializer-prompt-template.md" "${harness_dir}/initializer_prompt.md"
copy_managed_template "${tpl_dir}/coding-prompt-template.md" "${harness_dir}/coding_prompt.md"
copy_template "${tpl_dir}/feature-list-template.json" "${harness_dir}/feature-list.json"
copy_template "${tpl_dir}/bk-execution-handoff-template.md" "${harness_dir}/bk-execution-handoff.md"
copy_template "${tpl_dir}/bk-execution-table-template.json" "${harness_dir}/bk-execution-table.json"
copy_managed_template "${tpl_dir}/check-and-resume-sh-template.md" "${harness_dir}/check_and_resume.sh"
copy_managed_template "${tpl_dir}/ralphloop-sh-template.md" "${harness_dir}/ralphloop.sh"
copy_managed_template "${tpl_dir}/ralphloop-runner-sh-template.md" "${harness_dir}/ralphloop-runner.sh"
copy_template "$heartbeat_config_template" "${harness_dir}/heartbeat.config.json"
copy_template "$heartbeat_schedules_template" "${harness_dir}/heartbeat-schedules.json"
copy_template "$heartbeat_inbox_readme_template" "${inbox_dir}/README.md"

heartbeat_state_file="${harness_dir}/heartbeat.state.json"
if [[ ! -f "$heartbeat_state_file" || $force -eq 1 ]]; then
  cat >"$heartbeat_state_file" <<'EOF'
{
  "version": 1,
  "last_tick_at": "",
  "last_success_at": "",
  "recent_executions": [],
  "cooldown_minutes": 120
}
EOF
  echo "write: ${heartbeat_state_file}"
fi

heartbeat_queue_file="${inbox_dir}/queue.json"
if [[ ! -f "$heartbeat_queue_file" || $force -eq 1 ]]; then
  cat >"$heartbeat_queue_file" <<'EOF'
{
  "version": 1,
  "items": []
}
EOF
  echo "write: ${heartbeat_queue_file}"
fi

# Final-state cleanup: remove old long-run artifacts.
remove_legacy_file "${harness_dir}/init.sh"
remove_legacy_file "${harness_dir}/initial_prompt.md"

if [[ -f "${harness_dir}/check_and_resume.sh" ]]; then
  chmod +x "${harness_dir}/check_and_resume.sh" 2>/dev/null || true
fi
if [[ -f "${harness_dir}/ralphloop.sh" ]]; then
  chmod +x "${harness_dir}/ralphloop.sh" 2>/dev/null || true
fi
if [[ -f "${harness_dir}/ralphloop-runner.sh" ]]; then
  chmod +x "${harness_dir}/ralphloop-runner.sh" 2>/dev/null || true
fi
if [[ -f "${skill_root}/scripts/long-run-heartbeat.py" ]]; then
  chmod +x "${skill_root}/scripts/long-run-heartbeat.py" 2>/dev/null || true
fi
if [[ -f "${skill_root}/scripts/long-run-loop.py" ]]; then
  chmod +x "${skill_root}/scripts/long-run-loop.py" 2>/dev/null || true
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

launcher_route=""
if [[ -f "${project_root}/package.json" ]]; then
  wire_package_json_launcher
  launcher_route="package.json:scripts.ralphloop"
elif [[ -f "${project_root}/Makefile" ]]; then
  wire_makefile_launcher
  launcher_route="Makefile:ralphloop"
else
  wire_shell_launcher
  launcher_route="./ralphloop"
fi

write_project_profile "$launcher_route"

echo
rel_harness="${harness_dir#${project_root}/}"
echo "bagakit-long-run harness ready at: ${harness_dir}"
echo "agents block: BAGAKIT:LONGRUN in ${agents_file}"
echo "launcher route: ${launcher_route}"
echo "project profile: ${rel_harness}/project-profile.json"
echo "next:"
echo "  0) run detect pass with ${rel_harness}/detect_prompt.md and mark table detection.status=ready"
echo "  1) bash ${rel_harness}/check_and_resume.sh"
echo "  1b) trigger one pulse: bash ${rel_harness}/ralphloop.sh pulse --endless"
echo "  1c-setup) export BAGAKIT_AGENT_CMD='codex exec {prompt_text}'  # non-interactive required"
echo "  1c) start continuous loop: bash ${rel_harness}/ralphloop-runner.sh"
echo "  2) run initializer -> coding loop"
echo "  3) optional heartbeat tick: python3 \"\$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-heartbeat.py\" tick . --json"
echo "  4) optional schedule list: python3 \"\$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-heartbeat.py\" schedule-list ."
