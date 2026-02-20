#!/usr/bin/env python3
"""Feature list helper for bagakit-long-run harness."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ALLOWED_STATUS = {"todo", "in_progress", "done", "blocked"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"error: file not found: {path}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"error: invalid json in {path}: {e}")
    if not isinstance(data, dict):
        raise SystemExit(f"error: top-level json must be object: {path}")
    return data


def save_json(path: Path, data: Dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


def parse_confidence(value: Any, default: float = 0.5) -> float:
    if isinstance(value, bool):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, parsed))


def evidence_count(feature: Dict[str, Any]) -> int:
    value = feature.get("evidence_count")
    if not isinstance(value, bool):
        try:
            parsed = int(value)
            if parsed >= 0:
                return parsed
        except (TypeError, ValueError):
            pass
    evidence = feature.get("evidence")
    if isinstance(evidence, list):
        return len([item for item in evidence if str(item).strip()])
    return 0


def feature_sort_key(feature: Dict[str, Any]) -> tuple[float, int, int, str]:
    raw_priority = feature.get("priority", 10**9)
    try:
        priority = int(raw_priority)
    except (TypeError, ValueError):
        priority = 10**9
    confidence = parse_confidence(feature.get("confidence"), 0.5)
    evidence = evidence_count(feature)
    return (-confidence, -evidence, priority, str(feature.get("id", "")))


def validate_feature_list(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    features = data.get("features")
    if not isinstance(features, list):
        return ["missing or invalid 'features' array"]

    seen_ids = set()
    in_progress_count = 0

    for idx, item in enumerate(features):
        prefix = f"features[{idx}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: must be an object")
            continue

        for key in ("id", "title", "status"):
            if key not in item:
                errors.append(f"{prefix}: missing '{key}'")

        feature_id = item.get("id")
        if isinstance(feature_id, str):
            if feature_id in seen_ids:
                errors.append(f"{prefix}: duplicate id '{feature_id}'")
            seen_ids.add(feature_id)
        else:
            errors.append(f"{prefix}: id must be string")

        status = item.get("status")
        if status not in ALLOWED_STATUS:
            errors.append(f"{prefix}: invalid status '{status}'")
        if status == "in_progress":
            in_progress_count += 1

        if "priority" in item:
            try:
                int(item["priority"])
            except (TypeError, ValueError):
                errors.append(f"{prefix}: priority must be integer-like")

        if "confidence" in item:
            value = item.get("confidence")
            if isinstance(value, bool):
                errors.append(f"{prefix}: confidence must be a number between 0 and 1")
            else:
                try:
                    conf = float(value)
                except (TypeError, ValueError):
                    errors.append(f"{prefix}: confidence must be a number between 0 and 1")
                else:
                    if conf < 0.0 or conf > 1.0:
                        errors.append(f"{prefix}: confidence must be between 0 and 1")

        evidence = item.get("evidence")
        if evidence is not None:
            if not isinstance(evidence, list) or not all(str(e).strip() for e in evidence):
                errors.append(f"{prefix}: evidence must be an array of non-empty strings")

        if "evidence_count" in item:
            try:
                cnt = int(item.get("evidence_count"))
            except (TypeError, ValueError):
                errors.append(f"{prefix}: evidence_count must be integer-like")
            else:
                if cnt < 0:
                    errors.append(f"{prefix}: evidence_count must be >= 0")

        deps = item.get("dependencies")
        if deps is not None and not isinstance(deps, list):
            errors.append(f"{prefix}: dependencies must be an array")

        criteria = item.get("acceptance_criteria")
        if criteria is not None:
            if not isinstance(criteria, list) or not all(isinstance(c, str) for c in criteria):
                errors.append(f"{prefix}: acceptance_criteria must be an array of strings")

        updates = item.get("updates")
        if updates is not None:
            if not isinstance(updates, list) or not all(isinstance(u, str) for u in updates):
                errors.append(f"{prefix}: updates must be an array of strings")

    if in_progress_count > 1:
        errors.append("at most one feature may be 'in_progress'")

    return errors


def choose_feature(features: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    in_progress = sorted(
        [f for f in features if f.get("status") == "in_progress"],
        key=feature_sort_key,
    )
    if in_progress:
        return in_progress[0]

    todo = sorted(
        [f for f in features if f.get("status") == "todo"],
        key=feature_sort_key,
    )
    if todo:
        return todo[0]

    return None


def cmd_validate(args: argparse.Namespace) -> int:
    data = load_json(Path(args.file))
    errors = validate_feature_list(data)
    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        return 1
    print("ok")
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    data = load_json(Path(args.file))
    errors = validate_feature_list(data)
    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        return 1

    features = data["features"]
    counts = {status: 0 for status in ALLOWED_STATUS}
    for item in features:
        counts[item["status"]] += 1

    active = choose_feature(features)
    print(f"TOTAL {len(features)}")
    print(f"TODO {counts['todo']}")
    print(f"IN_PROGRESS {counts['in_progress']}")
    print(f"DONE {counts['done']}")
    print(f"BLOCKED {counts['blocked']}")
    if active:
        print(f"ACTIVE {active.get('id')} {active.get('title')}")
    else:
        print("ACTIVE NONE")
    return 0


def cmd_pick(args: argparse.Namespace) -> int:
    data = load_json(Path(args.file))
    errors = validate_feature_list(data)
    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        return 1

    active = choose_feature(data["features"])
    if not active:
        return 1

    if args.id_only:
        print(active["id"])
    else:
        print(f"{active['id']} {active.get('title', '')}".strip())
    return 0


def cmd_set_status(args: argparse.Namespace) -> int:
    path = Path(args.file)
    data = load_json(path)
    errors = validate_feature_list(data)
    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        return 1

    features = data["features"]
    target = None
    for item in features:
        if item.get("id") == args.feature_id:
            target = item
            break

    if target is None:
        print(f"error: feature id not found: {args.feature_id}", file=sys.stderr)
        return 1

    if args.status == "in_progress":
        others = [f for f in features if f.get("status") == "in_progress" and f.get("id") != args.feature_id]
        if others and not args.allow_switch:
            print(
                "error: another feature is already in_progress; use --allow-switch to move it back to todo",
                file=sys.stderr,
            )
            return 1
        if others and args.allow_switch:
            for item in others:
                item["status"] = "todo"
                updates = item.setdefault("updates", [])
                if isinstance(updates, list):
                    updates.append(f"{utc_now()} moved back to todo by status switch")

    target["status"] = args.status
    target["updated_at"] = utc_now()
    if args.note:
        updates = target.setdefault("updates", [])
        if not isinstance(updates, list):
            updates = []
            target["updates"] = updates
        updates.append(f"{utc_now()} {args.note}")

    save_json(path, data)
    print(f"updated {args.feature_id} -> {args.status}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="bagakit-long-run feature list helper")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="validate feature list json")
    p_validate.add_argument("file")
    p_validate.set_defaults(func=cmd_validate)

    p_summary = sub.add_parser("summary", help="print feature status summary")
    p_summary.add_argument("file")
    p_summary.set_defaults(func=cmd_summary)

    p_pick = sub.add_parser("pick", help="pick current feature (in_progress else top todo)")
    p_pick.add_argument("file")
    p_pick.add_argument("--id-only", action="store_true")
    p_pick.set_defaults(func=cmd_pick)

    p_set = sub.add_parser("set-status", help="set feature status")
    p_set.add_argument("file")
    p_set.add_argument("feature_id")
    p_set.add_argument("status", choices=sorted(ALLOWED_STATUS))
    p_set.add_argument("--note", default="")
    p_set.add_argument("--allow-switch", action="store_true")
    p_set.set_defaults(func=cmd_set_status)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
