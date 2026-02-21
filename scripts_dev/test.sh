#!/usr/bin/env bash
set -euo pipefail

dev_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill_root="$(cd "${dev_script_dir}/.." && pwd)"
runtime_scripts_dir="${skill_root}/scripts"
heartbeat_tool="${runtime_scripts_dir}/long-run-heartbeat.py"

tmp="$(mktemp -d -t bagakit-long-run-test.XXXXXX)"
trap 'rm -rf "$tmp"' EXIT

project="${tmp}/project"
mkdir -p "$project"
harness_dir="${project}/.bagakit/long-run"
ft_harness_dir="${project}/.bagakit/ft-harness"

echo "[test] docs + template policy audit"
python3 - <<PY
import json
from pathlib import Path

root = Path(r"${skill_root}")
doc = (root / "docs" / "notes-long-run-agent-first-detect.md").read_text(encoding="utf-8")
required_phrases = [
    "no hard dependency on external systems",
    "optional adapters",
]
for phrase in required_phrases:
    if phrase not in doc:
        raise SystemExit(f"missing policy phrase in docs/notes-long-run-agent-first-detect.md: {phrase}")

resume_doc = (root / "docs" / "guidelines-long-run-resume.md").read_text(encoding="utf-8")
for phrase in ("bash .bagakit/long-run/check_and_resume.sh", "LongRunStop:"):
    if phrase not in resume_doc:
        raise SystemExit(f"missing resume/stop contract phrase in docs/guidelines-long-run-resume.md: {phrase}")

table = json.loads((root / "references" / "tpl" / "bk-execution-table-template.json").read_text(encoding="utf-8"))
selection = table.get("selection", {})
if selection.get("strategy") != "status_confidence_evidence_priority":
    raise SystemExit("unexpected selection.strategy in execution table template")
adapters = table.get("adapters", [])
kinds = {str(a.get("kind", "")) for a in adapters if isinstance(a, dict)}
for kind in ("bagakit-ft", "openspec", "manual"):
    if kind not in kinds:
        raise SystemExit(f"missing built-in adapter kind in template: {kind}")

detect_prompt = (root / "references" / "tpl" / "detect-prompt-template.md").read_text(encoding="utf-8")
for phrase in ("confidence", "evidence"):
    if phrase not in detect_prompt:
        raise SystemExit(f"missing phrase in detect prompt template: {phrase}")
PY

echo "[test] apply harness"
bash "${runtime_scripts_dir}/apply-long-run.sh" "$project"

[[ -f "${harness_dir}/bk-execution-handoff.md" ]]
[[ -f "${harness_dir}/bk-execution-table.json" ]]
[[ -f "${harness_dir}/detect_prompt.md" ]]
[[ -f "${harness_dir}/check_and_resume.sh" ]]
[[ -f "${harness_dir}/heartbeat.config.json" ]]
[[ -f "${harness_dir}/heartbeat-schedules.json" ]]
[[ -f "${harness_dir}/heartbeat.state.json" ]]
[[ -f "${harness_dir}/inbox/queue.json" ]]
[[ -d "${harness_dir}/inbox/history" ]]
[[ -d "${harness_dir}/inbox/flash-ideas" ]]
[[ ! -e "${harness_dir}/init.sh" ]]
[[ ! -e "${harness_dir}/initial_prompt.md" ]]
[[ -f "${project}/AGENTS.md" ]]
grep -q "<!-- BAGAKIT:LONGRUN:START -->" "${project}/AGENTS.md"
grep -q "<!-- BAGAKIT:LONGRUN:END -->" "${project}/AGENTS.md"
grep -q "\[\[BAGAKIT\]\]" "${project}/AGENTS.md"
grep -q "LongRun:" "${project}/AGENTS.md"
grep -q "Confidence=" "${project}/AGENTS.md"
grep -q "LongRunStop:" "${project}/AGENTS.md"
grep -q "\[\[BAGAKIT\]\]" "${harness_dir}/detect_prompt.md"
grep -q "LongRun:" "${harness_dir}/detect_prompt.md"
grep -q "Confidence=" "${harness_dir}/detect_prompt.md"
grep -q "LongRunStop:" "${harness_dir}/detect_prompt.md"
grep -q "\[\[BAGAKIT\]\]" "${harness_dir}/initializer_prompt.md"
grep -q "LongRun:" "${harness_dir}/initializer_prompt.md"
grep -q "Confidence=" "${harness_dir}/initializer_prompt.md"
grep -q "LongRunStop:" "${harness_dir}/initializer_prompt.md"
grep -q "\[\[BAGAKIT\]\]" "${harness_dir}/coding_prompt.md"
grep -q "LongRun:" "${harness_dir}/coding_prompt.md"
grep -q "Confidence=" "${harness_dir}/coding_prompt.md"
grep -q "LongRunStop:" "${harness_dir}/coding_prompt.md"
grep -q "\[\[BAGAKIT\]\]" "${harness_dir}/bk-execution-handoff.md"
grep -q "^- LongRun:" "${harness_dir}/bk-execution-handoff.md"
grep -q "Confidence=" "${harness_dir}/bk-execution-handoff.md"
grep -q "LongRunStop:" "${harness_dir}/bk-execution-handoff.md"

echo "[test] detect quality gate should fail when draft"
if python3 "${runtime_scripts_dir}/long-run-execution.py" validate-table "${project}" --table "${harness_dir}/bk-execution-table.json" >/dev/null 2>&1; then
  echo "[test] expected validate-table to fail when detection.status=draft" >&2
  exit 1
fi

echo "[test] mark detection review ready"
python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
p = Path(r"${harness_dir}/bk-execution-table.json")
data = json.loads(p.read_text(encoding="utf-8"))
det = data.setdefault("detection", {})
det["status"] = "ready"
det["last_reviewed_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
det["reviewed_by"] = "test"
det["upstream_systems"] = ["bagakit-ft"]
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

echo "[test] validate harness"
bash "${runtime_scripts_dir}/validate-long-run.sh" "$project"

echo "[test] execution adapters: seed bagakit-ft + openspec"
mkdir -p "${ft_harness_dir}/index" "${ft_harness_dir}/feats-archived/f-20260215-sync-sample" "${project}/openspec/changes/add-health-check"
cat > "${ft_harness_dir}/index/feats.json" <<'EOF'
{
  "version": 1,
  "feats": [
    {
      "feat_id": "f-20260215-sync-sample",
      "status": "archived",
      "priority": 1
    }
  ]
}
EOF
cat > "${ft_harness_dir}/feats-archived/f-20260215-sync-sample/state.json" <<'EOF'
{
  "feat_id": "f-20260215-sync-sample",
  "title": "Sync Sample Feat",
  "status": "archived",
  "branch": "feat/f-20260215-sync-sample",
  "worktree_path": ".worktrees/wt-f-20260215-sync-sample"
}
EOF
cat > "${ft_harness_dir}/feats-archived/f-20260215-sync-sample/tasks.json" <<'EOF'
{
  "tasks": [
    {
      "id": "T-001",
      "title": "Implement sync",
      "status": "done"
    }
  ]
}
EOF
cat > "${project}/openspec/changes/add-health-check/proposal.md" <<'EOF'
# Add health check endpoint
EOF
cat > "${project}/openspec/changes/add-health-check/tasks.md" <<'EOF'
- [ ] Define endpoint contract
- [ ] Implement endpoint
EOF

echo "[test] execution plan + sync"
python3 "${runtime_scripts_dir}/long-run-execution.py" detect "${project}" --table "${harness_dir}/bk-execution-table.json" >/dev/null
python3 - <<PY
import json
import subprocess

out = subprocess.check_output(
    [
        "python3",
        r"${runtime_scripts_dir}/long-run-execution.py",
        "detect",
        r"${project}",
        "--table",
        r"${harness_dir}/bk-execution-table.json",
        "--json",
    ],
    text=True,
)
data = json.loads(out)
adapters = {item.get("kind"): item for item in data.get("adapters", []) if isinstance(item, dict)}
ft = adapters.get("bagakit-ft")
if not ft:
    raise SystemExit("missing bagakit-ft detect result")
if int(ft.get("row_count", 0)) < 1:
    raise SystemExit("expected bagakit-ft collector to read archived feat rows")
PY
python3 "${runtime_scripts_dir}/long-run-execution.py" plan "${project}" --table "${harness_dir}/bk-execution-table.json" >/dev/null
python3 "${runtime_scripts_dir}/long-run-execution.py" next-action "${project}" --table "${harness_dir}/bk-execution-table.json" --feature-file "${harness_dir}/feature-list.json" --json >/dev/null
python3 "${runtime_scripts_dir}/long-run-execution.py" guide "${project}" --table "${harness_dir}/bk-execution-table.json" >/dev/null
python3 "${runtime_scripts_dir}/long-run-execution.py" sync-feature-list "${project}" --table "${harness_dir}/bk-execution-table.json" --feature-file "${harness_dir}/feature-list.json" >/dev/null

echo "[test] guide should fail when only non-actionable rows remain"
python3 - <<PY
import json
from pathlib import Path
p = Path(r"${harness_dir}/bk-execution-table.json")
data = json.loads(p.read_text(encoding="utf-8"))
for adapter in data.get("adapters", []):
    if not isinstance(adapter, dict):
        continue
    kind = str(adapter.get("kind", ""))
    if kind == "bagakit-ft":
        adapter["enabled"] = True
    elif kind in {"openspec", "manual"}:
        adapter["enabled"] = False
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
PY
if python3 "${runtime_scripts_dir}/long-run-execution.py" guide "${project}" --table "${harness_dir}/bk-execution-table.json" >/dev/null 2>&1; then
  echo "[test] expected guide to fail when no actionable rows exist" >&2
  exit 1
fi

echo "[test] sync should keep tombstone when managed rows disappear upstream"
cat > "${ft_harness_dir}/index/feats.json" <<'EOF'
{
  "version": 1,
  "feats": []
}
EOF
python3 "${runtime_scripts_dir}/long-run-execution.py" sync-feature-list "${project}" --table "${harness_dir}/bk-execution-table.json" --feature-file "${harness_dir}/feature-list.json" >/dev/null
python3 - <<PY
import json
from pathlib import Path
p = Path(r"${harness_dir}/feature-list.json")
data = json.loads(p.read_text(encoding="utf-8"))
features = [f for f in data.get("features", []) if isinstance(f, dict)]
tombstones = [f for f in features if f.get("managed_state") == "stale_missing_upstream"]
if not tombstones:
    raise SystemExit("expected tombstone managed features when upstream rows disappear")
PY

echo "[test] check+resume should emit structured next-action contract"
export BAGAKIT_LONG_RUN_SKILL_DIR="${skill_root}"
bash "${harness_dir}/check_and_resume.sh" >/dev/null
[[ -f "${harness_dir}/next-action.json" ]]
python3 - <<PY
import json
from pathlib import Path
p = Path(r"${harness_dir}/next-action.json")
data = json.loads(p.read_text(encoding="utf-8"))
for key in ("resume_command", "selection_strategy", "footer_line"):
    if key not in data:
        raise SystemExit(f"missing next-action key: {key}")
if "Confidence=" not in str(data.get("footer_line", "")):
    raise SystemExit("next-action footer_line missing Confidence signal")
PY

echo "[test] heartbeat validators"
python3 "${heartbeat_tool}" validate-config "${project}" >/dev/null
python3 "${heartbeat_tool}" validate-schedules "${project}" >/dev/null

echo "[test] heartbeat tick skips when disabled"
python3 - <<PY
import json
from pathlib import Path
p = Path(r"${harness_dir}/heartbeat.config.json")
cfg = json.loads(p.read_text(encoding="utf-8"))
cfg["enabled"] = False
p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
python3 - <<PY
import json
import subprocess
out = subprocess.check_output(
    ["python3", r"${heartbeat_tool}", "tick", r"${project}", "--json"],
    text=True,
)
payload = json.loads(out)
if payload.get("status") != "skipped" or payload.get("reason") != "disabled":
    raise SystemExit(f"expected disabled skip, got: {payload}")
PY

echo "[test] heartbeat tick skips outside active window"
python3 - <<PY
import json
from pathlib import Path
p = Path(r"${harness_dir}/heartbeat.config.json")
cfg = json.loads(p.read_text(encoding="utf-8"))
cfg["enabled"] = True
cfg["active_windows"] = [{"days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], "start": "00:00", "end": "00:00"}]
p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
python3 - <<PY
import json
import subprocess
out = subprocess.check_output(
    ["python3", r"${heartbeat_tool}", "tick", r"${project}", "--json"],
    text=True,
)
payload = json.loads(out)
if payload.get("status") != "skipped" or payload.get("reason") != "outside_active_window":
    raise SystemExit(f"expected outside-window skip, got: {payload}")
PY

echo "[test] heartbeat inbox pending has highest priority"
python3 - <<PY
import json
from pathlib import Path
cfg_path = Path(r"${harness_dir}/heartbeat.config.json")
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
cfg["enabled"] = True
cfg["active_windows"] = [{"days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], "start": "00:00", "end": "23:59"}]
cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

queue_path = Path(r"${harness_dir}/inbox/queue.json")
queue = {
    "version": 1,
    "items": [
        {
            "id": "pending-priority",
            "title": "pending should execute first",
            "status": "pending",
            "commands": ["bash .bagakit/long-run/check_and_resume.sh"],
            "meta": {},
        },
        {
            "id": "pending-secondary",
            "title": "second item",
            "status": "pending",
            "commands": ["bash .bagakit/long-run/check_and_resume.sh"],
            "meta": {},
        },
    ],
}
queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
python3 - <<PY
import json
import subprocess
from pathlib import Path

out = subprocess.check_output(
    ["python3", r"${heartbeat_tool}", "tick", r"${project}", "--json"],
    text=True,
)
payload = json.loads(out)
if payload.get("status") != "success" or payload.get("source") != "inbox" or payload.get("item_id") != "pending-priority":
    raise SystemExit(f"pending priority failed: {payload}")

queue = json.loads(Path(r"${harness_dir}/inbox/queue.json").read_text(encoding="utf-8"))
items = [i for i in queue.get("items", []) if isinstance(i, dict)]
lookup = {str(i.get("id")): i for i in items}
if lookup.get("pending-priority", {}).get("status") != "done":
    raise SystemExit("pending-priority should be marked done")
if lookup.get("pending-secondary", {}).get("status") != "pending":
    raise SystemExit("pending-secondary should remain pending")
PY

echo "[test] heartbeat idle flash ideas auto-picks and executes top-1"
python3 - <<PY
import json
from pathlib import Path
queue_path = Path(r"${harness_dir}/inbox/queue.json")
queue_path.write_text(json.dumps({"version": 1, "items": []}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
python3 - <<PY
import json
import subprocess
from pathlib import Path

out = subprocess.check_output(
    ["python3", r"${heartbeat_tool}", "tick", r"${project}", "--json"],
    text=True,
)
payload = json.loads(out)
if payload.get("status") != "success" or payload.get("source") != "flash":
    raise SystemExit(f"flash fallback did not execute: {payload}")
flash_file = payload.get("flash_file")
if not flash_file:
    raise SystemExit("missing flash_file in tick result")
flash_path = Path(flash_file)
if not flash_path.exists():
    raise SystemExit(f"flash file missing: {flash_path}")
ideas = json.loads(flash_path.read_text(encoding="utf-8")).get("ideas", [])
if not isinstance(ideas, list) or not (3 <= len(ideas) <= 5):
    raise SystemExit(f"expected 3~5 ideas, got: {len(ideas) if isinstance(ideas, list) else 'invalid'}")
PY

echo "[test] heartbeat rejects non-allowlisted commands"
python3 - <<PY
import json
from pathlib import Path
queue_path = Path(r"${harness_dir}/inbox/queue.json")
queue = {
    "version": 1,
    "items": [
        {
            "id": "allowlist-reject",
            "title": "reject command",
            "status": "pending",
            "commands": ["echo denied"],
            "meta": {},
        }
    ],
}
queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
python3 - <<PY
import json
import subprocess
proc = subprocess.run(
    ["python3", r"${heartbeat_tool}", "tick", r"${project}", "--json"],
    text=True,
    capture_output=True,
)
if not proc.stdout.strip():
    raise SystemExit(f"missing json output, stderr={proc.stderr}")
payload = json.loads(proc.stdout)
if payload.get("status") != "failed" or payload.get("reason") != "allowlist_reject":
    raise SystemExit(f"expected allowlist rejection, got: {payload}")
PY

echo "[test] heartbeat command timeout is enforced"
python3 - <<PY
import json
from pathlib import Path

cfg_path = Path(r"${harness_dir}/heartbeat.config.json")
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
guard = cfg.setdefault("guardrails", {})
allowlist = guard.setdefault("allowlist_prefixes", [])
if "bash -lc" not in allowlist:
    allowlist.append("bash -lc")
guard["command_timeout_seconds"] = 1
cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

queue_path = Path(r"${harness_dir}/inbox/queue.json")
queue = {
    "version": 1,
    "items": [
        {
            "id": "timeout-item",
            "title": "timeout command",
            "status": "pending",
            "commands": ["bash -lc \"sleep 2\""],
            "meta": {},
        }
    ],
}
queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
python3 - <<PY
import json
import subprocess
proc = subprocess.run(
    ["python3", r"${heartbeat_tool}", "tick", r"${project}", "--json"],
    text=True,
    capture_output=True,
)
if not proc.stdout.strip():
    raise SystemExit(f"missing json output, stderr={proc.stderr}")
payload = json.loads(proc.stdout)
if payload.get("status") != "failed" or payload.get("reason") != "command_timeout":
    raise SystemExit(f"expected timeout failure, got: {payload}")
PY

echo "[test] heartbeat lock prevents concurrent tick"
python3 - <<PY
import fcntl
import json
import subprocess
from pathlib import Path

lock_path = Path(r"${harness_dir}/heartbeat.lock")
lock_path.parent.mkdir(parents=True, exist_ok=True)
with lock_path.open("w", encoding="utf-8") as lock_file:
    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    out = subprocess.check_output(
        ["python3", r"${heartbeat_tool}", "tick", r"${project}", "--json"],
        text=True,
    )
payload = json.loads(out)
if payload.get("status") != "locked":
    raise SystemExit(f"expected locked status, got: {payload}")
PY

echo "[test] heartbeat mirrors to living-docs inbox when available"
mkdir -p "${project}/docs/.bagakit/inbox"
python3 - <<PY
import json
from pathlib import Path

cfg_path = Path(r"${harness_dir}/heartbeat.config.json")
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
cfg["enabled"] = True
cfg["active_windows"] = [{"days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], "start": "00:00", "end": "23:59"}]
guard = cfg.setdefault("guardrails", {})
guard["command_timeout_seconds"] = 900
cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

queue_path = Path(r"${harness_dir}/inbox/queue.json")
queue = {
    "version": 1,
    "items": [
        {
            "id": "mirror-run",
            "title": "mirror run",
            "status": "pending",
            "commands": ["bash .bagakit/long-run/check_and_resume.sh"],
            "meta": {},
        }
    ],
}
queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
python3 - <<PY
import json
import subprocess
from pathlib import Path
out = subprocess.check_output(
    ["python3", r"${heartbeat_tool}", "tick", r"${project}", "--json"],
    text=True,
)
payload = json.loads(out)
mirror_file = payload.get("mirror_file", "")
if not mirror_file:
    raise SystemExit(f"expected mirror_file when docs inbox exists: {payload}")
if not Path(mirror_file).exists():
    raise SystemExit(f"mirror file does not exist: {mirror_file}")
PY

echo "[test] heartbeat falls back to local inbox history when living-docs inbox missing"
rm -rf "${project}/docs/.bagakit"
python3 - <<PY
import json
from pathlib import Path
queue_path = Path(r"${harness_dir}/inbox/queue.json")
queue = {
    "version": 1,
    "items": [
        {
            "id": "fallback-run",
            "title": "fallback run",
            "status": "pending",
            "commands": ["bash .bagakit/long-run/check_and_resume.sh"],
            "meta": {},
        }
    ],
}
queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
python3 - <<PY
import json
import subprocess
from pathlib import Path
out = subprocess.check_output(
    ["python3", r"${heartbeat_tool}", "tick", r"${project}", "--json"],
    text=True,
)
payload = json.loads(out)
if payload.get("mirror_file"):
    raise SystemExit(f"mirror_file should be empty without living-docs inbox: {payload}")
history_file = payload.get("history_file", "")
if not history_file or not Path(history_file).exists():
    raise SystemExit(f"history_file missing after fallback tick: {payload}")
PY

echo "[test] heartbeat schedule add/list/render/remove"
python3 - <<PY
import json
import os
import subprocess
from pathlib import Path

tool = r"${heartbeat_tool}"
root = r"${project}"

def run(*args):
    return subprocess.check_output(["python3", tool, *args], text=True).strip()

at = json.loads(run("schedule-add", root, "--kind", "at", "--name", "one-shot", "--spec", "2026-03-01T10:30:00Z"))
every = json.loads(run("schedule-add", root, "--kind", "every", "--name", "every-half-hour", "--spec", "30m"))
cron = json.loads(run("schedule-add", root, "--kind", "cron", "--name", "cron-half-hour", "--spec", "*/30 8-22 * * *"))

items = json.loads(run("schedule-list", root, "--json")).get("schedules", [])
ids = {str(item.get("id", "")) for item in items if isinstance(item, dict)}
for created in (at, every, cron):
    if str(created.get("id", "")) not in ids:
        raise SystemExit(f"schedule missing from list: {created}")

render_at = json.loads(run("schedule-render", root, "--id", str(at["id"])))
render_every = json.loads(run("schedule-render", root, "--id", str(every["id"])))
render_cron = json.loads(run("schedule-render", root, "--id", str(cron["id"])))

if "at_instruction" not in render_at or "at -t " not in str(render_at["at_instruction"]):
    raise SystemExit(f"invalid at render payload: {render_at}")
if not Path(str(render_at.get("script_path", ""))).exists():
    raise SystemExit("at render script_path missing")

every_script = Path(str(render_every.get("script_path", "")))
if render_every.get("every_seconds") != 1800 or not every_script.exists() or not os.access(every_script, os.X_OK):
    raise SystemExit(f"invalid every render payload: {render_every}")

if "cron_line" not in render_cron or "*/30 8-22 * * *" not in str(render_cron["cron_line"]):
    raise SystemExit(f"invalid cron render payload: {render_cron}")
if not Path(str(render_cron.get("script_path", ""))).exists():
    raise SystemExit("cron render script_path missing")

run("schedule-remove", root, "--id", str(cron["id"]))
ids_after = {
    str(item.get("id", ""))
    for item in json.loads(run("schedule-list", root, "--json")).get("schedules", [])
    if isinstance(item, dict)
}
if str(cron["id"]) in ids_after:
    raise SystemExit("schedule-remove failed to remove cron schedule")
PY

echo "[test] doctor"
bash "${runtime_scripts_dir}/long-run-doctor.sh" "$project"

echo "[test] idempotent apply"
bash "${runtime_scripts_dir}/apply-long-run.sh" "$project"

echo "[test] python tool summary"
python3 "${runtime_scripts_dir}/long-run-features.py" summary "${harness_dir}/feature-list.json" >/dev/null

echo "[test] pass (${skill_root})"
