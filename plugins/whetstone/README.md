# ws

**whetstone** — sharpen the thinking before the work, and the work before it
lands.

Four skills. One interviews you about a plan until nothing is left silently
assumed. Two hold tests to one bar — a gate as they are written, an audit for
the ones already there. One cleans a diff of AI slop before review.

## Install

```
/plugin marketplace add emaballarin/ccplugins
/plugin install ws@ccplugins
```

## Skills

| Skill            | When                                      | What it does                                                                                                                                                                                      |
| ---------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/ws:grill`      | Before committing to an approach          | Maps the subject as a design tree and works it in rounds, asking the whole settled frontier at a time with a recommendation on every question. Ends with the design, the open list, and one exit. |
| `/ws:test-gate`  | Automatically, whenever tests are written | Four questions, the junk-pattern check, red-before-green for regressions. Extends existing tests, never restructures them. Silent unless a test fails or the tests around it raise a concern.     |
| `/ws:test-audit` | When a suite needs pruning                | Audits and consolidates existing tests — low-value, implementation-coupled, duplicated — evidence first, then one approved batch. Campaign mode takes a whole subsystem.                          |
| `/ws:deslop`     | After writing, before `/code-review`      | Strips comment slop, defensive-check slop, type laundering, unrequested fallbacks and style drift from the diff. Behaviour-preserving; reports what it cannot safely fix.                         |

`/ws:test-gate` is the only model-invoked skill. The other three are
**user-only**: they never fire on their own, cost nothing in context, and start
only when you type them.

## `/ws:grill`

### How a round works

The **frontier** is every decision whose prerequisites are already settled — the
questions answerable now, without guessing at answers you have not given yet.
A round asks the entire frontier at once, waits, then recomputes: your answers
push the frontier outward and unblock what depended on them. The session ends
when the frontier is empty.

Every question carries a recommended answer and the one-line reason for it. A
question without one is research the agent has not done yet.

```
❓ **Q3** — **Noise floor before or after the harness is locked**: …

➡️ After. A floor measured against a harness you are still editing is measuring
   the edits.
```

### Two rules worth knowing before you use it

**Silence is not consent.** A question settles only when you answer it
explicitly — including an explicit _"your call"_. Where the work has to move on
regardless, the agent adopts its own recommendation as a **stated assumption**
and the question **stays open**, on a list restated at every round boundary and
again in the closing hand-off. An assumption keeps things moving; it never
closes anything.

**The frontier is fixed before the format is chosen.** Rounds are carried in
markdown by default. `AskUserQuestion` takes a whole round only when it fits
without distortion — four questions or fewer, each with two to four mutually
exclusive answers, and no option invented just to reach the widget's minimum of
two. An open question rendered as a menu anchors the answer, which is the exact
failure the skill exists to prevent. This rule is scoped to grilling rounds; it
says nothing about how `AskUserQuestion` is used anywhere else.

### Where it hands off

A grilling session produces understanding, not artifacts. It closes by naming
one exit:

| If the understanding is about                                      | Hand off to    |
| ------------------------------------------------------------------ | -------------- |
| Which experiment to run, and how to make the comparison fair       | `/tml:round`   |
| Where to sit on the speed↔quality frontier, and for how long       | `/tml:plan`    |
| Many measured iterations against one number under a locked harness | `/ar:start`    |
| A document an agent will read                                      | `/mf:author`   |
| Work now specified well enough to build                            | Implementation |

Those exits are suggestions, not dependencies — `ws` installs and runs on its
own.

## `/ws:test-gate` and `/ws:test-audit`

Two skills, one bar. `references/test-value.md` holds the value bar, the junk
patterns (a test that cannot fail, a mock that implements what it asserts, a
tolerance loose enough to pass a plausible bug, …), and the retention bar that
saves a test which only looks like junk. The gate applies it to a test being
written; the audit to tests that already exist.

**The gate extends; the audit consolidates.** While a test is being written,
every existing test keeps executing exactly what it did before — new tests, new
table rows, new fixtures and reused setup are fine, restructuring is not. Adding
an experimental condition and refactoring its tests in the same change leaves
you unable to tell which of the two broke, and turns discarding the experiment
into an un-refactoring. Consolidation waits for the audit, once the code has
settled.

**The gate notes what it will not fix.** Duplicated setup it had to leave, junk
in the neighbouring tests, several tests owning one contract: it reports them
at the end of the task and notes each one — in your `TESTS.md` if there is one,
in your to-do file for a concrete action item, else in `./.ws/test-notes.md`.
The audit starts from those notes and clears what it resolves.

**The audit asks before it edits.** It reads, records evidence for every
candidate, flags code that still looks experimental so you are reminded of its
state, proposes one batch, and waits. Every consolidated contract is
mutation-checked: break the production code on purpose, confirm the surviving
test goes red, restore it byte for byte.

## `/ws:deslop`

A second pass over what was just written, looking for what a human maintainer
would not have written: narrating comments, guards against states that cannot
occur, casts that assert a type instead of establishing one, fallbacks nobody
asked for, idiom that clashes with the file. It works on the diff only — the
uncommitted work, a branch since its merge base, or a range you name — and makes
no functional edits: anything that could change behaviour is reported, not
fixed. Docstrings are left to the project's own documentation rules.

It overlaps the built-in `/simplify` only on needless indirection; `/simplify`
looks for reuse and efficiency, `deslop` for the tells of generated code. Run it
before `/code-review`, never instead of it.

## Design notes

- **`/ws:grill` is read-only and stateless.** No files, no branches, no state
  directory. The open list lives in the conversation and is restated rather
  than persisted.
- **One model-invoked skill, three user-only.** `/ws:test-gate` must fire on its
  own whenever a test is written, or it gates nothing. `/ws:grill` changes how
  the conversation runs — a blast radius the size of the session. `/ws:deslop`
  and `/ws:test-audit` edit your code. None of these settings is permanent; a
  skill reached for constantly can flip.
- **The only state is the notes file**, and only when the gate has something to
  note. `ws` never touches `.gitignore`; whether `./.ws/` is committed is the
  project's call.
- **Facts are the agent's job.** Anything findable in the filesystem, git
  history, or a library's real signature gets looked up, never asked. Only
  decisions get put to you.

## Links

- Marketplace: [emaballarin/ccplugins](https://github.com/emaballarin/ccplugins)
- Changelog: [CHANGELOG.md](CHANGELOG.md)

## License

MIT. See [LICENSE](LICENSE) and [NOTICE](NOTICE) — `/ws:grill` is adapted from
the `grilling` skill in [mattpocock/skills](https://github.com/mattpocock/skills);
`/ws:test-gate`, `/ws:test-audit` and `/ws:deslop` from the `test-audit` and
`deslop` skills in [openclaw/openclaw](https://github.com/openclaw/openclaw).
