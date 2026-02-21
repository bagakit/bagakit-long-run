#!/usr/bin/env python3
"""Heartbeat + flash ideas + local scheduling for bagakit-long-run."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import fcntl
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
EVERY_SPEC_RE = re.compile(r"^(?P<num>\d+)(?P<unit>[mh])$")
CRON_SPEC_RE = re.compile(r"^\s*\S+\s+\S+\s+\S+\s+\S+\s+\S+\s*$")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def local_now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def iso_to_dt(value: str) -> dt.datetime | None:
    raw = value.strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return dt.datetime.fromisoformat(raw)
    except ValueError:
        return None


def safe_tail(text: str, limit: int = 400) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def slugify(value: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    out = re.sub(r"-+", "-", out).strip("-")
    return out or "item"


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return copy.deepcopy(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return copy.deepcopy(default)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            deep_merge(dst[key], value)
        else:
            dst[key] = value
    return dst


def parse_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise SystemExit(f"error: invalid boolean value: {value}")


def default_config() -> Dict[str, Any]:
    return {
        "version": 1,
        "enabled": True,
        "interval_minutes": 30,
        "active_windows": [
            {
                "days": DAY_NAMES,
                "start": "08:00",
                "end": "22:00",
            }
        ],
        "timezone": "local",
        "autonomy": {
            "mode": "full_auto_execute",
            "run_context": "main",
        },
        "guardrails": {
            "allowlist_prefixes": [
                "bash .bagakit/long-run/check_and_resume.sh",
                "bash \"$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/validate-long-run.sh\" .",
                "bash \"$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-doctor.sh\" .",
                "python3 \"$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-execution.py\"",
                "python3 \"$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-features.py\"",
                "python3 \"$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-heartbeat.py\"",
            ],
            "command_timeout_seconds": 900,
            "max_commands_per_tick": 4,
            "require_git_clean": True,
        },
        "delivery": {
            "mode": "announce",
            "webhook_url": "",
        },
        "inbox": {
            "prefer_living_docs": True,
        },
        "idle": {
            "flash_ideas": {
                "enabled": True,
                "count": 5,
                "auto_pick": "top_1",
            }
        },
    }


def default_schedules() -> Dict[str, Any]:
    return {"version": 1, "schedules": []}


def default_state() -> Dict[str, Any]:
    return {
        "version": 1,
        "last_tick_at": "",
        "last_success_at": "",
        "recent_executions": [],
        "cooldown_minutes": 120,
    }


def default_queue() -> Dict[str, Any]:
    return {
        "version": 1,
        "items": [],
    }


def heartbeat_paths(project_root: Path) -> Dict[str, Path]:
    harness = project_root / ".bagakit" / "long-run"
    inbox = harness / "inbox"
    return {
        "project_root": project_root,
        "harness": harness,
        "config": harness / "heartbeat.config.json",
        "schedules": harness / "heartbeat-schedules.json",
        "state": harness / "heartbeat.state.json",
        "lock": harness / "heartbeat.lock",
        "next_action": harness / "next-action.json",
        "execution_table": harness / "bk-execution-table.json",
        "feature_list": harness / "feature-list.json",
        "handoff": harness / "bk-execution-handoff.md",
        "queue": inbox / "queue.json",
        "history_dir": inbox / "history",
        "flash_dir": inbox / "flash-ideas",
        "inbox_readme": inbox / "README.md",
        "schedules_generated": harness / "schedules" / "generated",
    }


def ensure_files(project_root: Path, skill_root: Path) -> Dict[str, Path]:
    paths = heartbeat_paths(project_root)
    paths["harness"].mkdir(parents=True, exist_ok=True)
    paths["history_dir"].mkdir(parents=True, exist_ok=True)
    paths["flash_dir"].mkdir(parents=True, exist_ok=True)
    paths["schedules_generated"].mkdir(parents=True, exist_ok=True)

    tpl = skill_root / "references" / "tpl"
    config_template = tpl / "heartbeat-config-template.json"
    schedules_template = tpl / "heartbeat-schedules-template.json"
    inbox_template = tpl / "heartbeat-inbox-readme-template.md"

    if config_template.exists() and not paths["config"].exists():
        paths["config"].write_text(config_template.read_text(encoding="utf-8"), encoding="utf-8")
    if schedules_template.exists() and not paths["schedules"].exists():
        paths["schedules"].write_text(schedules_template.read_text(encoding="utf-8"), encoding="utf-8")
    if not paths["state"].exists():
        write_json(paths["state"], default_state())
    if not paths["queue"].exists():
        write_json(paths["queue"], default_queue())
    if inbox_template.exists() and not paths["inbox_readme"].exists():
        paths["inbox_readme"].write_text(inbox_template.read_text(encoding="utf-8"), encoding="utf-8")

    return paths


def load_config(paths: Dict[str, Path]) -> Dict[str, Any]:
    cfg = default_config()
    user_cfg = read_json(paths["config"], {})
    if isinstance(user_cfg, dict):
        deep_merge(cfg, user_cfg)
    return cfg


def load_state(paths: Dict[str, Path]) -> Dict[str, Any]:
    state = default_state()
    raw = read_json(paths["state"], {})
    if isinstance(raw, dict):
        deep_merge(state, raw)
    return state


def load_queue(paths: Dict[str, Path]) -> Dict[str, Any]:
    queue = default_queue()
    raw = read_json(paths["queue"], {})
    if isinstance(raw, dict):
        deep_merge(queue, raw)
    if not isinstance(queue.get("items"), list):
        queue["items"] = []
    return queue


def load_schedules(paths: Dict[str, Path]) -> Dict[str, Any]:
    schedules = default_schedules()
    raw = read_json(paths["schedules"], {})
    if isinstance(raw, dict):
        deep_merge(schedules, raw)
    if not isinstance(schedules.get("schedules"), list):
        schedules["schedules"] = []
    return schedules


def valid_time_hhmm(value: str) -> bool:
    return bool(re.match(r"^([01]\d|2[0-3]):[0-5]\d$", value))


def in_active_window(cfg: Dict[str, Any], now_local: dt.datetime) -> bool:
    windows = cfg.get("active_windows", [])
    if not isinstance(windows, list) or not windows:
        return True
    day = DAY_NAMES[now_local.weekday()]
    now_text = now_local.strftime("%H:%M")

    for item in windows:
        if not isinstance(item, dict):
            continue
        days = item.get("days", [])
        start = str(item.get("start", "")).strip()
        end = str(item.get("end", "")).strip()
        if not isinstance(days, list) or day not in [str(d) for d in days]:
            continue
        if not valid_time_hhmm(start) or not valid_time_hhmm(end):
            continue
        if start <= end:
            if start <= now_text < end:
                return True
        else:
            if now_text >= start or now_text < end:
                return True
    return False


def validate_every_spec(spec: str) -> int | None:
    match = EVERY_SPEC_RE.match(spec.strip())
    if not match:
        return None
    num = int(match.group("num"))
    unit = match.group("unit")
    if num <= 0:
        return None
    return num * 60 if unit == "m" else num * 3600


def validate_at_spec(spec: str) -> bool:
    return iso_to_dt(spec) is not None


def validate_cron_spec(spec: str) -> bool:
    return bool(CRON_SPEC_RE.match(spec))


def validate_config_payload(cfg: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    if not isinstance(cfg.get("enabled"), bool):
        errors.append("enabled must be boolean")

    interval = cfg.get("interval_minutes")
    if not isinstance(interval, int) or interval <= 0:
        errors.append("interval_minutes must be a positive integer")

    windows = cfg.get("active_windows")
    if not isinstance(windows, list) or not windows:
        errors.append("active_windows must be a non-empty list")
    else:
        for idx, item in enumerate(windows):
            if not isinstance(item, dict):
                errors.append(f"active_windows[{idx}] must be an object")
                continue
            days = item.get("days")
            if not isinstance(days, list) or not days:
                errors.append(f"active_windows[{idx}].days must be non-empty list")
            else:
                for day in days:
                    if str(day) not in DAY_NAMES:
                        errors.append(f"active_windows[{idx}].days includes unknown day: {day}")
            start = str(item.get("start", ""))
            end = str(item.get("end", ""))
            if not valid_time_hhmm(start):
                errors.append(f"active_windows[{idx}].start must be HH:MM")
            if not valid_time_hhmm(end):
                errors.append(f"active_windows[{idx}].end must be HH:MM")

    if str(cfg.get("timezone", "")).strip() != "local":
        errors.append("timezone must be 'local' in standalone mode")

    autonomy = cfg.get("autonomy", {})
    if not isinstance(autonomy, dict):
        errors.append("autonomy must be object")
    else:
        if str(autonomy.get("mode", "")) != "full_auto_execute":
            errors.append("autonomy.mode must be 'full_auto_execute'")
        if str(autonomy.get("run_context", "")) not in {"main", "isolated"}:
            errors.append("autonomy.run_context must be one of: main, isolated")

    guardrails = cfg.get("guardrails", {})
    if not isinstance(guardrails, dict):
        errors.append("guardrails must be object")
    else:
        prefixes = guardrails.get("allowlist_prefixes")
        if not isinstance(prefixes, list) or not prefixes or not all(isinstance(v, str) and v.strip() for v in prefixes):
            errors.append("guardrails.allowlist_prefixes must be non-empty string list")
        timeout = guardrails.get("command_timeout_seconds")
        if not isinstance(timeout, int) or timeout <= 0:
            errors.append("guardrails.command_timeout_seconds must be positive int")
        max_cmd = guardrails.get("max_commands_per_tick")
        if not isinstance(max_cmd, int) or max_cmd <= 0:
            errors.append("guardrails.max_commands_per_tick must be positive int")
        if not isinstance(guardrails.get("require_git_clean"), bool):
            errors.append("guardrails.require_git_clean must be boolean")

    delivery = cfg.get("delivery", {})
    if not isinstance(delivery, dict):
        errors.append("delivery must be object")
    else:
        mode = str(delivery.get("mode", ""))
        if mode not in {"announce", "webhook", "none"}:
            errors.append("delivery.mode must be one of: announce, webhook, none")
        if mode == "webhook" and not str(delivery.get("webhook_url", "")).strip():
            errors.append("delivery.webhook_url is required when delivery.mode=webhook")

    inbox = cfg.get("inbox", {})
    if not isinstance(inbox, dict) or not isinstance(inbox.get("prefer_living_docs"), bool):
        errors.append("inbox.prefer_living_docs must be boolean")

    idle = cfg.get("idle", {})
    if not isinstance(idle, dict):
        errors.append("idle must be object")
    else:
        flash = idle.get("flash_ideas", {})
        if not isinstance(flash, dict):
            errors.append("idle.flash_ideas must be object")
        else:
            if not isinstance(flash.get("enabled"), bool):
                errors.append("idle.flash_ideas.enabled must be boolean")
            count = flash.get("count")
            if not isinstance(count, int) or count < 3 or count > 5:
                errors.append("idle.flash_ideas.count must be integer in [3, 5]")
            if str(flash.get("auto_pick", "")) != "top_1":
                errors.append("idle.flash_ideas.auto_pick must be 'top_1'")

    return errors


def validate_schedules_payload(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if parse_int(payload.get("version"), 0) != 1:
        errors.append("version must be 1")
    schedules = payload.get("schedules")
    if not isinstance(schedules, list):
        errors.append("schedules must be list")
        return errors

    seen: set[str] = set()
    for idx, item in enumerate(schedules):
        prefix = f"schedules[{idx}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be object")
            continue
        sid = str(item.get("id", "")).strip()
        if not sid:
            errors.append(f"{prefix}.id is required")
        elif sid in seen:
            errors.append(f"duplicate schedule id: {sid}")
        else:
            seen.add(sid)

        kind = str(item.get("kind", "")).strip()
        spec = str(item.get("spec", "")).strip()
        if kind not in {"at", "every", "cron"}:
            errors.append(f"{prefix}.kind must be at|every|cron")
        elif not spec:
            errors.append(f"{prefix}.spec is required")
        elif kind == "at" and not validate_at_spec(spec):
            errors.append(f"{prefix}.spec invalid at ISO-8601: {spec}")
        elif kind == "every" and validate_every_spec(spec) is None:
            errors.append(f"{prefix}.spec invalid every spec (example: 30m, 2h): {spec}")
        elif kind == "cron" and not validate_cron_spec(spec):
            errors.append(f"{prefix}.spec invalid cron expression: {spec}")

        run_context = str(item.get("run_context", "")).strip()
        if run_context not in {"main", "isolated"}:
            errors.append(f"{prefix}.run_context must be main|isolated")

        delivery = str(item.get("delivery", "")).strip()
        if delivery not in {"announce", "webhook", "none"}:
            errors.append(f"{prefix}.delivery must be announce|webhook|none")

        if not isinstance(item.get("enabled"), bool):
            errors.append(f"{prefix}.enabled must be boolean")

    return errors


def parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def is_git_repo(project_root: Path) -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=project_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return proc.returncode == 0


def git_is_clean(project_root: Path) -> bool:
    if not is_git_repo(project_root):
        return True
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.returncode == 0 and not proc.stdout.strip()


def command_env(skill_root: Path, run_context: str, delivery_override: str | None = None) -> Dict[str, str]:
    env = os.environ.copy()
    env["BAGAKIT_LONG_RUN_SKILL_DIR"] = str(skill_root)
    env["BAGAKIT_LONG_RUN_RUN_CONTEXT"] = run_context
    if delivery_override:
        env["BAGAKIT_LONG_RUN_DELIVERY_MODE"] = delivery_override
    return env


def run_shell_command(
    command: str,
    project_root: Path,
    env: Dict[str, str],
    timeout_seconds: int,
) -> Dict[str, Any]:
    started = time.time()
    try:
        proc = subprocess.run(
            command,
            cwd=project_root,
            shell=True,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
        return {
            "command": command,
            "returncode": proc.returncode,
            "duration_seconds": round(time.time() - started, 3),
            "stdout_tail": safe_tail(proc.stdout),
            "stderr_tail": safe_tail(proc.stderr),
            "timeout": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": 124,
            "duration_seconds": round(time.time() - started, 3),
            "stdout_tail": safe_tail(exc.stdout or ""),
            "stderr_tail": safe_tail(exc.stderr or ""),
            "timeout": True,
        }


def cmd_check_resume() -> str:
    return "bash .bagakit/long-run/check_and_resume.sh"


def cmd_validate() -> str:
    return 'bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/validate-long-run.sh" .'


def cmd_doctor() -> str:
    return 'bash "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-doctor.sh" .'


def cmd_plan_top(limit: int = 8) -> str:
    return f'python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-execution.py" plan . --limit {limit}'


def cmd_guide_row(row_id: str) -> str:
    return (
        'python3 "$BAGAKIT_LONG_RUN_SKILL_DIR/scripts/long-run-execution.py" '
        f"guide . --row-id {shlex.quote(row_id)}"
    )


def load_execution_rows(project_root: Path, skill_root: Path, table_path: Path, run_context: str) -> List[Dict[str, Any]]:
    env = command_env(skill_root, run_context)
    proc = subprocess.run(
        [
            "python3",
            str(skill_root / "scripts" / "long-run-execution.py"),
            "plan",
            str(project_root),
            "--table",
            str(table_path),
            "--json",
        ],
        cwd=project_root,
        env=env,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        return []
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def load_feature_doc(feature_file: Path) -> Dict[str, Any]:
    payload = read_json(feature_file, {})
    return payload if isinstance(payload, dict) else {}


def build_flash_ideas(
    project_root: Path,
    state: Dict[str, Any],
    feature_doc: Dict[str, Any],
    rows: List[Dict[str, Any]],
    count: int,
) -> List[Dict[str, Any]]:
    features = feature_doc.get("features", [])
    if not isinstance(features, list):
        features = []
    feature_items = [f for f in features if isinstance(f, dict)]

    blocked_features = [f for f in feature_items if str(f.get("status")) == "blocked"]
    todo_features = [f for f in feature_items if str(f.get("status")) == "todo"]
    project_goal = str(feature_doc.get("project", {}).get("goal", "")).strip() if isinstance(feature_doc.get("project"), dict) else ""

    recent = state.get("recent_executions", [])
    if not isinstance(recent, list):
        recent = []
    fail_count = sum(1 for item in recent[-12:] if isinstance(item, dict) and str(item.get("outcome", "")).startswith("failed"))

    actionable_rows = [r for r in rows if str(r.get("status")) in {"todo", "in_progress"}]
    top_row = actionable_rows[0] if actionable_rows else None
    top_row_id = str(top_row.get("id", "")).strip() if isinstance(top_row, dict) else ""

    ideas: List[Dict[str, Any]] = []

    ideas.append(
        {
            "id": "history-recovery",
            "category": "history",
            "title": "Recover unfinished or degraded execution flow",
            "why": "Use recent failures/blocked history to restore deterministic progress.",
            "score": 60 + min(20, fail_count * 4) + min(20, len(blocked_features) * 3),
            "commands": [cmd_doctor(), cmd_check_resume()],
            "evidence": [f"recent_failures={fail_count}", f"blocked_features={len(blocked_features)}"],
        }
    )

    if top_row_id:
        ideas.append(
            {
                "id": "medium-interest-direction",
                "category": "medium_interest",
                "title": "Push one medium-term actionable row",
                "why": "Advance current actionable work with explicit guide + resume flow.",
                "score": 58 + min(20, len(todo_features) * 2),
                "commands": [cmd_guide_row(top_row_id), cmd_check_resume()],
                "evidence": [f"top_row={top_row_id}", f"todo_features={len(todo_features)}"],
            }
        )
    else:
        ideas.append(
            {
                "id": "medium-interest-direction",
                "category": "medium_interest",
                "title": "Refresh medium-term plan from execution table",
                "why": "No actionable row currently selected; re-plan from current table signals.",
                "score": 52,
                "commands": [cmd_plan_top(8), cmd_check_resume()],
                "evidence": ["top_row=none"],
            }
        )

    ideas.append(
        {
            "id": "long-vision-alignment",
            "category": "long_vision",
            "title": "Re-align current work with long-term goal",
            "why": "Review today execution against declared project direction and next milestones.",
            "score": 55 + (8 if project_goal else 0),
            "commands": [cmd_plan_top(12), cmd_check_resume()],
            "evidence": [f"project_goal={'set' if project_goal else 'empty'}"],
        }
    )

    ideas.append(
        {
            "id": "workflow-improvement",
            "category": "work_quality",
            "title": "Improve current execution quality loop",
            "why": "Run validation + doctor to reduce hidden drift before next coding pass.",
            "score": 57 + min(15, fail_count * 3),
            "commands": [cmd_validate(), cmd_doctor()],
            "evidence": [f"recent_failures={fail_count}"],
        }
    )

    ideas.append(
        {
            "id": "directory-tidy",
            "category": "directory_tidy",
            "title": "Tidy long-run artifacts and summarize current directory state",
            "why": "Keep execution artifacts clear and reduce operational friction.",
            "score": 50 + (6 if len(feature_items) > 0 else 0),
            "commands": [cmd_plan_top(8), cmd_doctor()],
            "evidence": [f"features_total={len(feature_items)}"],
        }
    )

    ideas.sort(key=lambda item: (int(item.get("score", 0)), str(item.get("id", ""))), reverse=True)
    capped = ideas[: max(3, min(5, count))]

    now = utc_now()
    for idx, item in enumerate(capped, start=1):
        item["rank"] = idx
        item["generated_at"] = now

    return capped


def save_flash_ideas(paths: Dict[str, Path], ideas: List[Dict[str, Any]]) -> Path:
    stamp = local_now().strftime("%Y%m%d-%H%M%S")
    target = paths["flash_dir"] / f"flash-ideas-{stamp}.json"
    write_json(
        target,
        {
            "version": 1,
            "generated_at": utc_now(),
            "ideas": ideas,
        },
    )
    return target


def queue_pending_item(queue: Dict[str, Any]) -> Tuple[int, Dict[str, Any]] | Tuple[None, None]:
    items = queue.get("items", [])
    if not isinstance(items, list):
        return None, None
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        if str(item.get("status", "pending")) == "pending":
            return idx, item
    return None, None


def pick_next_row_item(
    next_action: Dict[str, Any],
    rows: List[Dict[str, Any]],
    state: Dict[str, Any],
) -> Dict[str, Any] | None:
    next_row = next_action.get("next_row")
    if not isinstance(next_row, dict):
        return None
    row_id = str(next_row.get("id", "")).strip()
    if not row_id:
        return None

    cooldown = parse_int(state.get("cooldown_minutes"), 120)
    now = dt.datetime.now(dt.timezone.utc)
    recent = state.get("recent_executions", [])
    if isinstance(recent, list):
        for item in reversed(recent[-80:]):
            if not isinstance(item, dict):
                continue
            if str(item.get("item_id", "")) != row_id:
                continue
            stamp = iso_to_dt(str(item.get("timestamp", "")))
            if stamp is None:
                continue
            delta_minutes = (now - stamp.astimezone(dt.timezone.utc)).total_seconds() / 60
            if delta_minutes < cooldown:
                return None
            break

    matched = next((row for row in rows if str(row.get("id", "")) == row_id), None)
    commands: List[str] = []
    if isinstance(matched, dict):
        raw_commands = matched.get("commands", [])
        if isinstance(raw_commands, list):
            commands = [str(c).strip() for c in raw_commands if str(c).strip()]

    if not commands:
        commands = [cmd_guide_row(row_id), cmd_check_resume()]

    return {
        "id": row_id,
        "title": str(next_row.get("title", "") or row_id),
        "source": "next_row",
        "kind": "execution_row",
        "commands": commands,
        "meta": {
            "system": str(next_row.get("system", "")),
            "source_ref": str(next_row.get("source_ref", "")),
        },
    }


def ensure_queue_item_shape(item: Dict[str, Any]) -> Dict[str, Any]:
    now = utc_now()
    commands = item.get("commands", [])
    if not isinstance(commands, list):
        commands = []
    return {
        "id": str(item.get("id", "")).strip() or f"item-{slugify(now)}",
        "title": str(item.get("title", "")).strip() or "heartbeat item",
        "kind": str(item.get("kind", "generic")).strip() or "generic",
        "source": str(item.get("source", "inbox")).strip() or "inbox",
        "status": str(item.get("status", "pending")).strip() or "pending",
        "commands": [str(c).strip() for c in commands if str(c).strip()],
        "created_at": str(item.get("created_at", now)),
        "updated_at": str(item.get("updated_at", now)),
        "meta": item.get("meta", {}) if isinstance(item.get("meta", {}), dict) else {},
    }


def queue_item_from_idea(idea: Dict[str, Any]) -> Dict[str, Any]:
    now = utc_now()
    return ensure_queue_item_shape(
        {
            "id": f"flash-{slugify(str(idea.get('id', 'idea')))}-{local_now().strftime('%H%M%S')}",
            "title": str(idea.get("title", "flash idea")),
            "kind": "flash_idea",
            "source": "flash",
            "status": "pending",
            "commands": idea.get("commands", []),
            "created_at": now,
            "updated_at": now,
            "meta": {
                "idea_id": str(idea.get("id", "")),
                "score": int(idea.get("score", 0)),
                "category": str(idea.get("category", "")),
            },
        }
    )


def append_history(paths: Dict[str, Path], payload: Dict[str, Any]) -> Path:
    date = local_now().strftime("%Y-%m-%d")
    history_path = paths["history_dir"] / f"{date}.jsonl"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return history_path


def mirror_living_docs(project_root: Path, cfg: Dict[str, Any], summary: Dict[str, Any]) -> Path | None:
    prefer = bool(cfg.get("inbox", {}).get("prefer_living_docs", True))
    if not prefer:
        return None
    target_dir = project_root / "docs" / ".bagakit" / "inbox"
    if not target_dir.is_dir():
        return None
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"notes-long-run-heartbeat-{local_now().strftime('%Y-%m-%d')}.md"

    if not target.exists():
        target.write_text(
            "# Long-Run Heartbeat Notes\n\n"
            "Machine-generated heartbeat run notes.\n",
            encoding="utf-8",
        )

    line = (
        f"\n## {summary.get('timestamp','')}\n"
        f"- status: {summary.get('status','')}\n"
        f"- source: {summary.get('source','none')}\n"
        f"- item: {summary.get('item_id','none')}\n"
        f"- reason: {summary.get('reason','')}\n"
    )
    with target.open("a", encoding="utf-8") as f:
        f.write(line)
    return target


def send_webhook(url: str, payload: Dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return f"webhook:{resp.status}"
    except (urllib.error.URLError, TimeoutError) as exc:
        return f"webhook_error:{exc}"


def execute_guarded_commands(
    commands: List[str],
    cfg: Dict[str, Any],
    project_root: Path,
    skill_root: Path,
    run_context: str,
    dry_run: bool,
) -> Dict[str, Any]:
    guard = cfg.get("guardrails", {}) if isinstance(cfg.get("guardrails", {}), dict) else {}
    allowlist = [str(v).strip() for v in guard.get("allowlist_prefixes", []) if str(v).strip()]
    timeout = parse_int(guard.get("command_timeout_seconds"), 900)
    max_commands = parse_int(guard.get("max_commands_per_tick"), 4)
    require_clean = bool(guard.get("require_git_clean", True))

    if require_clean and not git_is_clean(project_root):
        return {
            "ok": False,
            "reason": "git_dirty",
            "results": [],
        }

    if not allowlist:
        return {
            "ok": False,
            "reason": "allowlist_empty",
            "results": [],
        }

    selected = commands[:max_commands]
    results: List[Dict[str, Any]] = []

    if dry_run:
        for cmd in selected:
            results.append({"command": cmd, "returncode": 0, "duration_seconds": 0.0, "dry_run": True})
        return {
            "ok": True,
            "reason": "dry_run",
            "results": results,
        }

    env = command_env(skill_root, run_context)
    for cmd in selected:
        if not any(cmd.startswith(prefix) for prefix in allowlist):
            results.append({
                "command": cmd,
                "returncode": 126,
                "duration_seconds": 0.0,
                "stdout_tail": "",
                "stderr_tail": "guardrail: command prefix not allowlisted",
                "timeout": False,
            })
            return {
                "ok": False,
                "reason": "allowlist_reject",
                "results": results,
            }

        item = run_shell_command(cmd, project_root, env, timeout)
        results.append(item)
        if item.get("timeout"):
            return {
                "ok": False,
                "reason": "command_timeout",
                "results": results,
            }
        if parse_int(item.get("returncode"), 1) != 0:
            return {
                "ok": False,
                "reason": "command_failed",
                "results": results,
            }

    return {
        "ok": True,
        "reason": "commands_ok",
        "results": results,
    }


def tick_logic(project_root: Path, skill_root: Path, json_mode: bool, dry_run: bool) -> int:
    paths = ensure_files(project_root, skill_root)
    config = load_config(paths)
    state = load_state(paths)
    queue = load_queue(paths)

    cfg_errors = validate_config_payload(config)
    if cfg_errors:
        payload = {
            "timestamp": utc_now(),
            "status": "invalid_config",
            "errors": cfg_errors,
        }
        if json_mode:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print("error: invalid heartbeat config")
            for err in cfg_errors:
                print(f"- {err}")
        return 1

    now_text = utc_now()
    result: Dict[str, Any] = {
        "timestamp": now_text,
        "status": "unknown",
        "source": "none",
        "item_id": "none",
        "reason": "",
        "history_file": "",
        "mirror_file": "",
        "command_results": [],
        "selected_commands": [],
    }

    if not bool(config.get("enabled", True)):
        result.update({"status": "skipped", "reason": "disabled"})
        state["last_tick_at"] = now_text
        write_json(paths["state"], state)
        history_path = append_history(paths, result)
        result["history_file"] = str(history_path)
        if json_mode:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("heartbeat: skipped (disabled)")
        return 0

    now_local = local_now()
    if not in_active_window(config, now_local):
        result.update({"status": "skipped", "reason": "outside_active_window"})
        state["last_tick_at"] = now_text
        write_json(paths["state"], state)
        history_path = append_history(paths, result)
        result["history_file"] = str(history_path)
        if json_mode:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("heartbeat: skipped (outside active window)")
        return 0

    run_context = str(config.get("autonomy", {}).get("run_context", "main"))
    env_run_context = os.environ.get("BAGAKIT_LONG_RUN_RUN_CONTEXT", "").strip()
    if env_run_context in {"main", "isolated"}:
        run_context = env_run_context
    delivery_mode = str(config.get("delivery", {}).get("mode", "announce"))
    env_delivery = os.environ.get("BAGAKIT_LONG_RUN_DELIVERY_MODE", "").strip()
    if env_delivery:
        delivery_mode = env_delivery

    preflight = execute_guarded_commands(
        [cmd_check_resume()],
        config,
        project_root,
        skill_root,
        run_context,
        dry_run,
    )
    if not preflight["ok"]:
        result.update(
            {
                "status": "failed",
                "reason": f"preflight_{preflight['reason']}",
                "command_results": preflight["results"],
            }
        )
    else:
        next_action = read_json(paths["next_action"], {})
        if not isinstance(next_action, dict):
            next_action = {}

        rows = load_execution_rows(project_root, skill_root, paths["execution_table"], run_context)

        selected_item: Dict[str, Any] | None = None
        selected_idx: int | None = None

        pending_idx, pending = queue_pending_item(queue)
        if isinstance(pending_idx, int) and isinstance(pending, dict):
            selected_idx = pending_idx
            selected_item = ensure_queue_item_shape(pending)
            result["source"] = "inbox"

        if selected_item is None:
            next_item = pick_next_row_item(next_action, rows, state)
            if next_item:
                selected_item = next_item
                result["source"] = "next_row"

        if selected_item is None:
            idle = config.get("idle", {}).get("flash_ideas", {})
            if isinstance(idle, dict) and bool(idle.get("enabled", True)):
                feature_doc = load_feature_doc(paths["feature_list"])
                idea_count = parse_int(idle.get("count"), 5)
                ideas = build_flash_ideas(project_root, state, feature_doc, rows, idea_count)
                flash_file = save_flash_ideas(paths, ideas)
                result["flash_file"] = str(flash_file)
                if ideas and str(idle.get("auto_pick", "top_1")) == "top_1":
                    item = queue_item_from_idea(ideas[0])
                    queue.setdefault("items", [])
                    queue["items"].append(item)
                    selected_idx = len(queue["items"]) - 1
                    selected_item = item
                    result["source"] = "flash"

        if selected_item is None:
            result.update(
                {
                    "status": "skipped",
                    "reason": "no_actionable_item",
                }
            )
        else:
            selected_commands = [str(c).strip() for c in selected_item.get("commands", []) if str(c).strip()]
            result["item_id"] = str(selected_item.get("id", "none"))
            result["selected_commands"] = selected_commands
            if not selected_commands:
                exec_result = {"ok": False, "reason": "empty_commands", "results": []}
            else:
                exec_result = execute_guarded_commands(
                    selected_commands,
                    config,
                    project_root,
                    skill_root,
                    run_context,
                    dry_run,
                )

            result["command_results"] = exec_result["results"]
            if exec_result["ok"]:
                result.update({"status": "success", "reason": exec_result["reason"]})
                if isinstance(selected_idx, int):
                    queue["items"][selected_idx]["status"] = "done"
                    queue["items"][selected_idx]["updated_at"] = now_text
            else:
                result.update({"status": "failed", "reason": exec_result["reason"]})
                if isinstance(selected_idx, int):
                    queue["items"][selected_idx]["status"] = "failed"
                    queue["items"][selected_idx]["updated_at"] = now_text
                    queue["items"][selected_idx]["meta"] = queue["items"][selected_idx].get("meta", {})
                    queue["items"][selected_idx]["meta"]["last_error"] = exec_result["reason"]

    state["last_tick_at"] = now_text
    if result["status"] == "success":
        state["last_success_at"] = now_text
    recent = state.get("recent_executions", [])
    if not isinstance(recent, list):
        recent = []
    recent.append(
        {
            "timestamp": now_text,
            "item_id": result.get("item_id", "none"),
            "source": result.get("source", "none"),
            "outcome": result.get("status", "unknown"),
            "reason": result.get("reason", ""),
        }
    )
    state["recent_executions"] = recent[-120:]

    write_json(paths["queue"], queue)
    write_json(paths["state"], state)

    history_path = append_history(paths, result)
    result["history_file"] = str(history_path)

    mirror_path = mirror_living_docs(project_root, config, result)
    if mirror_path:
        result["mirror_file"] = str(mirror_path)

    if delivery_mode == "webhook":
        url = str(config.get("delivery", {}).get("webhook_url", "")).strip()
        if url:
            result["delivery"] = send_webhook(url, result)
        else:
            result["delivery"] = "webhook_skipped_missing_url"
    else:
        result["delivery"] = delivery_mode

    if json_mode:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            "heartbeat: status={status} source={source} item={item} reason={reason}".format(
                status=result.get("status", ""),
                source=result.get("source", ""),
                item=result.get("item_id", ""),
                reason=result.get("reason", ""),
            )
        )
        if result.get("history_file"):
            print(f"history: {result['history_file']}")
        if result.get("mirror_file"):
            print(f"mirror: {result['mirror_file']}")

    return 0 if result.get("status") in {"success", "skipped"} else 1


def cmd_tick(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    skill_root = Path(__file__).resolve().parents[1]
    paths = ensure_files(project_root, skill_root)

    paths["lock"].parent.mkdir(parents=True, exist_ok=True)
    with paths["lock"].open("w", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            payload = {
                "timestamp": utc_now(),
                "status": "locked",
                "reason": "another heartbeat tick is running",
            }
            if args.json:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                print("heartbeat: skipped (lock held by another process)")
            return 0
        return tick_logic(project_root, skill_root, args.json, args.dry_run)


def cmd_flash_ideas(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    skill_root = Path(__file__).resolve().parents[1]
    paths = ensure_files(project_root, skill_root)
    state = load_state(paths)
    rows = load_execution_rows(project_root, skill_root, paths["execution_table"], "main")
    feature_doc = load_feature_doc(paths["feature_list"])
    count = max(3, min(5, args.count))
    ideas = build_flash_ideas(project_root, state, feature_doc, rows, count)
    payload = {
        "generated_at": utc_now(),
        "count": len(ideas),
        "ideas": ideas,
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for idea in ideas:
            print(f"[{idea.get('rank')}] {idea.get('title')} score={idea.get('score')}")
            print(f"  why: {idea.get('why')}")
            for cmd in idea.get("commands", []):
                print(f"  cmd: {cmd}")
    return 0


def cmd_schedule_add(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    skill_root = Path(__file__).resolve().parents[1]
    paths = ensure_files(project_root, skill_root)

    schedules = load_schedules(paths)
    config = load_config(paths)

    kind = args.kind.strip()
    spec = args.spec.strip()
    if kind == "at" and not validate_at_spec(spec):
        raise SystemExit(f"error: invalid at spec (ISO-8601 expected): {spec}")
    if kind == "every" and validate_every_spec(spec) is None:
        raise SystemExit(f"error: invalid every spec (example: 30m, 2h): {spec}")
    if kind == "cron" and not validate_cron_spec(spec):
        raise SystemExit(f"error: invalid cron spec: {spec}")

    run_context = args.run_context.strip() if args.run_context else str(config.get("autonomy", {}).get("run_context", "main"))
    delivery = args.delivery.strip() if args.delivery else str(config.get("delivery", {}).get("mode", "announce"))
    if run_context not in {"main", "isolated"}:
        raise SystemExit("error: run-context must be main|isolated")
    if delivery not in {"announce", "webhook", "none"}:
        raise SystemExit("error: delivery must be announce|webhook|none")

    enabled = parse_bool(args.enabled) if args.enabled else True
    sid = f"{slugify(args.name)}-{local_now().strftime('%Y%m%d%H%M%S')}"

    item = {
        "id": sid,
        "name": args.name.strip(),
        "kind": kind,
        "spec": spec,
        "run_context": run_context,
        "delivery": delivery,
        "enabled": enabled,
        "created_at": utc_now(),
    }
    schedules.setdefault("schedules", [])
    schedules["schedules"].append(item)

    errors = validate_schedules_payload(schedules)
    if errors:
        raise SystemExit("error: invalid schedule payload after add: " + "; ".join(errors))

    write_json(paths["schedules"], schedules)
    print(json.dumps(item, indent=2, ensure_ascii=False))
    return 0


def cmd_schedule_list(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    skill_root = Path(__file__).resolve().parents[1]
    paths = ensure_files(project_root, skill_root)
    schedules = load_schedules(paths)

    items = [item for item in schedules.get("schedules", []) if isinstance(item, dict)]
    if args.json:
        print(json.dumps({"version": 1, "schedules": items}, indent=2, ensure_ascii=False))
        return 0

    if not items:
        print("(no schedules)")
        return 0
    for item in items:
        print(
            "{id} {kind} enabled={enabled} context={ctx} delivery={delivery} spec={spec}".format(
                id=item.get("id", ""),
                kind=item.get("kind", ""),
                enabled=item.get("enabled", True),
                ctx=item.get("run_context", ""),
                delivery=item.get("delivery", ""),
                spec=item.get("spec", ""),
            )
        )
    return 0


def cmd_schedule_remove(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    skill_root = Path(__file__).resolve().parents[1]
    paths = ensure_files(project_root, skill_root)
    schedules = load_schedules(paths)

    items = [item for item in schedules.get("schedules", []) if isinstance(item, dict)]
    keep = [item for item in items if str(item.get("id", "")) != args.id]
    if len(keep) == len(items):
        raise SystemExit(f"error: schedule id not found: {args.id}")

    schedules["schedules"] = keep
    write_json(paths["schedules"], schedules)
    print(f"removed: {args.id}")
    return 0


def build_tick_shell_command(project_root: Path, skill_root: Path, run_context: str, delivery: str) -> str:
    return (
        f'cd {shlex.quote(str(project_root))} && '
        f'BAGAKIT_LONG_RUN_SKILL_DIR={shlex.quote(str(skill_root))} '
        f'BAGAKIT_LONG_RUN_RUN_CONTEXT={shlex.quote(run_context)} '
        f'BAGAKIT_LONG_RUN_DELIVERY_MODE={shlex.quote(delivery)} '
        f'python3 {shlex.quote(str(skill_root / "scripts" / "long-run-heartbeat.py"))} '
        f'tick {shlex.quote(str(project_root))}'
    )


def cmd_schedule_render(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    skill_root = Path(__file__).resolve().parents[1]
    paths = ensure_files(project_root, skill_root)
    schedules = load_schedules(paths)

    item = next(
        (
            s
            for s in schedules.get("schedules", [])
            if isinstance(s, dict) and str(s.get("id", "")) == args.id
        ),
        None,
    )
    if item is None:
        raise SystemExit(f"error: schedule id not found: {args.id}")

    run_context = str(item.get("run_context", "main"))
    delivery = str(item.get("delivery", "announce"))
    kind = str(item.get("kind", ""))
    spec = str(item.get("spec", ""))

    one_shot_script = paths["schedules_generated"] / f"{args.id}.sh"
    command = build_tick_shell_command(project_root, skill_root, run_context, delivery)

    payload: Dict[str, Any] = {
        "id": args.id,
        "kind": kind,
        "spec": spec,
        "run_context": run_context,
        "delivery": delivery,
    }

    if kind == "every":
        seconds = validate_every_spec(spec)
        if seconds is None:
            raise SystemExit(f"error: invalid every spec: {spec}")
        script_path = paths["schedules_generated"] / f"{args.id}-loop.sh"
        script_path.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "while true; do\n"
            f"  {command}\n"
            f"  sleep {seconds}\n"
            "done\n",
            encoding="utf-8",
        )
        script_path.chmod(0o755)
        payload.update(
            {
                "script_path": str(script_path),
                "every_seconds": seconds,
                "hint": f"run: {script_path}",
            }
        )
    else:
        one_shot_script.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            f"{command}\n",
            encoding="utf-8",
        )
        one_shot_script.chmod(0o755)
        payload["script_path"] = str(one_shot_script)

        if kind == "cron":
            cron_line = (
                f"{spec} cd {shlex.quote(str(project_root))} && "
                f"BAGAKIT_LONG_RUN_SKILL_DIR={shlex.quote(str(skill_root))} "
                f"BAGAKIT_LONG_RUN_RUN_CONTEXT={shlex.quote(run_context)} "
                f"BAGAKIT_LONG_RUN_DELIVERY_MODE={shlex.quote(delivery)} "
                f"{shlex.quote(str(one_shot_script))} >> "
                f"{shlex.quote(str(paths['history_dir'] / (args.id + '.log')))} 2>&1"
            )
            payload["cron_line"] = cron_line
        elif kind == "at":
            run_at = iso_to_dt(spec)
            if run_at is None:
                raise SystemExit(f"error: invalid at spec: {spec}")
            local_time = run_at.astimezone()
            at_token = local_time.strftime("%Y%m%d%H%M")
            payload["at_instruction"] = (
                f"echo {shlex.quote(str(one_shot_script))} | at -t {at_token}"
            )

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def cmd_validate_config(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    skill_root = Path(__file__).resolve().parents[1]
    paths = ensure_files(project_root, skill_root)
    cfg = load_config(paths)
    errors = validate_config_payload(cfg)
    if errors:
        if args.json:
            print(json.dumps({"ok": False, "errors": errors}, indent=2, ensure_ascii=False))
        else:
            for err in errors:
                print(f"error: {err}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"ok": True}, indent=2, ensure_ascii=False))
    else:
        print("ok: heartbeat config valid")
    return 0


def cmd_validate_schedules(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    skill_root = Path(__file__).resolve().parents[1]
    paths = ensure_files(project_root, skill_root)
    schedules = load_schedules(paths)
    errors = validate_schedules_payload(schedules)
    if errors:
        if args.json:
            print(json.dumps({"ok": False, "errors": errors}, indent=2, ensure_ascii=False))
        else:
            for err in errors:
                print(f"error: {err}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"ok": True}, indent=2, ensure_ascii=False))
    else:
        print("ok: heartbeat schedules valid")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_tick = sub.add_parser("tick", help="run one heartbeat tick")
    p_tick.add_argument("project_root")
    p_tick.add_argument("--json", action="store_true")
    p_tick.add_argument("--dry-run", action="store_true")
    p_tick.set_defaults(func=cmd_tick)

    p_flash = sub.add_parser("flash-ideas", help="generate flash ideas from execution signals")
    p_flash.add_argument("project_root")
    p_flash.add_argument("--count", type=int, default=5)
    p_flash.add_argument("--json", action="store_true")
    p_flash.set_defaults(func=cmd_flash_ideas)

    p_add = sub.add_parser("schedule-add", help="add one local schedule")
    p_add.add_argument("project_root")
    p_add.add_argument("--kind", choices=["at", "every", "cron"], required=True)
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--spec", required=True)
    p_add.add_argument("--run-context", default="")
    p_add.add_argument("--delivery", default="")
    p_add.add_argument("--enabled", default="")
    p_add.set_defaults(func=cmd_schedule_add)

    p_list = sub.add_parser("schedule-list", help="list local schedules")
    p_list.add_argument("project_root")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_schedule_list)

    p_remove = sub.add_parser("schedule-remove", help="remove local schedule by id")
    p_remove.add_argument("project_root")
    p_remove.add_argument("--id", required=True)
    p_remove.set_defaults(func=cmd_schedule_remove)

    p_render = sub.add_parser("schedule-render", help="render runnable artifacts for external schedulers")
    p_render.add_argument("project_root")
    p_render.add_argument("--id", required=True)
    p_render.set_defaults(func=cmd_schedule_render)

    p_validate_cfg = sub.add_parser("validate-config", help="validate heartbeat config")
    p_validate_cfg.add_argument("project_root")
    p_validate_cfg.add_argument("--json", action="store_true")
    p_validate_cfg.set_defaults(func=cmd_validate_config)

    p_validate_schedules = sub.add_parser("validate-schedules", help="validate heartbeat schedules")
    p_validate_schedules.add_argument("project_root")
    p_validate_schedules.add_argument("--json", action="store_true")
    p_validate_schedules.set_defaults(func=cmd_validate_schedules)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
