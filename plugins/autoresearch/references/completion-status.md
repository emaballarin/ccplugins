# Completion status

End every action-skill run with a single terminal **status token** on the last
line of the reply, so a human — or the unattended `ar-loop.sh` driver — can tell
at a glance what happened without parsing the whole message. This is the skill
_invocation's_ outcome; it is separate from, and does not replace, the experiment
state in `ar.jsonl` or the skill's own output (status block, report, sentinel).

One of:

- **DONE** — the work completed, with evidence (the printed status block, the
  written report, the committed or reverted iteration).
- **DONE_WITH_CONCERNS** — completed, but list the concerns: a flaky harness, a
  seed that disagreed, a measurement you could not fully trust.
- **BLOCKED** — could not proceed. State the blocker and what was tried.
- **NEEDS_CONTEXT** — missing information or an unmet prerequisite. State exactly
  what is needed (e.g. the `benchmark.sh` handover, a missing `ar.config.json`).

At an escalation point — repeated failures, an unverifiable or destructive step,
or scope you cannot confirm — stop and report in this shape rather than pressing
on:

```
STATUS:         BLOCKED
REASON:         <one line>
ATTEMPTED:      <what you already tried>
RECOMMENDATION: <the concrete next step you would take or ask for>
```

The token caps the reply; it is additive, never a substitute for the skill's
normal deliverable.
