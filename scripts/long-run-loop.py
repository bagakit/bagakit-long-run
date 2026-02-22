#!/usr/bin/env python3
"""Minimal pulse entry for bagakit-long-run.

This runner intentionally stays small:
- run check_and_resume
- surface next actionable row
- when no row and --endless, generate an expansion prompt for the agent
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, List

KNOWN_AGENT_CLI_BINARIES = {
    "codex",
    "claude",
    "cc",
    "gemini",
}
NON_INTERACTIVE_HINTS = (
    " exec ",
    " --non-interactive ",
    " --no-interactive ",
    " --print ",
    " --prompt ",
    " --message ",
    " --stdin ",
    " -p ",
    " {prompt_file} ",
    " {prompt_text} ",
)


def read_json(path: Path) -> Dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"error: file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: invalid json in {path}: {exc}")
    if not isinstance(raw, dict):
        raise SystemExit(f"error: top-level json must be object: {path}")
    return raw


def run_resume(project_root: Path) -> tuple[int, str]:
    proc = subprocess.run(
        ["bash", ".bagakit/long-run/check_and_resume.sh"],
        cwd=project_root,
        text=True,
        capture_output=True,
    )
    return proc.returncode, proc.stderr[-400:]


def detect_cli_hint() -> str:
    for key in ("BAGAKIT_AGENT_CMD", "BAGAKIT_AGENT_CLI"):
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


def read_project_context(feature_file: Path) -> tuple[str, str]:
    if not feature_file.exists():
        return "", ""
    data = read_json(feature_file)
    project = data.get("project", {})
    if not isinstance(project, dict):
        return "", ""
    name = str(project.get("name", "")).strip()
    goal = str(project.get("goal", "")).strip()
    return name, goal


def to_str_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def read_project_profile(profile_file: Path) -> Dict[str, Any]:
    if not profile_file.exists():
        return {}
    data = read_json(profile_file)
    return data if isinstance(data, dict) else {}


def render_profile_section(profile: Dict[str, Any], cli_hint: str) -> str:
    stack = profile.get("stack", {}) if isinstance(profile.get("stack"), dict) else {}
    launcher = profile.get("launcher", {}) if isinstance(profile.get("launcher"), dict) else {}
    agent = profile.get("agent", {}) if isinstance(profile.get("agent"), dict) else {}
    analysis_paths = to_str_list(profile.get("analysis_paths"))
    quality_commands = to_str_list(profile.get("quality_commands"))

    primary_stack = str(stack.get("primary", "unknown")).strip() or "unknown"
    route = str(launcher.get("route", "")).strip() or "(not-detected)"
    launch_cmd = str(launcher.get("command", "")).strip() or "bash .bagakit/long-run/ralphloop-runner.sh"
    agent_hint = str(agent.get("hint", "")).strip() or cli_hint
    agent_command = str(agent.get("command", "")).strip() or "(set BAGAKIT_AGENT_CMD)"

    lines = [
        "项目检测上下文（由 apply-long-run 生成）:",
        f"- primary_stack: {primary_stack}",
        f"- launcher_route: {route}",
        f"- launcher_command: {launch_cmd}",
        f"- agent_cli_hint: {agent_hint}",
        f"- agent_command: {agent_command}",
    ]

    if analysis_paths:
        lines.append("- preferred_analysis_paths: " + ", ".join(analysis_paths))
    else:
        lines.append("- preferred_analysis_paths: (auto-discover)")

    if quality_commands:
        lines.append("- preferred_quality_commands:")
        for command in quality_commands:
            lines.append(f"  - {command}")
    else:
        lines.append("- preferred_quality_commands: (detect and propose)")

    return "\n".join(lines)


def render_endless_prompt(project_name: str, project_goal: str, profile: Dict[str, Any], cli_hint: str) -> str:
    name = project_name or "当前项目"
    goal = project_goal or "（未声明，先从代码与文档反推项目目标）"
    profile_section = render_profile_section(profile, cli_hint)
    return f"""# Endless Expansion Prompt

你现在处于 long-run 的“无下一步”状态，需要先补全计划再继续执行。

项目：{name}
项目目标：{goal}
{profile_section}

现在请完整分析项目，了解项目目标和具体实现，审查发现脆弱环节和优化点，提升代码质量和鲁棒性，提高测试覆盖，优化架构，提高复用降低耦合，优化圈复杂度，优化性能和安全性等。分析完成后，根据结果，按照优先级扩充 long-run 计划。

执行要求：
1. 先通读关键代码、测试、配置与文档，给出结构化风险清单（按优先级）。
2. 将结论落地到 `.bagakit/long-run/bk-execution-table.json`（优先使用 `manual` rows，字段必须完整：why_now/acceptance_criteria/files_to_touch/commands/confidence/evidence）。
3. 计划必须可执行：每条 row 都要有明确命令与可验证完成标准，且单条 row 保持“最小闭环”。
4. 你后续进入执行阶段时，每个最小闭环后提交一个 git commit（小而可追踪）。
5. 更新完成后，运行 `bash .bagakit/long-run/check_and_resume.sh`，确保 next-action 恢复可执行。

输出要求：
- 先给“新增/调整的 rows 摘要（按优先级）”
- 再给验证结果与下一条建议执行项
"""


def emit(payload: Dict[str, Any], as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return int(payload.get("exit_code", 0))

    print(f"status: {payload.get('status', 'unknown')}")
    if payload.get("reason"):
        print(f"reason: {payload.get('reason')}")
    if payload.get("detected_cli"):
        print(f"detected_cli: {payload.get('detected_cli')}")
    if payload.get("pulse_status"):
        print(f"pulse_status: {payload.get('pulse_status')}")
    if payload.get("next_row_id"):
        print(f"next_row: {payload.get('next_row_id')} {payload.get('next_row_title', '')}".strip())
        print("use_prompt: .bagakit/long-run/coding_prompt.md")
    if payload.get("endless_prompt_file"):
        print(f"endless_prompt_file: {payload.get('endless_prompt_file')}")
    prompts = payload.get("executed_prompts")
    if isinstance(prompts, list) and prompts:
        print("executed_prompts:")
        for item in prompts:
            print(f"- {item}")
    if payload.get("agent_command"):
        print(f"agent_command: {payload.get('agent_command')}")
    return int(payload.get("exit_code", 0))


def build_pulse_payload(project_root: Path, endless: bool) -> Dict[str, Any]:
    harness_dir = project_root / ".bagakit" / "long-run"
    next_action_file = harness_dir / "next-action.json"
    feature_file = harness_dir / "feature-list.json"
    profile_file = harness_dir / "project-profile.json"
    cli_hint = detect_cli_hint()

    payload: Dict[str, Any] = {
        "status": "unknown",
        "reason": "",
        "detected_cli": cli_hint,
        "next_row_id": "",
        "next_row_title": "",
        "endless_prompt_file": "",
        "exit_code": 0,
    }

    resume_rc, resume_stderr = run_resume(project_root)
    if resume_rc != 0:
        payload.update(
            {
                "status": "failed",
                "reason": "check_and_resume_failed",
                "resume_stderr_tail": resume_stderr,
                "exit_code": 1,
            }
        )
        return payload

    if not next_action_file.exists():
        payload.update(
            {
                "status": "failed",
                "reason": "next_action_missing",
                "exit_code": 1,
            }
        )
        return payload

    next_action = read_json(next_action_file)
    next_row = next_action.get("next_row")
    if isinstance(next_row, dict) and str(next_row.get("id", "")).strip():
        payload.update(
            {
                "status": "actionable",
                "reason": "next_row_ready",
                "next_row_id": str(next_row.get("id", "")).strip(),
                "next_row_title": str(next_row.get("title", "")).strip(),
            }
        )
        return payload

    if endless:
        project_name, project_goal = read_project_context(feature_file)
        project_profile = read_project_profile(profile_file)
        prompt_text = render_endless_prompt(project_name, project_goal, project_profile, cli_hint)
        prompt_file = harness_dir / "endless_expand_prompt.md"
        prompt_file.write_text(prompt_text, encoding="utf-8")
        payload.update(
            {
                "status": "endless_prompt_ready",
                "reason": "no_actionable_row",
                "endless_prompt_file": str(prompt_file),
            }
        )
        return payload

    payload.update(
        {
            "status": "no_action",
            "reason": "no_actionable_row",
        }
    )
    return payload


def cmd_pulse(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    payload = build_pulse_payload(project_root, args.endless)
    return emit(payload, args.json)


def prompt_files_for_pulse(payload: Dict[str, Any], harness_dir: Path) -> List[Path]:
    status = str(payload.get("status", "")).strip()
    if status == "actionable":
        return [
            harness_dir / "initializer_prompt.md",
            harness_dir / "coding_prompt.md",
        ]
    if status == "endless_prompt_ready":
        prompt_file = str(payload.get("endless_prompt_file", "")).strip()
        if prompt_file:
            return [Path(prompt_file).resolve()]
    return []


def resolve_agent_command(profile: Dict[str, Any]) -> str:
    for key in ("BAGAKIT_AGENT_CMD", "BAGAKIT_AGENT_CLI"):
        value = os.environ.get(key, "").strip()
        if value:
            return value

    agent = profile.get("agent")
    if isinstance(agent, dict):
        value = str(agent.get("command", "")).strip()
        if value:
            return value
    return ""


def interactive_agent_command_reason(command_template: str) -> str:
    if os.environ.get("BAGAKIT_ALLOW_INTERACTIVE_AGENT_CMD", "").strip() == "1":
        return ""

    text = command_template.strip()
    if not text:
        return ""
    try:
        parts = shlex.split(text)
    except ValueError:
        parts = text.split()
    if not parts:
        return ""

    cmd0 = Path(parts[0]).name.lower()
    if cmd0 not in KNOWN_AGENT_CLI_BINARIES:
        return ""

    normalized = f" {text.lower()} "
    if any(hint in normalized for hint in NON_INTERACTIVE_HINTS):
        return ""

    return (
        f"agent command '{text}' looks interactive (TUI). "
        "use non-interactive form (for example: codex exec {prompt_text})."
    )


def render_agent_command(command_template: str, prompt_file: Path, project_root: Path) -> str:
    prompt_file_q = shlex.quote(str(prompt_file))
    project_root_q = shlex.quote(str(project_root))
    has_placeholder = ("{prompt_file}" in command_template) or ("{project_root}" in command_template)

    rendered = command_template.replace("{prompt_file}", prompt_file_q).replace("{project_root}", project_root_q)

    if "{prompt_text}" in rendered:
        prompt_text = prompt_file.read_text(encoding="utf-8")
        rendered = rendered.replace("{prompt_text}", shlex.quote(prompt_text))
        has_placeholder = True

    if not has_placeholder:
        rendered = f"{rendered} {prompt_file_q}"
    return rendered


def run_agent_prompt(project_root: Path, command_template: str, prompt_file: Path, verbose: bool = False) -> int:
    command = render_agent_command(command_template, prompt_file, project_root)
    if verbose:
        print(f"agent_command: {command}")
    proc = subprocess.run(
        ["bash", "-lc", command],
        cwd=project_root,
        text=True,
    )
    return int(proc.returncode)


def cmd_run(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    harness_dir = project_root / ".bagakit" / "long-run"
    profile_file = harness_dir / "project-profile.json"

    payload = build_pulse_payload(project_root, args.endless)
    pulse_status = str(payload.get("status", "")).strip()

    result: Dict[str, Any] = {
        "status": "run_unknown",
        "reason": "",
        "pulse_status": pulse_status,
        "detected_cli": payload.get("detected_cli", ""),
        "executed_prompts": [],
        "agent_command": "",
        "exit_code": 0,
    }

    if pulse_status == "failed":
        result.update(
            {
                "status": "run_failed",
                "reason": str(payload.get("reason", "pulse_failed")),
                "resume_stderr_tail": payload.get("resume_stderr_tail", ""),
                "exit_code": 1,
            }
        )
        return emit(result, args.json)

    prompt_files = prompt_files_for_pulse(payload, harness_dir)
    if not prompt_files:
        result.update(
            {
                "status": "run_no_action",
                "reason": str(payload.get("reason", "no_actionable_row")),
            }
        )
        return emit(result, args.json)

    project_profile = read_project_profile(profile_file)
    agent_command = resolve_agent_command(project_profile)
    result["agent_command"] = agent_command
    if not agent_command:
        result.update(
            {
                "status": "agent_command_missing",
                "reason": "set BAGAKIT_AGENT_CMD (or BAGAKIT_AGENT_CLI) to run prompts automatically",
                "exit_code": 2,
            }
        )
        return emit(result, args.json)

    interactive_reason = interactive_agent_command_reason(agent_command)
    if interactive_reason:
        result.update(
            {
                "status": "agent_command_interactive",
                "reason": interactive_reason,
                "exit_code": 2,
            }
        )
        return emit(result, args.json)

    for prompt_file in prompt_files:
        if not prompt_file.exists():
            result.update(
                {
                    "status": "run_failed",
                    "reason": f"missing_prompt:{prompt_file}",
                    "exit_code": 1,
                }
            )
            return emit(result, args.json)

    if args.dry_run:
        result.update(
            {
                "status": "run_dry",
                "reason": "dry_run",
                "executed_prompts": [str(path) for path in prompt_files],
            }
        )
        return emit(result, args.json)

    for prompt_file in prompt_files:
        rc = run_agent_prompt(project_root, agent_command, prompt_file, verbose=args.verbose)
        result["executed_prompts"].append(str(prompt_file))
        if rc != 0:
            result.update(
                {
                    "status": "run_failed",
                    "reason": f"agent_command_failed:{prompt_file}",
                    "exit_code": rc,
                }
            )
            return emit(result, args.json)

    result.update(
        {
            "status": "run_completed",
            "reason": "agent_prompts_executed",
        }
    )
    return emit(result, args.json)


def cmd_plan(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    skill_root = Path(__file__).resolve().parents[1]
    execution_tool = skill_root / "scripts" / "long-run-execution.py"
    table_path = (
        Path(args.table).resolve()
        if args.table
        else project_root / ".bagakit" / "long-run" / "bk-execution-table.json"
    )
    command = [
        "python3",
        str(execution_tool),
        "plan",
        str(project_root),
        "--table",
        str(table_path),
        "--limit",
        str(args.limit),
    ]
    if args.json:
        command.append("--json")
    proc = subprocess.run(command, cwd=project_root, text=True)
    return proc.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="bagakit-long-run pulse entry")
    sub = parser.add_subparsers(dest="command", required=True)

    p_pulse = sub.add_parser("pulse", help="run check+resume and return next action")
    p_pulse.add_argument("project_root")
    p_pulse.add_argument("--endless", action="store_true")
    p_pulse.add_argument("--json", action="store_true")
    p_pulse.set_defaults(func=cmd_pulse)

    p_run = sub.add_parser("run", help="run one pulse and dispatch resulting prompts to local agent")
    p_run.add_argument("project_root")
    p_run.add_argument("--endless", action="store_true")
    p_run.add_argument("--json", action="store_true")
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--verbose", action="store_true")
    p_run.set_defaults(func=cmd_run)

    p_plan = sub.add_parser("plan", help="print normalized execution rows")
    p_plan.add_argument("project_root")
    p_plan.add_argument("--table", default="")
    p_plan.add_argument("--limit", type=int, default=8)
    p_plan.add_argument("--json", action="store_true")
    p_plan.set_defaults(func=cmd_plan)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
