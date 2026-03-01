#!/usr/bin/env python3
"""Minimal pulse entry for bagakit-long-run.

This runner intentionally stays small:
- run check_and_resume
- surface next actionable row
- when no row and --endless, generate an expansion prompt for the agent
- optionally consume async user message from .bagakit/long-run/ralph-msg.md and inject into run prompts
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

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

MESSAGE_SEPARATOR_RE = re.compile(r"(?m)^\s*---\s*$")
OUTCOME_START_MARKER = "<!-- LONG_RUN_OUTCOME_JSON:START -->"
OUTCOME_END_MARKER = "<!-- LONG_RUN_OUTCOME_JSON:END -->"
LEGACY_RC_ONLY_ENV = "BAGAKIT_LONG_RUN_LEGACY_RC_ONLY"

OUTCOME_STATUS_ALLOWED = {"done", "in_progress", "blocked", "retry", "no_action"}
OUTCOME_PASS_ALLOWED = {"initializer", "coding", "endless_expand"}
OUTCOME_POSITIVE_RESULTS = {"pass", "passed", "ok", "success", "true", "1"}

ANOMALY_ENV_NO_WRITE = "ENV_NO_WRITE"
ANOMALY_ENV_NO_TMP = "ENV_NO_TMP"
ANOMALY_PROMPT_CONTRACT_MISSING = "PROMPT_CONTRACT_MISSING"
ANOMALY_OUTCOME_SCHEMA_INVALID = "OUTCOME_SCHEMA_INVALID"
ANOMALY_ACCEPTANCE_FAILED = "ACCEPTANCE_FAILED"
ANOMALY_UPSTREAM_ROW_STALE = "UPSTREAM_ROW_STALE"
ANOMALY_AGENT_RUNTIME_ERROR = "AGENT_RUNTIME_ERROR"

ANOMALY_ACTION_BLOCKED_STOP = "blocked_stop"
ANOMALY_ACTION_RETRYABLE = "retryable"
ANOMALY_ACTION_NEEDS_DETECT = "needs_detect"
ANOMALY_ACTION_MAP = {
    ANOMALY_ENV_NO_WRITE: ANOMALY_ACTION_BLOCKED_STOP,
    ANOMALY_ENV_NO_TMP: ANOMALY_ACTION_BLOCKED_STOP,
    ANOMALY_PROMPT_CONTRACT_MISSING: ANOMALY_ACTION_RETRYABLE,
    ANOMALY_OUTCOME_SCHEMA_INVALID: ANOMALY_ACTION_RETRYABLE,
    ANOMALY_ACCEPTANCE_FAILED: ANOMALY_ACTION_RETRYABLE,
    ANOMALY_UPSTREAM_ROW_STALE: ANOMALY_ACTION_NEEDS_DETECT,
    ANOMALY_AGENT_RUNTIME_ERROR: ANOMALY_ACTION_RETRYABLE,
}


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


def ensure_async_message_file(harness_dir: Path) -> Path:
    msg_file = harness_dir / "ralph-msg.md"
    msg_file.parent.mkdir(parents=True, exist_ok=True)
    if not msg_file.exists():
        msg_file.write_text("", encoding="utf-8")
    return msg_file


def split_async_message_segments(text: str) -> List[str]:
    return MESSAGE_SEPARATOR_RE.split(text)


def join_async_message_segments(segments: List[str]) -> str:
    normalized = [segment.strip("\n") for segment in segments if segment.strip()]
    if not normalized:
        return ""
    return "\n\n---\n\n".join(normalized) + "\n"


def render_consumed_message_entry(
    message_text: str,
    pulse_payload: Dict[str, Any],
    prompt_files: List[Path],
) -> str:
    consumed_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    pulse_status = str(pulse_payload.get("status", "")).strip() or "unknown"
    next_row_id = str(pulse_payload.get("next_row_id", "")).strip() or "-"
    next_row_title = str(pulse_payload.get("next_row_title", "")).strip() or "-"
    prompt_targets = ", ".join(path.name for path in prompt_files) if prompt_files else "-"
    return (
        f"## Consumed At {consumed_at}\n"
        f"- pulse_status: {pulse_status}\n"
        f"- next_row_id: {next_row_id}\n"
        f"- next_row_title: {next_row_title}\n"
        f"- prompt_targets: {prompt_targets}\n"
        "\n"
        "### User Message\n"
        f"{message_text.strip()}\n"
    )


def consume_async_message(
    harness_dir: Path,
    pulse_payload: Dict[str, Any],
    prompt_files: List[Path],
) -> str:
    msg_file = ensure_async_message_file(harness_dir)
    raw = msg_file.read_text(encoding="utf-8")
    segments = split_async_message_segments(raw)
    if not segments:
        return ""

    first_non_empty = -1
    for index, segment in enumerate(segments):
        if segment.strip():
            first_non_empty = index
            break
    if first_non_empty < 0:
        return ""

    message_text = segments[first_non_empty].strip()
    remaining = segments[first_non_empty + 1 :]
    msg_file.write_text(join_async_message_segments(remaining), encoding="utf-8")

    consumed_file = harness_dir / "ralph-msg.consumed.md"
    consumed_entry = render_consumed_message_entry(message_text, pulse_payload, prompt_files).strip() + "\n"
    if consumed_file.exists():
        existing = consumed_file.read_text(encoding="utf-8")
    else:
        existing = ""
    if existing.strip():
        merged = f"{consumed_entry}\n---\n\n{existing.lstrip()}"
    else:
        merged = consumed_entry
    consumed_file.write_text(merged, encoding="utf-8")
    return message_text


def build_injected_prompt_content(prompt_file: Path, message_text: str) -> str:
    original = prompt_file.read_text(encoding="utf-8")
    return (
        "# Async Ralph User Message\n\n"
        "以下内容来自 `.bagakit/long-run/ralph-msg.md` 顶部留言，作为本轮 user messages 注入：\n\n"
        f"{message_text.strip()}\n\n"
        "---\n\n"
        f"{original}"
    )


def materialize_injected_prompt(harness_dir: Path, prompt_file: Path, message_text: str) -> Path:
    content = build_injected_prompt_content(prompt_file, message_text)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        delete=False,
        prefix=f".{prompt_file.stem}.ralph-msg.",
        suffix=".md",
        dir=str(harness_dir),
    ) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    return temp_path


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
6. 输出末尾必须携带 machine-readable outcome JSON（用于 evidence gate）。
7. 输出前做一次简短反思：计划是否可执行、是否遗漏高优先级风险、下一轮最合理入口是什么。

输出要求：
- 先给“新增/调整的 rows 摘要（按优先级）”
- 再给验证结果与下一条建议执行项
- 最后附上以下 outcome JSON 块：

{OUTCOME_START_MARKER}
{{
  "schema_version": "1",
  "pass": "endless_expand",
  "item_id": "none",
  "status": "done",
  "evidence": [
    {{"type": "plan", "name": "execution_table_updated", "result": "pass", "artifact": ".bagakit/long-run/bk-execution-table.json"}},
    {{"type": "reflection", "name": "endless_expand_self_review", "result": "pass", "artifact": ".bagakit/long-run/endless_expand_prompt.md"}}
  ],
  "anomaly_codes": [],
  "next_command": "bash .bagakit/long-run/check_and_resume.sh",
  "confidence": 0.70
}}
{OUTCOME_END_MARKER}
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
    if payload.get("next_row_status"):
        print(f"next_row_status: {payload.get('next_row_status')}")
    if payload.get("selected_pass"):
        print(f"selected_pass: {payload.get('selected_pass')}")
    if payload.get("endless_prompt_file"):
        print(f"endless_prompt_file: {payload.get('endless_prompt_file')}")
    prompts = payload.get("executed_prompts")
    if isinstance(prompts, list) and prompts:
        print("executed_prompts:")
        for item in prompts:
            print(f"- {item}")
    if payload.get("consumed_user_message"):
        print("consumed_user_message: yes")
    if payload.get("consumed_file"):
        print(f"consumed_file: {payload.get('consumed_file')}")
    if payload.get("consumed_user_message_preview"):
        print(f"consumed_user_message_preview: {payload.get('consumed_user_message_preview')}")
    if payload.get("agent_command"):
        print(f"agent_command: {payload.get('agent_command')}")
    if payload.get("outcome_status"):
        print(f"outcome_status: {payload.get('outcome_status')}")
    anomaly_codes = payload.get("anomaly_codes")
    if isinstance(anomaly_codes, list) and anomaly_codes:
        print(f"anomaly_codes: {', '.join(str(code) for code in anomaly_codes)}")
    if payload.get("anomaly_action"):
        print(f"anomaly_action: {payload.get('anomaly_action')}")
    return int(payload.get("exit_code", 0))


def build_pulse_payload(project_root: Path, endless: bool) -> Dict[str, Any]:
    harness_dir = project_root / ".bagakit" / "long-run"
    ensure_async_message_file(harness_dir)
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
        "next_row_status": "",
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
                "next_row_status": str(next_row.get("status", "")).strip(),
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


def prompt_files_for_pulse(payload: Dict[str, Any], harness_dir: Path) -> Tuple[List[Path], str]:
    status = str(payload.get("status", "")).strip()
    gen_dir = harness_dir / ".gen"
    if status == "actionable":
        next_row_status = str(payload.get("next_row_status", "")).strip()
        if next_row_status == "todo":
            return [gen_dir / "initializer_prompt.md"], "initializer"
        if next_row_status == "in_progress":
            return [gen_dir / "coding_prompt.md"], "coding"
        return [], ""
    if status == "endless_prompt_ready":
        prompt_file = str(payload.get("endless_prompt_file", "")).strip()
        if prompt_file:
            return [Path(prompt_file).resolve()], "endless_expand"
    return [], ""


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


def parse_bool_env(name: str) -> bool:
    value = os.environ.get(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def anomaly_action_for_codes(codes: List[str]) -> str:
    normalized = sorted({str(code).strip() for code in codes if str(code).strip()})
    if not normalized:
        return ""

    actions = {ANOMALY_ACTION_MAP.get(code, "") for code in normalized}
    actions.discard("")
    if ANOMALY_ACTION_NEEDS_DETECT in actions:
        return ANOMALY_ACTION_NEEDS_DETECT
    if ANOMALY_ACTION_BLOCKED_STOP in actions:
        return ANOMALY_ACTION_BLOCKED_STOP
    if ANOMALY_ACTION_RETRYABLE in actions:
        return ANOMALY_ACTION_RETRYABLE
    return ""


def run_agent_prompt(project_root: Path, command_template: str, prompt_file: Path, verbose: bool = False) -> Dict[str, Any]:
    command = render_agent_command(command_template, prompt_file, project_root)
    if verbose:
        print(f"agent_command: {command}")
    proc = subprocess.run(
        ["bash", "-lc", command],
        cwd=project_root,
        text=True,
        capture_output=True,
    )
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    return {
        "returncode": int(proc.returncode),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "command": command,
    }


def probe_writable_file(target_dir: Path, prefix: str) -> tuple[bool, str]:
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # noqa: BLE001
        return False, f"mkdir_failed:{target_dir}:{exc}"

    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=str(target_dir), prefix=prefix, delete=True) as h:
            h.write("ok")
            h.flush()
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        return False, f"write_failed:{target_dir}:{exc}"


def run_preflight(project_root: Path) -> Dict[str, Any]:
    checks: List[Dict[str, str]] = []
    anomaly_codes: List[str] = []

    workspace_ok, workspace_detail = probe_writable_file(project_root, ".bagakit-long-run.workspace.")
    checks.append({"name": "workspace_writable", "result": "pass" if workspace_ok else "fail", "detail": workspace_detail})
    if not workspace_ok:
        anomaly_codes.append(ANOMALY_ENV_NO_WRITE)

    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix="bagakit-long-run.tmp.", delete=True) as h:
            h.write("ok")
            h.flush()
        tmp_ok, tmp_detail = True, "ok"
    except Exception as exc:  # noqa: BLE001
        tmp_ok, tmp_detail = False, str(exc)
    checks.append({"name": "tmp_writable", "result": "pass" if tmp_ok else "fail", "detail": tmp_detail})
    if not tmp_ok:
        anomaly_codes.append(ANOMALY_ENV_NO_TMP)

    cache_root_env = os.environ.get("BAGAKIT_LONG_RUN_CACHE_DIR", "").strip()
    cache_root = Path(cache_root_env) if cache_root_env else Path(os.environ.get("XDG_CACHE_HOME", "").strip() or (Path.home() / ".cache"))
    cache_dir = cache_root / "bagakit-long-run"
    cache_ok, cache_detail = probe_writable_file(cache_dir, "preflight-cache.")
    checks.append({"name": "cache_writable", "result": "pass" if cache_ok else "fail", "detail": cache_detail})
    if not cache_ok:
        anomaly_codes.append(ANOMALY_ENV_NO_WRITE)

    ok = workspace_ok and tmp_ok and cache_ok
    return {
        "ok": ok,
        "checks": checks,
        "anomaly_codes": sorted(set(anomaly_codes)),
    }


def extract_outcome_block(text: str) -> tuple[str, str]:
    start = text.find(OUTCOME_START_MARKER)
    end = text.find(OUTCOME_END_MARKER)
    if start < 0 or end < 0 or end <= start:
        return "", "missing outcome markers"
    block = text[start + len(OUTCOME_START_MARKER) : end].strip()
    if not block:
        return "", "empty outcome block"

    if block.startswith("```"):
        lines = block.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        block = "\n".join(lines).strip()
    return block, ""


def load_outcome_schema() -> Dict[str, Any]:
    schema_file = Path(__file__).resolve().parents[1] / "references" / "schema" / "long-run-outcome.schema.json"
    if not schema_file.exists():
        return {}
    try:
        schema = json.loads(schema_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return schema if isinstance(schema, dict) else {}


def parse_outcome(stdout: str, stderr: str) -> tuple[Dict[str, Any], str, List[str]]:
    combined = f"{stdout}\n{stderr}" if stderr else stdout
    block, err = extract_outcome_block(combined)
    if err:
        return {}, err, [ANOMALY_PROMPT_CONTRACT_MISSING]

    try:
        outcome = json.loads(block)
    except json.JSONDecodeError as exc:
        return {}, f"invalid outcome json: {exc}", [ANOMALY_OUTCOME_SCHEMA_INVALID]

    if not isinstance(outcome, dict):
        return {}, "outcome must be object", [ANOMALY_OUTCOME_SCHEMA_INVALID]
    return outcome, "", []


def validate_outcome(
    outcome: Dict[str, Any],
    expected_pass: str,
    expected_item_id: str,
    schema: Dict[str, Any],
) -> tuple[List[str], List[str]]:
    errors: List[str] = []
    anomalies: List[str] = []

    if not schema:
        errors.append("outcome schema missing")
        anomalies.append(ANOMALY_OUTCOME_SCHEMA_INVALID)
        return errors, anomalies

    required = schema.get("required")
    if not isinstance(required, list):
        required = ["schema_version", "pass", "item_id", "status", "evidence", "anomaly_codes", "next_command", "confidence"]

    for key in required:
        if str(key) not in outcome:
            errors.append(f"missing field: {key}")

    pass_value = str(outcome.get("pass", "")).strip()
    if pass_value not in OUTCOME_PASS_ALLOWED:
        errors.append(f"invalid pass: {pass_value}")
    elif expected_pass and pass_value != expected_pass:
        errors.append(f"unexpected pass: expected={expected_pass} got={pass_value}")

    status = str(outcome.get("status", "")).strip()
    if status not in OUTCOME_STATUS_ALLOWED:
        errors.append(f"invalid status: {status}")

    item_id = str(outcome.get("item_id", "")).strip()
    if expected_item_id and item_id != expected_item_id:
        errors.append(f"unexpected item_id: expected={expected_item_id} got={item_id}")

    evidence = outcome.get("evidence")
    if not isinstance(evidence, list):
        errors.append("evidence must be list")
        evidence = []
    else:
        for idx, item in enumerate(evidence):
            if not isinstance(item, dict):
                errors.append(f"evidence[{idx}] must be object")
                continue
            for field in ("type", "name", "result"):
                if not str(item.get(field, "")).strip():
                    errors.append(f"evidence[{idx}] missing field: {field}")

    anomaly_codes = outcome.get("anomaly_codes")
    if not isinstance(anomaly_codes, list):
        errors.append("anomaly_codes must be list")

    next_command = str(outcome.get("next_command", "")).strip()
    if not next_command:
        errors.append("next_command must be non-empty")

    confidence = outcome.get("confidence")
    if isinstance(confidence, bool):
        errors.append("confidence must be number")
    else:
        try:
            conf = float(confidence)
            if conf < 0.0 or conf > 1.0:
                errors.append("confidence must be within [0,1]")
        except (TypeError, ValueError):
            errors.append("confidence must be number")

    if errors:
        anomalies.append(ANOMALY_OUTCOME_SCHEMA_INVALID)
        return errors, sorted(set(anomalies))

    has_passed_evidence = False
    for item in evidence:
        if not isinstance(item, dict):
            continue
        result = str(item.get("result", "")).strip().lower()
        if result in OUTCOME_POSITIVE_RESULTS:
            has_passed_evidence = True
            break

    if status in {"done", "in_progress"} and not has_passed_evidence:
        errors.append("status done/in_progress requires at least one passing evidence result")
        anomalies.append(ANOMALY_ACCEPTANCE_FAILED)

    if status in {"blocked", "retry", "no_action"}:
        anomalies.append(ANOMALY_ACCEPTANCE_FAILED)

    return errors, sorted(set(anomalies))


def cmd_preflight(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    payload = run_preflight(project_root)
    anomaly_codes = payload.get("anomaly_codes", [])
    out = {
        "status": "ok" if payload.get("ok") else "failed",
        "ok": bool(payload.get("ok")),
        "checks": payload.get("checks", []),
        "anomaly_codes": anomaly_codes,
        "anomaly_action": anomaly_action_for_codes(anomaly_codes),
        "exit_code": 0 if payload.get("ok") else 1,
    }
    return emit(out, args.json)


def cmd_run(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    harness_dir = project_root / ".bagakit" / "long-run"
    profile_file = harness_dir / "project-profile.json"

    payload = build_pulse_payload(project_root, args.endless)
    pulse_status = str(payload.get("status", "")).strip()
    legacy_rc_only = parse_bool_env(LEGACY_RC_ONLY_ENV)

    result: Dict[str, Any] = {
        "status": "run_unknown",
        "reason": "",
        "pulse_status": pulse_status,
        "detected_cli": payload.get("detected_cli", ""),
        "next_row_id": payload.get("next_row_id", ""),
        "next_row_title": payload.get("next_row_title", ""),
        "next_row_status": payload.get("next_row_status", ""),
        "selected_pass": "",
        "executed_prompts": [],
        "agent_command": "",
        "consumed_user_message": False,
        "consumed_user_message_preview": "",
        "consumed_file": "",
        "outcome_status": "",
        "anomaly_codes": [],
        "anomaly_action": "",
        "legacy_rc_only": legacy_rc_only,
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

    prompt_files, selected_pass = prompt_files_for_pulse(payload, harness_dir)
    result["selected_pass"] = selected_pass
    if pulse_status == "actionable" and not prompt_files:
        anomaly_codes = [ANOMALY_UPSTREAM_ROW_STALE]
        result.update(
            {
                "status": "run_failed",
                "reason": "upstream_row_stale_or_unsupported_status",
                "anomaly_codes": anomaly_codes,
                "anomaly_action": anomaly_action_for_codes(anomaly_codes),
                "exit_code": 1,
            }
        )
        return emit(result, args.json)

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
            anomaly_codes = [ANOMALY_PROMPT_CONTRACT_MISSING]
            result.update(
                {
                    "status": "run_failed",
                    "reason": f"missing_prompt:{prompt_file}",
                    "anomaly_codes": anomaly_codes,
                    "anomaly_action": anomaly_action_for_codes(anomaly_codes),
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

    preflight = run_preflight(project_root)
    if not preflight.get("ok"):
        anomaly_codes = [str(code) for code in preflight.get("anomaly_codes", []) if str(code).strip()]
        result.update(
            {
                "status": "run_failed",
                "reason": "preflight_failed",
                "preflight": preflight,
                "anomaly_codes": anomaly_codes,
                "anomaly_action": anomaly_action_for_codes(anomaly_codes),
                "exit_code": 1,
            }
        )
        return emit(result, args.json)

    async_message = consume_async_message(harness_dir, payload, prompt_files)
    dispatch_prompt_files: List[Path] = list(prompt_files)
    temp_prompt_files: List[Path] = []
    if async_message:
        dispatch_prompt_files = []
        for prompt_file in prompt_files:
            injected = materialize_injected_prompt(harness_dir, prompt_file, async_message)
            dispatch_prompt_files.append(injected)
            temp_prompt_files.append(injected)
        preview = async_message.strip().replace("\n", " ")
        if len(preview) > 120:
            preview = preview[:117] + "..."
        result.update(
            {
                "consumed_user_message": True,
                "consumed_user_message_preview": preview,
                "consumed_file": str(harness_dir / "ralph-msg.consumed.md"),
            }
        )

    outcome_schema = load_outcome_schema()
    try:
        for prompt_file, dispatch_prompt in zip(prompt_files, dispatch_prompt_files):
            run_info = run_agent_prompt(project_root, agent_command, dispatch_prompt, verbose=args.verbose)
            rc = int(run_info.get("returncode", 1))
            result["executed_prompts"].append(str(prompt_file))

            if rc != 0:
                anomaly_codes = [ANOMALY_AGENT_RUNTIME_ERROR]
                result.update(
                    {
                        "status": "run_failed",
                        "reason": f"agent_command_failed:{prompt_file}",
                        "anomaly_codes": anomaly_codes,
                        "anomaly_action": anomaly_action_for_codes(anomaly_codes),
                        "exit_code": rc,
                    }
                )
                return emit(result, args.json)

            if legacy_rc_only:
                continue

            outcome, parse_error, parse_anomalies = parse_outcome(
                str(run_info.get("stdout", "")),
                str(run_info.get("stderr", "")),
            )
            if parse_error:
                anomaly_codes = [str(code) for code in parse_anomalies if str(code).strip()]
                result.update(
                    {
                        "status": "run_failed",
                        "reason": f"outcome_parse_failed:{parse_error}",
                        "anomaly_codes": anomaly_codes,
                        "anomaly_action": anomaly_action_for_codes(anomaly_codes),
                        "exit_code": 3,
                    }
                )
                return emit(result, args.json)

            expected_item_id = str(payload.get("next_row_id", "")).strip()
            if selected_pass == "endless_expand":
                expected_item_id = "none"

            validation_errors, validation_anomalies = validate_outcome(
                outcome=outcome,
                expected_pass=selected_pass,
                expected_item_id=expected_item_id,
                schema=outcome_schema,
            )
            if validation_errors:
                anomaly_codes = [str(code) for code in validation_anomalies if str(code).strip()]
                result.update(
                    {
                        "status": "run_failed",
                        "reason": "outcome_validation_failed:" + " | ".join(validation_errors),
                        "anomaly_codes": anomaly_codes,
                        "anomaly_action": anomaly_action_for_codes(anomaly_codes),
                        "outcome": outcome,
                        "outcome_status": str(outcome.get("status", "")).strip(),
                        "exit_code": 3,
                    }
                )
                return emit(result, args.json)

            outcome_status = str(outcome.get("status", "")).strip()
            result["outcome"] = outcome
            result["outcome_status"] = outcome_status
            if outcome_status in {"blocked", "retry", "no_action"}:
                anomaly_codes = [ANOMALY_ACCEPTANCE_FAILED]
                result.update(
                    {
                        "status": "run_failed",
                        "reason": f"outcome_status_non_success:{outcome_status}",
                        "anomaly_codes": anomaly_codes,
                        "anomaly_action": anomaly_action_for_codes(anomaly_codes),
                        "exit_code": 3,
                    }
                )
                return emit(result, args.json)
    finally:
        for temp_file in temp_prompt_files:
            try:
                temp_file.unlink()
            except FileNotFoundError:
                pass

    result.update(
        {
            "status": "run_completed",
            "reason": "agent_prompt_executed_with_evidence_gate" if not legacy_rc_only else "agent_prompt_executed_legacy_rc_only",
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

    p_preflight = sub.add_parser("preflight", help="run environment preflight checks before dispatch")
    p_preflight.add_argument("project_root")
    p_preflight.add_argument("--json", action="store_true")
    p_preflight.set_defaults(func=cmd_preflight)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
