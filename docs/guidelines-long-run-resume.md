---
title: Long Run Resume & Stop Contract (恢复循环与停止说明)
required: false
sop:
  - Preferred loop entry is `bash .bagakit/long-run/ralphloop.sh pulse --endless`; fallback resume command is `bash .bagakit/long-run/check_and_resume.sh`.
  - After finishing the current item (done/blocked), run resume and continue by following its output (do not guess the next action).
  - If you stop the loop at the end of a session, explain **why you are not continuing** in the `[[BAGAKIT]]` footer. If not fully done, include a short retrospective and the unblock/next step.
  - When this contract changes, update `references/tpl/*template*` + `scripts/validate-long-run.sh`, then regenerate `docs/must-sop.md`.
---

# Long Run Resume & Stop Contract

This doc defines the long-run loop behavior that should be injected into target projects via the managed AGENTS block and prompt templates.

## 1) Pulse Entry + Resume Script (Next Action SSOT)

Preferred command:

```bash
bash .bagakit/long-run/ralphloop.sh pulse --endless
```

This command always runs resume and, when no actionable row exists, auto-generates `.bagakit/long-run/endless_expand_prompt.md` for agent-driven plan expansion.

Fallback direct resume script:

The long-run **resume script** is:

```bash
bash .bagakit/long-run/check_and_resume.sh
```

It is the single source of truth for:
- whether harness + execution-table quality gates pass
- the top-ranked execution rows
- confidence/evidence signals used for ranking
- guidance for the next actionable item
- feature-list sync + suggested current item
- structured next-action contract (`.bagakit/long-run/next-action.json`)
- adapter diagnostics (for example `bagakit-ft` index rows vs collected rows)

Rule: **Do not guess the next step**. Always run resume and follow its output.

If resume reports no actionable rows:
- do not fallback to done/blocked rows as current target,
- first fix upstream mapping/data freshness (detect/table/index), then re-run resume.

## 2) Action Injection Requirement (Every Round)

After each detect/initializer/coding pass (especially after status changes like `done`/`blocked`):
1) run resume (`bash .bagakit/long-run/check_and_resume.sh`)
2) follow the suggested next action (initializer -> coding -> validate/doctor -> resume again)

This is what keeps long-run deterministic across sessions.

## 3) Stop Contract (End Of Session)

When you end a session and you are **not continuing the loop right now**, your final response must include, under `[[BAGAKIT]]`, an explicit explanation for why you stop.

Minimum footer format (peer lines):

```text
[[BAGAKIT]]
- LivingDoc: <...>
- LongRun: Item=<id|detect>; Status=<ready|in_progress|done|blocked>; Confidence=<0.00~1.00>; Evidence=<...>; Next=bash .bagakit/long-run/check_and_resume.sh
- LongRunStop: Reason=<done|blocked|paused>; Retro=<if not done: why can't fully complete the plan + what's needed to finish/unblock>
```

Guidance:
- If the work is fully complete: `Reason=done` and state what is done + how you verified it.
- If not complete: you MUST add a brief retro (what prevented completion, and what would unblock/finish it).
- Even when stopping, keep `Next=bash .bagakit/long-run/check_and_resume.sh` so the next session can resume deterministically.
