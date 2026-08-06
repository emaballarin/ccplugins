# ws

**whetstone** — sharpen the thinking before the work.

One skill. It interviews you about a plan, a design, or a decision until nothing
is left silently assumed, then hands off. It writes nothing and builds nothing.

## Install

```
/plugin marketplace add emaballarin/ccplugins
/plugin install ws@ccplugins
```

## Skills

| Skill       | When                             | What it does                                                                                                                                                                                      |
| ----------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/ws:grill` | Before committing to an approach | Maps the subject as a design tree and works it in rounds, asking the whole settled frontier at a time with a recommendation on every question. Ends with the design, the open list, and one exit. |

`/ws:grill` is **user-only**. It never fires on its own, costs nothing in
context, and starts only when you type it.

## How a round works

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

## Two rules worth knowing before you use it

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

## Where it hands off

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

## Design notes

- **Read-only and stateless.** No files, no branches, no state directory. The
  open list lives in the conversation and is restated rather than persisted.
- **User-only on purpose.** A skill that changes how the conversation runs has a
  blast radius the size of the session, unlike a task skill whose misfire leaves
  a visible, revertible artifact. That is the reasoning; it is not permanent. If
  it turns out to be reached for constantly, the flag flips.
- **Facts are the agent's job.** Anything findable in the filesystem, git
  history, or a library's real signature gets looked up, never asked. Only
  decisions get put to you.

## Links

- Marketplace: [emaballarin/ccplugins](https://github.com/emaballarin/ccplugins)
- Changelog: [CHANGELOG.md](CHANGELOG.md)

## License

MIT. See [LICENSE](LICENSE) and [NOTICE](NOTICE) — `/ws:grill` is adapted from
the `grilling` skill in [mattpocock/skills](https://github.com/mattpocock/skills).
