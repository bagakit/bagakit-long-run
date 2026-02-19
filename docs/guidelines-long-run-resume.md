---
title: Long Run Resume & Stop Contract (恢复循环与停止说明)
required: false
sop:
  - Treat `bash .bagakit/long-run/check_and_resume.sh` as the **resume command** (next-action SSOT); run it at the start of a session and after every detect/initializer/coding pass.
  - After finishing the current item (done/blocked), run resume and continue by following its output (do not guess the next action).
  - If you stop the loop at the end of a session, explain **why you are not continuing** in the `[[BAGAKIT]]` footer. If not fully done, include a short retrospective and the unblock/next step.
  - When this contract changes, update `references/*template*` + `scripts/validate-long-run.sh`, then regenerate `docs/must-sop.md`.
---

# Long Run Resume & Stop Contract

This doc defines the long-run loop behavior that should be injected into target projects via the managed AGENTS block and prompt templates.

## 1) Resume Script (Next Action SSOT)

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

Rule: **Do not guess the next step**. Always run resume and follow its output.

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
