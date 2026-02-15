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
STATUS_RANK = {
    "in_progress": 0,
    "todo": 1,
    "blocked": 2,
    "done": 3,
}

DEFAULT_TABLE: Dict[str, Any] = {
    "version": "1",
    "selection": {"strategy": "highest_priority_first"},
    "adapters": [
        {
            "name": "bagakit-ft-default",
            "kind": "bagakit-ft",
            "enabled": True,
            "root": ".",
            "weight": 100,
            "detect": {
                "all": [
                    {"path_exists": ".bagakit-ft/index/feats.json"},
                    {"json_has_key": {"path": ".bagakit-ft/index/feats.json", "key": "feats"}},
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
        },
    },
}


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


def load_execution_table(project_root: Path, table_arg: str | None) -> Tuple[Path | None, Dict[str, Any]]:
    if table_arg:
        table_path = Path(table_arg)
    else:
        table_path = project_root / ".bagakit-long-run" / "bk-execution-table.json"

    if table_path.exists():
        data = load_json(table_path)
        return table_path, data
    return None, DEFAULT_TABLE


def adapter_root(project_root: Path, adapter: Dict[str, Any]) -> Path:
    root = str(adapter.get("root", "."))
    return (project_root / root).resolve()


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
        # Backward-compatible shorthand: a single atomic rule object.
        raw_rules = [detect]

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


def collect_bagakit_ft(project_root: Path, adapter: Dict[str, Any]) -> List[Dict[str, Any]]:
    root = adapter_root(project_root, adapter)
    index_file = root / ".bagakit-ft" / "index" / "feats.json"
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

        feat_dir = root / ".bagakit-ft" / "feats" / feat_id
        state_file = feat_dir / "state.json"
        tasks_file = feat_dir / "tasks.json"
        if not state_file.exists() or not tasks_file.exists():
            continue

        state = load_json(state_file)
        tasks_data = load_json(tasks_file)
        tasks = tasks_data.get("tasks", [])
        if not isinstance(tasks, list):
            tasks = []

        feat_title = str(state.get("title") or feat_id)
        feat_status = str(state.get("status") or "proposal")
        feat_priority = parse_int(item.get("priority"), idx + 1)

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
            source_ref = str(tasks_file.relative_to(project_root))
            extra: Dict[str, Any] = {
                "feat_id": feat_id,
                "task_id": task_id,
                "branch": str(state.get("branch") or ""),
                "worktree": str(state.get("worktree_path") or ""),
            }
        else:
            row_id = f"bagakit-ft:{feat_id}"
            row_title = feat_title
            task_status = feat_to_row_status(feat_status)
            row_priority = feat_priority * 100
            source_ref = str(state_file.relative_to(project_root))
            extra = {
                "feat_id": feat_id,
                "task_id": "",
                "branch": str(state.get("branch") or ""),
                "worktree": str(state.get("worktree_path") or ""),
            }

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
                "change": change_name,
            }
        )

    return rows


def collect_rows_for_adapter(project_root: Path, adapter: Dict[str, Any]) -> List[Dict[str, Any]]:
    kind = str(adapter.get("kind", "")).strip()
    if kind == "bagakit-ft":
        return collect_bagakit_ft(project_root, adapter)
    if kind == "openspec":
        return collect_openspec(project_root, adapter)
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

    rows.sort(
        key=lambda row: (
            STATUS_RANK.get(str(row.get("status")), 9),
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
            }
        )

    if args.json:
        print(json.dumps({"table_path": str(table_path) if table_path else "<builtin-default>", "adapters": out}, indent=2, ensure_ascii=False))
        return 0

    print(f"table: {table_path if table_path else '<builtin-default>'}")
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
        print(
            f"{row['status']:<12} {row['system']:<10} {row['id']:<40} {row['title']}"
        )
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    _, table = load_execution_table(project_root, args.table)
    rows = collect_rows(project_root, table)
    next_rows = [r for r in rows if r.get("actionable")]
    if not next_rows:
        return 1
    row = next_rows[0]

    if args.json:
        print(json.dumps(row, indent=2, ensure_ascii=False))
        return 0

    print(f"{row['id']} {row['title']}")
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
        target_row = actionable[0] if actionable else (rows[0] if rows else None)

    system = str(args.system or (target_row.get("system") if target_row else "")).strip()
    if not system:
        print("error: no target system found; provide --system or ensure rows exist", file=sys.stderr)
        return 1

    guidance = merge_guidance(table, system)
    payload: Dict[str, Any] = {
        "system": system,
        "guidance": guidance,
    }
    if target_row:
        payload["target_row"] = {
            "id": target_row.get("id", ""),
            "title": target_row.get("title", ""),
            "status": target_row.get("status", ""),
            "source_ref": target_row.get("source_ref", ""),
        }

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if target_row:
        print(
            f"target: {target_row.get('id','')} ({target_row.get('status','')}) {target_row.get('title','')}"
        )
        print(f"source: {target_row.get('source_ref','')}")
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

    return {
        "id": fid,
        "title": str(row.get("title") or row.get("id")),
        "status": status,
        "priority": parse_int(row.get("priority"), 9999),
        "description": f"Execution row from {row.get('system')} ({row.get('id')}).",
        "dependencies": [],
        "acceptance_criteria": [
            f"Source item reaches done/blocked: {row.get('id')}",
            "Validation checks pass for changed scope",
        ],
        "updates": [f"{utc_now()} synced from bk-execution-table"],
        "managed_by": "execution-table",
        "source_system": str(row.get("system", "")),
        "source_item": str(row.get("id", "")),
        "source_ref": str(row.get("source_ref", "")),
    }


def cmd_sync_feature_list(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    feature_file = Path(args.feature_file) if args.feature_file else project_root / ".bagakit-long-run" / "feature-list.json"
    _, table = load_execution_table(project_root, args.table)
    rows = collect_rows(project_root, table)

    if feature_file.exists():
        data = load_json(feature_file)
    else:
        data = {"version": 1, "features": []}

    data = ensure_feature_doc(data)
    all_features = [f for f in data.get("features", []) if isinstance(f, dict)]
    manual = [f for f in all_features if str(f.get("managed_by", "")) != "execution-table"]

    generated = [row_to_feature(row) for row in rows]

    manual_has_in_progress = any(str(f.get("status")) == "in_progress" for f in manual)
    in_progress_taken = manual_has_in_progress

    # Keep a single in_progress item for validator compatibility.
    for feature in generated:
        if feature.get("status") == "in_progress":
            if in_progress_taken:
                feature["status"] = "todo"
            else:
                in_progress_taken = True

    data["features"] = manual + generated
    data["updated_at"] = utc_now()

    feature_file.parent.mkdir(parents=True, exist_ok=True)
    save_json(feature_file, data)

    print(f"synced feature list from execution rows: total_rows={len(rows)}")
    print(f"manual_features_kept={len(manual)} managed_features={len(generated)}")
    print(f"feature_file={feature_file}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="bagakit-long-run execution-table adapters")
    sub = parser.add_subparsers(dest="command", required=True)

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

    p_next = sub.add_parser("next", help="print next actionable execution row")
    p_next.add_argument("project_root")
    p_next.add_argument("--table", default="")
    p_next.add_argument("--json", action="store_true")
    p_next.set_defaults(func=cmd_next)

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
