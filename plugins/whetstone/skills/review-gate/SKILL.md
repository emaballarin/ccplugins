---
name: review-gate
description: Fresh-context review of a change against its stated intent, before the change is acted on. Use before a commit (not the per-iteration commits of an autonomous loop the operator started, such as `/ar:resume`), before a release, or before launching a run whose result will be acted on — whenever the change is more than a one-line tweak, and always for an audit script, a release, or a pipeline feeding an experiment. Hands the diff and a written intent, never the implementer's reasoning, to a fresh sub-agent with a defect checklist; every finding then gets an outcome. Training or evaluation pipeline diffs also get /tml:review.
---

# /ws:review-gate — a second reader before the change is acted on

The context that built a change shares its author's blind spots: it reads the
diff through the reasoning that produced it. The gate puts the change in front
of a reader with **fresh** context, who sees what was written and what was
asked for, and nothing in between. Scale it with blast radius: a one-flag tweak
skips it; an audit script, a release, or a change feeding an experiment never
does — except the per-iteration commits of an autonomous loop the operator
started (`/ar:resume`), which the loop's own measurement gates.

## 1. Scope

Take the first that applies, and state it in one line:

1. What the operator named — a commit range, a branch, a set of files.
2. In a git repository: before a commit, everything against `HEAD`
   (`git diff HEAD` plus untracked files from
   `git ls-files --others --exclude-standard`, as wholly new hunks); before a
   release or merge, everything since the merge base with the default branch. In
   a repository with no commits yet, everything against the empty tree —
   `git diff $(git hash-object -t tree /dev/null)` — plus untracked files.
3. Outside git: the files the task touched, whole. Say so — the reviewer then
   judges content, not a delta.

An empty scope is not a pass. Stop and say there is nothing to review.

## 2. Write the intent

In at most five lines, from the request as given: what the change must do, what
it must leave alone, and the observable condition that means it is done. Use
the request's terms. The intent describes the goal, never the route — no
account of how the change was built or why a choice was made. It is the
reviewer's only statement of what was asked for.

## 3. Dispatch one fresh reviewer

Spawn one fresh sub-agent — a new agent that starts with an empty context,
never a fork or any mode that carries this conversation over (in Claude Code:
`general-purpose`, never `fork`) — and give it exactly four things: the scope, the intent, the
checklist below, and the output format. Nothing else from the session — no
plan, no rationale, no earlier findings. Tell it to read whatever surrounding
code it needs to judge a hunk, and that it reports and edits nothing.

The reviewer applies every item to the whole scope:

1. **Intent mismatch** — the change does all of what the intent asks, and
   nothing it says to leave alone.
2. **Silent drops** — a file, artifact, feature, flag, row or case present
   before and gone now, without the intent asking.
3. **Masked failures** — exit codes swallowed by a pipe or `|| true`, a broad
   `except`, a check that prints FAIL and exits 0, a fallback that hides the
   error.
4. **Checks that cannot fail** — a test, audit or gate whose verdict is the
   same whatever the input.
5. **Quoting and splitting** — unquoted paths and variables, word splitting,
   glob surprises, shell-dialect assumptions, line endings.
6. **Unrun paths** — branches, handlers and flags the change adds that nothing
   exercised.
7. **Stale restatements** — docs, descriptions, changelogs, comments or version
   strings that repeat a fact the change altered.
8. **Run validity**, when a run follows — the flags, device, seeds, interpreter
   and environment the run will actually use; anything that silently changes
   the problem instance.

Output format, one line per finding:
`file:line — what breaks — failure scenario (input → wrong result) — blocker | should-fix | note`.
With no findings: "no findings", the files it read, and any checklist item it
could not assess.

## 4. Give every finding an outcome

Back in the main context, fix each blocker and should-fix, or say why not.
Dispute a finding only with evidence. When a fix changes behaviour beyond the
finding's own lines, dispatch a fresh reviewer on the new scope. Then go ahead
with the commit, release or run.

In the hand-off, one line per finding with its outcome — fixed, reported, or
disputed and why — or "reviewed: no findings" with the scope.

## Routing

- A training or evaluation pipeline diff — optimiser, data pipeline, precision,
  evaluation path — also goes through `/tml:review`, which adds the ML pitfall
  catalogue. It runs inline, so it complements this gate rather than replacing
  it.
- For slop and style, suggest `/ws:deslop` before this gate; the operator
  types it.
- For a second model's opinion, suggest `/codex:adversarial-review`; the
  operator types it.

## Done when

- The scope was stated and was not empty.
- The intent was written from the request, with no reasoning in it.
- One fresh reviewer applied every checklist item to the whole scope.
- Every finding has an outcome in the hand-off.
