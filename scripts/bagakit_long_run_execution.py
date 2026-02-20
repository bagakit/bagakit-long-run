#!/usr/bin/env python3
"""Execution-table adapters for bagakit-long-run.

This tool normalizes actionable items from external spec systems into a single
execution row list that long-run can consume.
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROW_STATUS = {"todo", "in_progress", "done", "blocked"}
FEATURE_STATUS = {"todo", "in_progress", "done", "blocked"}
STATUS_RANK = {
    "in_progress": 0,
    "todo": 1,
    "blocked": 2,
    "done": 3,
}
LONG_RUN_DIR = Path(".bagakit") / "long-run"
FT_HARNESS_DIR = Path(".bagakit") / "ft-harness"
KNOWN_ADAPTER_KINDS = {"bagakit-ft", "openspec", "manual"}
DETECTION_STATUS = {"draft", "ready"}
SELECTION_STRATEGY = "status_confidence_evidence_priority"
DEFAULT_CONFIDENCE_BY_STATUS = {
    "in_progress": 0.85,
    "todo": 0.70,
    "blocked": 0.25,
    "done": 0.10,
}
QUALITY_REQUIRED_PLAN_ITEMS = [
    "Why this item now",
    "Exact files to touch",
    "Commands/checks to run",
    "Verification or gate expectation",
    "Risk and rollback note",
]

DEFAULT_TABLE: Dict[str, Any] = {
    "version": "1",
    "selection": {"strategy": SELECTION_STRATEGY},
    "detection": {
        "status": "draft",
        "last_reviewed_at": "",
        "reviewed_by": "",
        "upstream_systems": [],
        "notes": "Run detect_prompt.md once, update adapters/guidance, then set status=ready.",
    },
    "adapters": [
        {
            "name": "bagakit-ft-default",
            "kind": "bagakit-ft",
            "enabled": True,
            "root": ".",
            "weight": 100,
            "detect": {
                "all": [
                    {"path_exists": ".bagakit/ft-harness/index/feats.json"},
                    {"json_has_key": {"path": ".bagakit/ft-harness/index/feats.json", "key": "feats"}},
                ]
            },
        },
        {
            "name": "openspec-default",
            "kind": "openspec",
            "enabled": True,
            "root": ".",
            "weight": 80,
            "detect": {
                "all": [
                    {"path_exists": "openspec/changes"},
                    {"glob_count_ge": {"pattern": "openspec/changes/*/tasks.md", "min": 1}},
                ]
            },
        },
        {
            "name": "manual-default",
            "kind": "manual",
            "enabled": False,
            "root": ".",
            "weight": 60,
            "detect": {
                "all": []
            },
            "rows": [],
        },
    ],
    "guidance": {
        "global": {
            "analyze_when": [
                "No item is currently in_progress",
                "Current item becomes blocked",
                "Upstream rows changed since previous run",
            ],
            "plan_must_include": [
                "Why this item now",
                "Exact files to touch",
                "Commands/checks to run",
                "Verification or gate expectation",
                "Risk and rollback note",
                "Acceptance checklist with binary pass/fail criteria",
                "Fallback or unblock action if checks fail",
            ],
        },
        "systems": {
            "openspec": {
                "analyze_when": [
                    "tasks.md has unchecked checklist items",
                    "proposal/scope changed since last pass",
                ],
                "plan_must_include": [
                    "change name and target capability",
                    "current checklist item from tasks.md",
                    "spec delta impact and validation command",
                ],
                "example": [
                    "Open proposal.md + tasks.md, pick first unchecked task, restate acceptance as executable checks.",
                ],
            },
            "bagakit-ft": {
                "analyze_when": [
                    "feat has an in_progress task",
                    "gate_fail_streak or no_progress counters increase",
                ],
                "plan_must_include": [
                    "feat-id and task-id",
                    "worktree path and branch",
                    "gate command path and expected result",
                ],
                "example": [
                    "Use feat/task state as SSOT, execute only current task, then run task gate and prepare structured commit.",
                ],
            },
            "manual": {
                "analyze_when": [
                    "Custom upstream tracker has pending actionable items",
                    "Mapped manual rows drift from source tracker",
                ],
                "plan_must_include": [
                    "source tracker id and current state",
                    "binary acceptance checks copied into handoff",
                    "exact file list and run commands",
                ],
                "example": [
                    "Map one upstream ticket into one manual row with acceptance_criteria/files_to_touch/commands, then execute single-item pass.",
                ],
            },
        },
    },
}


def resolve_long_run_dir(project_root: Path) -> Path:
    return project_root / LONG_RUN_DIR


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"error: file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: invalid json in {path}: {exc}")
    if not isinstance(data, dict):
        raise SystemExit(f"error: top-level json must be object: {path}")
    return data


def save_json(path: Path, data: Dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


def parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_confidence(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, parsed))


def parse_confidence_strict(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0.0 or parsed > 1.0:
        return None
    return parsed


def status_default_confidence(status: str) -> float:
    return DEFAULT_CONFIDENCE_BY_STATUS.get(status, 0.50)


def to_str_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        s = str(item).strip()
        if s:
            out.append(s)
    return out


def uniq_strs(items: List[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for item in items:
        v = str(item).strip()
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def normalize_row_signals(row: Dict[str, Any]) -> Dict[str, Any]:
    status = str(row.get("status", "todo"))
    confidence = parse_confidence(row.get("confidence"), status_default_confidence(status))
    evidence = to_str_list(row.get("evidence"))
    if not evidence:
        source_ref = str(row.get("source_ref", "")).strip()
        if source_ref:
            evidence = [f"source_ref={source_ref}"]
    row["confidence"] = confidence
    row["evidence"] = evidence
    row["evidence_count"] = parse_int(row.get("evidence_count"), len(evidence))
    if row["evidence_count"] < 0:
        row["evidence_count"] = len(evidence)
    return row


def load_execution_table(project_root: Path, table_arg: str | None) -> Tuple[Path | None, Dict[str, Any]]:
    if table_arg:
        table_path = Path(table_arg)
    else:
        table_path = resolve_long_run_dir(project_root) / "bk-execution-table.json"

    if not table_path.exists():
        raise SystemExit(f"error: execution table not found: {table_path}")
    data = load_json(table_path)
    return table_path, data


def adapter_root(project_root: Path, adapter: Dict[str, Any]) -> Path:
    root = str(adapter.get("root", "."))
    return (project_root / root).resolve()


def rel_ref(path: Path, project_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path.resolve())


def read_json_key(data: Any, key: str) -> tuple[bool, Any]:
    if not isinstance(key, str) or not key.strip():
        return False, None
    cur = data
    for part in [p for p in key.split(".") if p]:
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def eval_atomic_rule(adapter_root_path: Path, rule: Dict[str, Any]) -> bool:
    if not isinstance(rule, dict) or len(rule) != 1:
        return False

    op, payload = next(iter(rule.items()))

    if op == "path_exists":
        target = (adapter_root_path / str(payload)).resolve()
        return target.exists()

    if op == "glob_count_ge":
        if not isinstance(payload, dict):
            return False
        pattern = str(payload.get("pattern", "")).strip()
        if not pattern:
            return False
        min_count = max(0, parse_int(payload.get("min"), 1))
        full_pattern = str((adapter_root_path / pattern))
        return len(glob.glob(full_pattern, recursive=True)) >= min_count

    if op in {"json_has_key", "json_equals"}:
        if not isinstance(payload, dict):
            return False
        path_str = str(payload.get("path", "")).strip()
        key = str(payload.get("key", "")).strip()
        if not path_str or not key:
            return False
        path = (adapter_root_path / path_str).resolve()
        if not path.exists():
            return False
        try:
            data = load_json(path)
        except SystemExit:
            return False
        exists, value = read_json_key(data, key)
        if not exists:
            return False
        if op == "json_has_key":
            return True
        return value == payload.get("equals")

    if op == "file_contains":
        if not isinstance(payload, dict):
            return False
        path_str = str(payload.get("path", "")).strip()
        needle = str(payload.get("text", ""))
        if not path_str or not needle:
            return False
        path = (adapter_root_path / path_str).resolve()
        if not path.exists() or not path.is_file():
            return False
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return False
        return needle in text

    return False


def eval_detect_rules(adapter_root_path: Path, detect: Any) -> Dict[str, Any]:
    if not isinstance(detect, dict) or not detect:
        return {
            "matched": True,
            "mode": "none",
            "passed_rules": 0,
            "total_rules": 0,
        }

    mode = "all"
    raw_rules: Any = detect.get("all")
    if raw_rules is None and "any" in detect:
        mode = "any"
        raw_rules = detect.get("any")

    if raw_rules is None:
        return {
            "matched": False,
            "mode": mode,
            "passed_rules": 0,
            "total_rules": 0,
        }

    if not isinstance(raw_rules, list):
        return {
            "matched": False,
            "mode": mode,
            "passed_rules": 0,
            "total_rules": 0,
        }

    if not raw_rules:
        return {
            "matched": True,
            "mode": mode,
            "passed_rules": 0,
            "total_rules": 0,
        }

    passes = [eval_atomic_rule(adapter_root_path, r) for r in raw_rules]
    matched = all(passes) if mode == "all" else any(passes)
    return {
        "matched": matched,
        "mode": mode,
        "passed_rules": sum(1 for p in passes if p),
        "total_rules": len(passes),
    }


def feat_to_row_status(feat_status: str) -> str:
    mapping = {
        "proposal": "todo",
        "ready": "todo",
        "in_progress": "in_progress",
        "blocked": "blocked",
        "done": "done",
        "archived": "done",
    }
    return mapping.get(feat_status, "todo")


def parse_task_rank(task: Dict[str, Any], default: int = 9999) -> int:
    if "order" in task:
        return parse_int(task.get("order"), default)
    tid = str(task.get("id", ""))
    match = re.match(r"T-(\d+)", tid)
    if match:
        return int(match.group(1))
    return default


def pick_feat_task(tasks: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    in_progress = sorted(
        [t for t in tasks if t.get("status") == "in_progress"],
        key=parse_task_rank,
    )
    if in_progress:
        return in_progress[0]

    todo = sorted(
        [t for t in tasks if t.get("status") == "todo"],
        key=parse_task_rank,
    )
    if todo:
        return todo[0]

    blocked = sorted(
        [t for t in tasks if t.get("status") == "blocked"],
        key=parse_task_rank,
    )
    if blocked:
        return blocked[0]

    done = sorted(
        [t for t in tasks if t.get("status") == "done"],
        key=parse_task_rank,
    )
    if done:
        return done[0]

    return None


def bagakit_ft_index_summary(root: Path) -> Dict[str, int]:
    index_file = root / FT_HARNESS_DIR / "index" / "feats.json"
    if not index_file.exists():
        return {"total": 0, "archived": 0}

    try:
        index_data = load_json(index_file)
    except SystemExit:
        return {"total": 0, "archived": 0}

    feats = index_data.get("feats", [])
    if not isinstance(feats, list):
        return {"total": 0, "archived": 0}

    total = 0
    archived = 0
    for item in feats:
        if not isinstance(item, dict):
            continue
        feat_id = str(item.get("feat_id", "")).strip()
        if not feat_id:
            continue
        total += 1
        if str(item.get("status", "")).strip() == "archived":
            archived += 1
    return {"total": total, "archived": archived}


def resolve_bagakit_ft_files(
    harness_dir: Path, feat_id: str, index_status: str
) -> tuple[Path, Path] | None:
    # Final-state layout is strict by status to avoid ambiguous source rows.
    feat_dir = (
        harness_dir / "feats-archived" / feat_id
        if index_status == "archived"
        else harness_dir / "feats" / feat_id
    )
    state_file = feat_dir / "state.json"
    tasks_file = feat_dir / "tasks.json"
    if state_file.exists() and tasks_file.exists():
        return state_file, tasks_file
    return None


def collect_bagakit_ft(project_root: Path, adapter: Dict[str, Any]) -> List[Dict[str, Any]]:
    root = adapter_root(project_root, adapter)
    harness_dir = root / FT_HARNESS_DIR
    index_file = harness_dir / "index" / "feats.json"
    if not index_file.exists():
        return []

    index_data = load_json(index_file)
    feats = index_data.get("feats", [])
    if not isinstance(feats, list):
        return []

    rows: List[Dict[str, Any]] = []
    base_weight = parse_int(adapter.get("weight"), 100)

    for idx, item in enumerate(feats):
        if not isinstance(item, dict):
            continue
        feat_id = str(item.get("feat_id", "")).strip()
        if not feat_id:
            continue

        index_status = str(item.get("status") or "").strip()
        files = resolve_bagakit_ft_files(harness_dir, feat_id, index_status)
        if files is None:
            continue
        state_file, tasks_file = files

        state = load_json(state_file)
        tasks_data = load_json(tasks_file)
        tasks = tasks_data.get("tasks", [])
        if not isinstance(tasks, list):
            tasks = []

        feat_title = str(state.get("title") or feat_id)
        feat_status = str(state.get("status") or "proposal")
        feat_priority = parse_int(item.get("priority"), idx + 1)
        counters = state.get("counters", {}) if isinstance(state.get("counters"), dict) else {}
        gate_fail_streak = max(0, parse_int(counters.get("gate_fail_streak"), 0))
        no_progress_rounds = max(0, parse_int(counters.get("no_progress_rounds"), 0))
        round_count = max(0, parse_int(counters.get("round_count"), 0))
        state_current_task = str(state.get("current_task_id") or "")

        task = pick_feat_task([t for t in tasks if isinstance(t, dict)])
        if task:
            task_id = str(task.get("id") or "")
            task_title = str(task.get("title") or task_id or feat_title)
            task_status = str(task.get("status") or feat_to_row_status(feat_status))
            if task_status not in ROW_STATUS:
                task_status = feat_to_row_status(feat_status)
            row_id = f"bagakit-ft:{feat_id}:{task_id or 'task'}"
            row_title = f"{feat_title} / {task_title}"
            row_priority = feat_priority * 100 + parse_task_rank(task)
            source_ref = rel_ref(tasks_file, project_root)
            extra: Dict[str, Any] = {
                "feat_id": feat_id,
                "task_id": task_id,
                "branch": str(state.get("branch") or ""),
                "worktree": str(state.get("worktree_path") or ""),
            }
            task_gate_result = str(task.get("gate_result") or "")
        else:
            row_id = f"bagakit-ft:{feat_id}"
            row_title = feat_title
            task_status = feat_to_row_status(feat_status)
            row_priority = feat_priority * 100
            source_ref = rel_ref(state_file, project_root)
            extra = {
                "feat_id": feat_id,
                "task_id": "",
                "branch": str(state.get("branch") or ""),
                "worktree": str(state.get("worktree_path") or ""),
            }
            task_gate_result = ""

        confidence = status_default_confidence(task_status)
        confidence -= min(gate_fail_streak, 4) * 0.08
        confidence -= min(no_progress_rounds, 3) * 0.06
        if task_gate_result == "pass":
            confidence += 0.06
        elif task_gate_result == "fail":
            confidence -= 0.10
        if feat_status == "blocked":
            confidence = min(confidence, 0.30)
        confidence = max(0.05, min(0.99, confidence))

        evidence: List[str] = [
            f"feat_status={feat_status}",
            f"task_status={task_status}",
        ]
        if state_current_task:
            evidence.append(f"current_task={state_current_task}")
        if task:
            evidence.append(f"selected_task={str(task.get('id') or '')}")
        if gate_fail_streak > 0:
            evidence.append(f"gate_fail_streak={gate_fail_streak}")
        if no_progress_rounds > 0:
            evidence.append(f"no_progress_rounds={no_progress_rounds}")
        if round_count > 0:
            evidence.append(f"round_count={round_count}")
        if task_gate_result:
            evidence.append(f"task_gate_result={task_gate_result}")

        rows.append(
            {
                "id": row_id,
                "system": "bagakit-ft",
                "adapter": str(adapter.get("name") or "bagakit-ft"),
                "status": task_status,
                "priority": row_priority,
                "weight": base_weight,
                "title": row_title,
                "source_ref": source_ref,
                "actionable": task_status in {"todo", "in_progress"},
                "confidence": confidence,
                "evidence": evidence,
                **extra,
            }
        )

    return rows


def extract_heading(md: str) -> str | None:
    for line in md.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return None


TASK_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s+(.*)$")


def parse_markdown_tasks(path: Path) -> List[Dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []

    tasks: List[Dict[str, Any]] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        match = TASK_RE.match(line)
        if not match:
            continue
        done = match.group(1).lower() == "x"
        title = match.group(2).strip()
        tasks.append({"index": idx, "title": title, "done": done})
    return tasks


def collect_openspec(project_root: Path, adapter: Dict[str, Any]) -> List[Dict[str, Any]]:
    root = adapter_root(project_root, adapter)
    changes_dir = root / "openspec" / "changes"
    if not changes_dir.exists() or not changes_dir.is_dir():
        return []

    rows: List[Dict[str, Any]] = []
    base_weight = parse_int(adapter.get("weight"), 80)

    for idx, change_dir in enumerate(sorted([p for p in changes_dir.iterdir() if p.is_dir()]), start=1):
        change_name = change_dir.name
        proposal_file = change_dir / "proposal.md"
        tasks_file = change_dir / "tasks.md"

        title = change_name
        if proposal_file.exists():
            heading = extract_heading(proposal_file.read_text(encoding="utf-8"))
            if heading:
                title = heading

        tasks = parse_markdown_tasks(tasks_file)
        unchecked = [t for t in tasks if not t["done"]]
        checked = [t for t in tasks if t["done"]]

        if unchecked:
            task = unchecked[0]
            status = "in_progress" if checked else "todo"
            task_label = task["title"]
            row_id = f"openspec:{change_name}:{task['index']}"
            source_ref = str(tasks_file.relative_to(project_root)) if tasks_file.exists() else str(change_dir.relative_to(project_root))
        elif checked:
            task = checked[-1]
            status = "done"
            task_label = task["title"]
            row_id = f"openspec:{change_name}:{task['index']}"
            source_ref = str(tasks_file.relative_to(project_root)) if tasks_file.exists() else str(change_dir.relative_to(project_root))
        else:
            status = "todo"
            task_label = "plan change"
            row_id = f"openspec:{change_name}:change"
            source_ref = str(proposal_file.relative_to(project_root)) if proposal_file.exists() else str(change_dir.relative_to(project_root))

        confidence = status_default_confidence(status)
        if unchecked:
            confidence += 0.05
        if not tasks_file.exists():
            confidence -= 0.20
        if status == "done":
            confidence = min(confidence, 0.20)
        confidence = max(0.05, min(0.95, confidence))

        evidence: List[str] = [
            f"unchecked_tasks={len(unchecked)}",
            f"checked_tasks={len(checked)}",
        ]
        if tasks_file.exists():
            evidence.append(f"tasks_file={tasks_file.relative_to(project_root)}")
        else:
            evidence.append("tasks_file=missing")
        if unchecked:
            evidence.append(f"next_task_line={unchecked[0]['index']}")

        rows.append(
            {
                "id": row_id,
                "system": "openspec",
                "adapter": str(adapter.get("name") or "openspec"),
                "status": status,
                "priority": idx,
                "weight": base_weight,
                "title": f"{title} / {task_label}",
                "source_ref": source_ref,
                "actionable": status in {"todo", "in_progress"},
                "confidence": confidence,
                "evidence": evidence,
                "change": change_name,
            }
        )

    return rows


def collect_manual(project_root: Path, adapter: Dict[str, Any]) -> List[Dict[str, Any]]:
    base_weight = parse_int(adapter.get("weight"), 60)
    adapter_name = str(adapter.get("name") or "manual")
    raw_rows = adapter.get("rows", [])
    if not isinstance(raw_rows, list):
        return []

    rows: List[Dict[str, Any]] = []
    for idx, raw in enumerate(raw_rows, start=1):
        if not isinstance(raw, dict):
            continue
        row_id = str(raw.get("id", "")).strip()
        title = str(raw.get("title", "")).strip()
        status = str(raw.get("status", "todo")).strip()
        if not row_id or not title:
            continue
        if status not in ROW_STATUS:
            status = "todo"

        source_ref = str(raw.get("source_ref", "")).strip() or f"{adapter_name}:row:{idx}"
        row = {
            "id": row_id,
            "system": str(raw.get("system", "")).strip() or adapter_name,
            "adapter": adapter_name,
            "status": status,
            "priority": parse_int(raw.get("priority"), idx),
            "weight": parse_int(raw.get("weight"), base_weight),
            "title": title,
            "source_ref": source_ref,
            "actionable": status in {"todo", "in_progress"},
            "why_now": str(raw.get("why_now", "")).strip(),
            "acceptance_criteria": to_str_list(raw.get("acceptance_criteria")),
            "files_to_touch": to_str_list(raw.get("files_to_touch")),
            "commands": to_str_list(raw.get("commands")),
            "risks": to_str_list(raw.get("risks")),
            "confidence": parse_confidence(raw.get("confidence"), status_default_confidence(status)),
            "evidence": to_str_list(raw.get("evidence")),
            "evidence_count": parse_int(raw.get("evidence_count"), len(to_str_list(raw.get("evidence")))),
        }
        rows.append(row)

    return rows


def collect_rows_for_adapter(project_root: Path, adapter: Dict[str, Any]) -> List[Dict[str, Any]]:
    kind = str(adapter.get("kind", "")).strip()
    if kind == "bagakit-ft":
        return collect_bagakit_ft(project_root, adapter)
    if kind == "openspec":
        return collect_openspec(project_root, adapter)
    if kind == "manual":
        return collect_manual(project_root, adapter)
    return []


def collect_rows(project_root: Path, table: Dict[str, Any]) -> List[Dict[str, Any]]:
    adapters = table.get("adapters", [])
    if not isinstance(adapters, list):
        return []

    rows: List[Dict[str, Any]] = []
    for adapter in adapters:
        if not isinstance(adapter, dict):
            continue
        if not bool(adapter.get("enabled", True)):
            continue
        root = adapter_root(project_root, adapter)
        detect_summary = eval_detect_rules(root, adapter.get("detect", {}))
        if not bool(detect_summary.get("matched", False)):
            continue

        rows.extend(collect_rows_for_adapter(project_root, adapter))

    rows = [normalize_row_signals(row) for row in rows]

    rows.sort(
        key=lambda row: (
            STATUS_RANK.get(str(row.get("status")), 9),
            -parse_confidence(row.get("confidence"), status_default_confidence(str(row.get("status", "")))),
            -parse_int(row.get("evidence_count"), len(to_str_list(row.get("evidence")))),
            -parse_int(row.get("weight"), 0),
            parse_int(row.get("priority"), 10**9),
            str(row.get("id", "")),
        )
    )
    return rows


def truncate_rows(rows: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    if limit <= 0:
        return rows
    return rows[:limit]


def pick_next_row(rows: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    actionable = [row for row in rows if bool(row.get("actionable"))]
    if actionable:
        return actionable[0]
    return None


def feature_sort_key(feature: Dict[str, Any]) -> tuple[float, int, int, str]:
    priority = parse_int(feature.get("priority"), 10**9)
    confidence = parse_confidence(feature.get("confidence"), 0.5)
    evidence_count = parse_int(
        feature.get("evidence_count"), len(to_str_list(feature.get("evidence")))
    )
    return (-confidence, -evidence_count, priority, str(feature.get("id", "")))


def pick_feature_from_file(feature_file: Path) -> Dict[str, Any] | None:
    if not feature_file.exists():
        return None
    data = load_json(feature_file)
    features = data.get("features")
    if not isinstance(features, list):
        return None
    normalized = [f for f in features if isinstance(f, dict) and str(f.get("status")) in FEATURE_STATUS]
    in_progress = sorted(
        [f for f in normalized if f.get("status") == "in_progress"],
        key=feature_sort_key,
    )
    if in_progress:
        return in_progress[0]
    todo = sorted(
        [f for f in normalized if f.get("status") == "todo"],
        key=feature_sort_key,
    )
    if todo:
        return todo[0]
    return None


def validate_table_quality(table: Dict[str, Any]) -> List[str]:
    issues: List[str] = []

    selection = table.get("selection")
    if not isinstance(selection, dict):
        issues.append("selection must be an object")
    else:
        strategy = str(selection.get("strategy", "")).strip()
        if strategy != SELECTION_STRATEGY:
            issues.append(
                f"selection.strategy must be '{SELECTION_STRATEGY}'"
            )

    detection = table.get("detection")
    if not isinstance(detection, dict):
        issues.append("missing object: detection")
    else:
        status = str(detection.get("status", "")).strip()
        if status not in DETECTION_STATUS:
            issues.append(f"detection.status must be one of {sorted(DETECTION_STATUS)}")
        if status != "ready":
            issues.append("detection.status must be 'ready' (run detect prompt and update table first)")
        if status == "ready":
            if not str(detection.get("last_reviewed_at", "")).strip():
                issues.append("detection.last_reviewed_at is required when status=ready")
            if not str(detection.get("reviewed_by", "")).strip():
                issues.append("detection.reviewed_by is required when status=ready")
            systems = to_str_list(detection.get("upstream_systems"))
            if not systems:
                issues.append("detection.upstream_systems must list at least one detected upstream system when status=ready")

    adapters = table.get("adapters")
    if not isinstance(adapters, list) or not adapters:
        issues.append("adapters must be a non-empty array")
        return issues

    enabled_adapters: List[Dict[str, Any]] = []
    enabled_kinds: set[str] = set()
    for idx, adapter in enumerate(adapters):
        if not isinstance(adapter, dict):
            issues.append(f"adapters[{idx}] must be an object")
            continue

        name = str(adapter.get("name", "")).strip()
        kind = str(adapter.get("kind", "")).strip()
        enabled = bool(adapter.get("enabled", True))

        if not name:
            issues.append(f"adapters[{idx}] missing name")
        if not kind:
            issues.append(f"adapters[{idx}] missing kind")
        if enabled and kind not in KNOWN_ADAPTER_KINDS:
            issues.append(
                f"adapters[{idx}] kind={kind!r} is unsupported; use one of {sorted(KNOWN_ADAPTER_KINDS)} "
                "or implement a new collector"
            )

        if not enabled:
            continue

        enabled_adapters.append(adapter)
        enabled_kinds.add(kind)

        detect = adapter.get("detect")
        if not isinstance(detect, dict):
            issues.append(f"adapters[{idx}] detect must be an object")
            continue
        if "all" not in detect and "any" not in detect:
            issues.append(f"adapters[{idx}] detect must define 'all' or 'any' rules")
            continue
        key = "all" if "all" in detect else "any"
        rules = detect.get(key)
        if not isinstance(rules, list):
            issues.append(f"adapters[{idx}] detect.{key} must be a list")

        if kind == "manual":
            rows = adapter.get("rows")
            if not isinstance(rows, list) or not rows:
                issues.append(f"adapters[{idx}] manual adapter requires non-empty rows[]")
            else:
                for ridx, row in enumerate(rows):
                    prefix = f"adapters[{idx}].rows[{ridx}]"
                    if not isinstance(row, dict):
                        issues.append(f"{prefix} must be an object")
                        continue
                    for field in ("id", "title", "source_ref", "why_now"):
                        if not str(row.get(field, "")).strip():
                            issues.append(f"{prefix} missing required field: {field}")
                    status = str(row.get("status", "")).strip()
                    if status not in ROW_STATUS:
                        issues.append(f"{prefix} status must be one of {sorted(ROW_STATUS)}")
                    if len(to_str_list(row.get("acceptance_criteria"))) < 2:
                        issues.append(f"{prefix} acceptance_criteria must have at least 2 items")
                    if len(to_str_list(row.get("files_to_touch"))) < 1:
                        issues.append(f"{prefix} files_to_touch must have at least 1 path")
                    if len(to_str_list(row.get("commands"))) < 1:
                        issues.append(f"{prefix} commands must have at least 1 command")
                    confidence_raw = row.get("confidence")
                    if confidence_raw is None:
                        issues.append(f"{prefix} missing required field: confidence")
                    else:
                        confidence = parse_confidence_strict(confidence_raw)
                        if confidence is None:
                            issues.append(f"{prefix} confidence must be a number between 0 and 1")
                    if len(to_str_list(row.get("evidence"))) < 1:
                        issues.append(f"{prefix} evidence must have at least 1 item")

    if not enabled_adapters:
        issues.append("at least one adapter must be enabled")

    guidance = table.get("guidance")
    if not isinstance(guidance, dict):
        issues.append("guidance must be an object")
        return issues

    global_guidance = guidance.get("global")
    if not isinstance(global_guidance, dict):
        issues.append("guidance.global must be an object")
    else:
        analyze = to_str_list(global_guidance.get("analyze_when"))
        plan = to_str_list(global_guidance.get("plan_must_include"))
        if len(analyze) < 3:
            issues.append("guidance.global.analyze_when must have at least 3 items")
        if len(plan) < 5:
            issues.append("guidance.global.plan_must_include must have at least 5 items")
        for item in QUALITY_REQUIRED_PLAN_ITEMS:
            if item not in plan:
                issues.append(f"guidance.global.plan_must_include missing required item: {item}")

    systems = guidance.get("systems")
    if not isinstance(systems, dict):
        issues.append("guidance.systems must be an object")
        return issues

    for kind in sorted(enabled_kinds):
        entry = systems.get(kind)
        if not isinstance(entry, dict):
            issues.append(f"guidance.systems.{kind} must be defined for enabled adapter kind={kind}")
            continue
        if len(to_str_list(entry.get("analyze_when"))) < 1:
            issues.append(f"guidance.systems.{kind}.analyze_when must have at least 1 item")
        if len(to_str_list(entry.get("plan_must_include"))) < 3:
            issues.append(f"guidance.systems.{kind}.plan_must_include must have at least 3 items")
        if len(to_str_list(entry.get("example"))) < 1:
            issues.append(f"guidance.systems.{kind}.example must have at least 1 item")

    return issues


def cmd_validate_table(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    table_path, table = load_execution_table(project_root, args.table)
    issues = validate_table_quality(table)

    payload = {
        "table_path": str(table_path) if table_path else "",
        "ok": not issues,
        "issues": issues,
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if not issues else 1

    print(f"table: {table_path}")
    if issues:
        for issue in issues:
            print(f"error: {issue}", file=sys.stderr)
        print(
            f"next: use detect prompt at {(resolve_long_run_dir(project_root) / 'detect_prompt.md')}",
            file=sys.stderr,
        )
        return 1

    print("ok: execution table quality check passed")
    return 0


def cmd_detect(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    table_path, table = load_execution_table(project_root, args.table)
    adapters = table.get("adapters", [])

    out: List[Dict[str, Any]] = []
    for adapter in adapters if isinstance(adapters, list) else []:
        if not isinstance(adapter, dict):
            continue
        kind = str(adapter.get("kind", "")).strip()
        root = adapter_root(project_root, adapter)
        detect_rules = adapter.get("detect", {})
        detect_summary = eval_detect_rules(root, detect_rules)
        rows = collect_rows_for_adapter(project_root, adapter) if detect_summary["matched"] else []
        row_count = len(rows)
        if not detect_summary["matched"]:
            signal = "detect_unmatched"
        elif row_count > 0:
            signal = "rows_found"
        else:
            signal = "detect_matched_no_rows"
        adapter_warnings: List[str] = []
        index_summary: Dict[str, int] | None = None
        if kind == "bagakit-ft":
            index_summary = bagakit_ft_index_summary(root)
            if signal == "detect_matched_no_rows" and index_summary.get("total", 0) > 0:
                adapter_warnings.append(
                    "bagakit-ft index has feats but collector produced 0 rows; check feats/ vs feats-archived/ layout and state files"
                )
        out.append(
            {
                "name": str(adapter.get("name") or kind),
                "kind": kind,
                "root": str(root),
                "enabled": bool(adapter.get("enabled", True)),
                "signal": signal,
                "row_count": row_count,
                "detect_rules": detect_rules if isinstance(detect_rules, dict) else {},
                "detect_summary": detect_summary,
                "index_summary": index_summary or {},
                "warnings": adapter_warnings,
            }
        )

    if args.json:
        print(json.dumps({"table_path": str(table_path), "adapters": out}, indent=2, ensure_ascii=False))
        return 0

    print(f"table: {table_path}")
    for item in out:
        print(
            f"- {item['name']} ({item['kind']}) enabled={item['enabled']} signal={item['signal']} rows={item['row_count']} root={item['root']}"
        )
        detect_summary = item.get("detect_summary", {})
        if isinstance(detect_summary, dict):
            print(
                "  detect: matched={matched} mode={mode} pass={passed}/{total}".format(
                    matched=detect_summary.get("matched", False),
                    mode=detect_summary.get("mode", "none"),
                    passed=detect_summary.get("passed_rules", 0),
                    total=detect_summary.get("total_rules", 0),
                )
            )
        rules = item.get("detect_rules", {})
        if isinstance(rules, dict) and rules:
            print(f"  rules: {json.dumps(rules, ensure_ascii=False)}")
        index_summary = item.get("index_summary", {})
        if isinstance(index_summary, dict) and index_summary:
            print(
                "  index: total={total} archived={archived}".format(
                    total=parse_int(index_summary.get("total"), 0),
                    archived=parse_int(index_summary.get("archived"), 0),
                )
            )
        for warning in to_str_list(item.get("warnings")):
            print(f"  warn: {warning}")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    _, table = load_execution_table(project_root, args.table)
    rows = truncate_rows(collect_rows(project_root, table), args.limit)

    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0

    if not rows:
        print("(no execution rows found)")
        return 0

    for row in rows:
        confidence = parse_confidence(
            row.get("confidence"),
            status_default_confidence(str(row.get("status", ""))),
        )
        evidence_count = parse_int(row.get("evidence_count"), len(to_str_list(row.get("evidence"))))
        print(
            f"{row['status']:<12} conf={confidence:.2f} ev={evidence_count:<2} "
            f"{row['system']:<10} {row['id']:<40} {row['title']}"
        )
    return 0


def cmd_next_action(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    _, table = load_execution_table(project_root, args.table)
    rows = collect_rows(project_root, table)
    next_row = pick_next_row(rows)

    feature_file = (
        Path(args.feature_file)
        if args.feature_file
        else resolve_long_run_dir(project_root) / "feature-list.json"
    )
    next_feature = pick_feature_from_file(feature_file)

    resume_command = "bash .bagakit/long-run/check_and_resume.sh"
    payload: Dict[str, Any] = {
        "selection_strategy": SELECTION_STRATEGY,
        "resume_command": resume_command,
        "next_row": None,
        "next_feature": None,
        "footer_line": "",
    }

    if next_row:
        confidence = parse_confidence(
            next_row.get("confidence"),
            status_default_confidence(str(next_row.get("status", ""))),
        )
        evidence = to_str_list(next_row.get("evidence"))
        evidence_count = parse_int(next_row.get("evidence_count"), len(evidence))
        payload["next_row"] = {
            "id": next_row.get("id", ""),
            "title": next_row.get("title", ""),
            "status": next_row.get("status", ""),
            "system": next_row.get("system", ""),
            "source_ref": next_row.get("source_ref", ""),
            "confidence": confidence,
            "evidence": evidence,
            "evidence_count": evidence_count,
        }
        evidence_brief = " | ".join(evidence[:3]) if evidence else "none"
        payload["footer_line"] = (
            f"- LongRun: Item={next_row.get('id','')}; "
            f"Status={next_row.get('status','')}; "
            f"Confidence={confidence:.2f}; "
            f"Evidence={evidence_brief}; "
            f"Next={resume_command}"
        )
    else:
        payload["footer_line"] = (
            f"- LongRun: Item=none; Status=blocked; Confidence=0.00; "
            f"Evidence=no actionable row; Next={resume_command}"
        )

    if next_feature:
        payload["next_feature"] = {
            "id": next_feature.get("id", ""),
            "title": next_feature.get("title", ""),
            "status": next_feature.get("status", ""),
            "confidence": parse_confidence(next_feature.get("confidence"), 0.5),
            "evidence_count": parse_int(
                next_feature.get("evidence_count"),
                len(to_str_list(next_feature.get("evidence"))),
            ),
        }

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if payload["next_row"]:
        row = payload["next_row"]
        print(
            "next_row: {id} ({status}) {title}".format(
                id=row.get("id", ""),
                status=row.get("status", ""),
                title=row.get("title", ""),
            )
        )
        print(f"system: {row.get('system', '')}")
        print(f"source: {row.get('source_ref', '')}")
        print(
            "confidence/evidence: conf={conf:.2f} evidence_count={ev}".format(
                conf=float(row.get("confidence", 0.0)),
                ev=row.get("evidence_count", 0),
            )
        )
    else:
        print("next_row: none")

    if payload["next_feature"]:
        feat = payload["next_feature"]
        print(
            "next_feature: {id} ({status}) {title}".format(
                id=feat.get("id", ""),
                status=feat.get("status", ""),
                title=feat.get("title", ""),
            )
        )
    else:
        print("next_feature: none")

    print("footer_line:")
    print(payload["footer_line"])
    return 0


def merge_guidance(table: Dict[str, Any], system: str) -> Dict[str, List[str]]:
    default_guidance = DEFAULT_TABLE.get("guidance", {})
    table_guidance = table.get("guidance", {}) if isinstance(table.get("guidance", {}), dict) else {}

    def read_list(source: Dict[str, Any], path: List[str]) -> List[str]:
        cur: Any = source
        for key in path:
            if not isinstance(cur, dict):
                return []
            cur = cur.get(key, {})
        if isinstance(cur, list):
            return [str(x) for x in cur]
        return []

    merged_analyze = uniq_strs(
        read_list(default_guidance, ["global", "analyze_when"])
        + read_list(table_guidance, ["global", "analyze_when"])
        + read_list(default_guidance, ["systems", system, "analyze_when"])
        + read_list(table_guidance, ["systems", system, "analyze_when"])
    )
    merged_plan = uniq_strs(
        read_list(default_guidance, ["global", "plan_must_include"])
        + read_list(table_guidance, ["global", "plan_must_include"])
        + read_list(default_guidance, ["systems", system, "plan_must_include"])
        + read_list(table_guidance, ["systems", system, "plan_must_include"])
    )
    merged_example = uniq_strs(
        read_list(default_guidance, ["systems", system, "example"])
        + read_list(table_guidance, ["systems", system, "example"])
    )

    return {
        "analyze_when": merged_analyze,
        "plan_must_include": merged_plan,
        "example": merged_example,
    }


def cmd_guide(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    _, table = load_execution_table(project_root, args.table)
    rows = collect_rows(project_root, table)

    target_row: Dict[str, Any] | None = None
    if args.row_id:
        target_row = next((r for r in rows if str(r.get("id")) == args.row_id), None)
    elif not args.system:
        actionable = [r for r in rows if r.get("actionable")]
        target_row = actionable[0] if actionable else None

    system = str(args.system or (target_row.get("system") if target_row else "")).strip()
    if not system:
        if rows:
            print(
                "error: no actionable rows found; provide --system/--row-id if you need non-actionable guidance",
                file=sys.stderr,
            )
        else:
            print("error: no target system found; provide --system or ensure rows exist", file=sys.stderr)
        return 1

    guidance = merge_guidance(table, system)
    payload: Dict[str, Any] = {
        "system": system,
        "guidance": guidance,
    }
    if target_row:
        target_confidence = parse_confidence(
            target_row.get("confidence"),
            status_default_confidence(str(target_row.get("status", ""))),
        )
        target_evidence = to_str_list(target_row.get("evidence"))
        payload["target_row"] = {
            "id": target_row.get("id", ""),
            "title": target_row.get("title", ""),
            "status": target_row.get("status", ""),
            "source_ref": target_row.get("source_ref", ""),
            "confidence": target_confidence,
            "evidence": target_evidence,
            "evidence_count": parse_int(target_row.get("evidence_count"), len(target_evidence)),
        }

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if target_row:
        confidence = parse_confidence(
            target_row.get("confidence"),
            status_default_confidence(str(target_row.get("status", ""))),
        )
        evidence = to_str_list(target_row.get("evidence"))
        print(
            f"target: {target_row.get('id','')} ({target_row.get('status','')}) {target_row.get('title','')}"
        )
        print(f"source: {target_row.get('source_ref','')}")
        print(f"confidence: {confidence:.2f}")
        if evidence:
            print("evidence:")
            for item in evidence:
                print(f"- {item}")
    print(f"system: {system}")
    print("analyze_when:")
    for item in guidance["analyze_when"]:
        print(f"- {item}")
    print("plan_must_include:")
    for item in guidance["plan_must_include"]:
        print(f"- {item}")
    if guidance["example"]:
        print("example:")
        for item in guidance["example"]:
            print(f"- {item}")
    return 0


def ensure_feature_doc(data: Dict[str, Any]) -> Dict[str, Any]:
    if "features" not in data or not isinstance(data["features"], list):
        data["features"] = []
    if "version" not in data:
        data["version"] = 1
    return data


def row_to_feature(row: Dict[str, Any]) -> Dict[str, Any]:
    fid = f"EXEC::{row['id']}"
    status = str(row.get("status", "todo"))
    if status not in ROW_STATUS:
        status = "todo"
    confidence = parse_confidence(row.get("confidence"), status_default_confidence(status))
    evidence = to_str_list(row.get("evidence"))
    evidence_count = parse_int(row.get("evidence_count"), len(evidence))

    acceptance = to_str_list(row.get("acceptance_criteria"))
    if not acceptance:
        acceptance = [
            f"Source item reaches done/blocked: {row.get('id')}",
            "Validation checks pass for changed scope",
        ]
    files_to_touch = to_str_list(row.get("files_to_touch"))
    commands = to_str_list(row.get("commands"))
    risks = to_str_list(row.get("risks"))
    why_now = str(row.get("why_now", "")).strip()

    desc = f"Execution row from {row.get('system')} ({row.get('id')})."
    if why_now:
        desc = f"{desc} Why now: {why_now}"

    return {
        "id": fid,
        "title": str(row.get("title") or row.get("id")),
        "status": status,
        "priority": parse_int(row.get("priority"), 9999),
        "description": desc,
        "dependencies": [],
        "acceptance_criteria": acceptance,
        "files_to_touch": files_to_touch,
        "commands": commands,
        "risks": risks,
        "why_now": why_now,
        "updates": [f"{utc_now()} synced from bk-execution-table"],
        "managed_by": "execution-table",
        "confidence": confidence,
        "evidence": evidence,
        "evidence_count": evidence_count,
        "source_system": str(row.get("system", "")),
        "source_item": str(row.get("id", "")),
        "source_ref": str(row.get("source_ref", "")),
    }


def cmd_sync_feature_list(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    feature_file = (
        Path(args.feature_file)
        if args.feature_file
        else resolve_long_run_dir(project_root) / "feature-list.json"
    )
    _, table = load_execution_table(project_root, args.table)
    rows = collect_rows(project_root, table)

    if feature_file.exists():
        data = load_json(feature_file)
    else:
        data = {"version": 1, "features": []}

    data = ensure_feature_doc(data)
    all_features = [f for f in data.get("features", []) if isinstance(f, dict)]
    manual = [f for f in all_features if str(f.get("managed_by", "")) != "execution-table"]
    managed_existing = [f for f in all_features if str(f.get("managed_by", "")) == "execution-table"]

    generated = [row_to_feature(row) for row in rows]
    generated_ids = {str(f.get("id", "")) for f in generated if str(f.get("id", ""))}

    manual_has_in_progress = any(str(f.get("status")) == "in_progress" for f in manual)
    in_progress_taken = manual_has_in_progress

    # Keep exactly one in_progress item to preserve deterministic selection.
    for feature in generated:
        if feature.get("status") == "in_progress":
            if in_progress_taken:
                feature["status"] = "todo"
            else:
                in_progress_taken = True

    now = utc_now()
    tombstoned: List[Dict[str, Any]] = []
    for feature in managed_existing:
        fid = str(feature.get("id", "")).strip()
        if not fid or fid in generated_ids:
            continue
        tombstone = dict(feature)
        tombstone["managed_by"] = "execution-table"
        tombstone["managed_state"] = "stale_missing_upstream"
        tombstone["stale_since"] = str(tombstone.get("stale_since") or now)
        status = str(tombstone.get("status", "todo")).strip()
        if status in {"todo", "in_progress"}:
            tombstone["status"] = "blocked"
        updates = to_str_list(tombstone.get("updates"))
        updates.append(f"{now} upstream row missing during sync; kept as tombstone")
        tombstone["updates"] = updates
        tombstoned.append(tombstone)

    data["features"] = manual + generated + tombstoned
    data["updated_at"] = now

    feature_file.parent.mkdir(parents=True, exist_ok=True)
    save_json(feature_file, data)

    print(f"synced feature list from execution rows: total_rows={len(rows)}")
    print(
        "manual_features_kept={manual} managed_features={managed} managed_tombstones={tombstones}".format(
            manual=len(manual),
            managed=len(generated),
            tombstones=len(tombstoned),
        )
    )
    print(f"feature_file={feature_file}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="bagakit-long-run execution-table adapters")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate_table = sub.add_parser("validate-table", help="validate execution-table quality contract")
    p_validate_table.add_argument("project_root")
    p_validate_table.add_argument("--table", default="")
    p_validate_table.add_argument("--json", action="store_true")
    p_validate_table.set_defaults(func=cmd_validate_table)

    p_detect = sub.add_parser("detect", help="detect configured adapter roots")
    p_detect.add_argument("project_root")
    p_detect.add_argument("--table", default="")
    p_detect.add_argument("--json", action="store_true")
    p_detect.set_defaults(func=cmd_detect)

    p_plan = sub.add_parser("plan", help="list normalized execution rows")
    p_plan.add_argument("project_root")
    p_plan.add_argument("--table", default="")
    p_plan.add_argument("--limit", type=int, default=0, help="0 means no limit")
    p_plan.add_argument("--json", action="store_true")
    p_plan.set_defaults(func=cmd_plan)

    p_next = sub.add_parser("next-action", help="print structured next-action recommendation")
    p_next.add_argument("project_root")
    p_next.add_argument("--table", default="")
    p_next.add_argument("--feature-file", default="")
    p_next.add_argument("--json", action="store_true")
    p_next.set_defaults(func=cmd_next_action)

    p_guide = sub.add_parser("guide", help="print guidance checklist for target system/item")
    p_guide.add_argument("project_root")
    p_guide.add_argument("--table", default="")
    p_guide.add_argument("--row-id", default="")
    p_guide.add_argument("--system", default="")
    p_guide.add_argument("--json", action="store_true")
    p_guide.set_defaults(func=cmd_guide)

    p_sync = sub.add_parser("sync-feature-list", help="sync execution rows into long-run feature-list.json")
    p_sync.add_argument("project_root")
    p_sync.add_argument("--table", default="")
    p_sync.add_argument("--feature-file", default="")
    p_sync.set_defaults(func=cmd_sync_feature_list)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
