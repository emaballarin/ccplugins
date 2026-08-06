---
name: grill
description: A relentless, round-based interview that stress-tests a plan, design or decision against its own design tree until nothing is left silently assumed.
disable-model-invocation: true
allowed-tools: [Read, Glob, Grep, Bash, Task, AskUserQuestion]
---

# /ws:grill — interview a plan until nothing is assumed

Interview relentlessly until you and the operator reach a shared understanding
of what is being built. Map the subject as a **design tree**: every decision
branches into the decisions that hang off it.

This skill produces **understanding**, not artifacts. It writes nothing, changes
nothing, and does not begin the work. It ends by handing off.

## The frontier

The **frontier** is every decision whose prerequisites are already settled — the
questions answerable _now_, without guessing at answers you have not heard yet.
A question whose answer depends on another question still open in this round
belongs to a _later_ round, not this one.

Work the tree in **rounds**. Each round asks the whole frontier, then waits.

## The round

### 1. Compute the frontier, and write it down

Recompute the frontier from everything settled so far, and state its size before
anything else: _"Frontier this round: 6 questions."_

**The frontier is fixed before a carrier is chosen.** It is never trimmed,
merged, or deferred to fit a display format. If the frontier does not fit the
carrier, the carrier loses.

### 2. Ask the whole frontier, each question with a recommendation

Every question carries your recommended answer. A question without one is
research you have not done yet — do it first.

```
❓ **Q1** — **<question title>**: <body; may be several paragraphs, may include
options>

➡️ <your recommended answer, and the one-line reason it is your recommendation>
```

### 3. Wait

Do not proceed to the next round, and do not begin any work, until the operator
answers.

### 4. Recompute

Each round of answers reshapes the tree: settled decisions push the frontier
outward and unblock what depended on them. Return to step 1.

## Carrying a round

**This rule governs grilling rounds only.** It is a scoped specialisation, not a
general policy on `AskUserQuestion` — outside a round, and in every other skill,
the tool's own usage guidance applies unchanged.

**Markdown `❓`/`➡️` is the default carrier.** It is the only one that carries an
open question, multi-paragraph framing, more than four questions, and a single
reply that answers several at once.

`AskUserQuestion` takes the **whole** round only when all three hold:

1. The entire frontier this round is **four questions or fewer**.
2. Each question has **two to four mutually exclusive answers**, nameable in
   five words or fewer.
3. **No option had to be invented to reach the minimum of two.** If you
   manufactured a second option, the question is open — a fabricated menu
   anchors the answer, which is the failure this skill exists to prevent. Carry
   the round in markdown.

Put the recommendation first and label it `(Recommended)` — that is the `➡️`,
preserved.

Side-by-side `preview` is the one capability markdown lacks. When a question
turns on comparing concrete artifacts the operator needs to _see_ together, that
earns the tool — but the round must still pass all three tests. Otherwise stay
in markdown and inline the artifacts as fenced blocks.

**One round, one carrier, one call.** Never split a frontier across two calls or
two channels. Frontier questions are independent in their _prerequisites_, but
an operator reading Q7 routinely revises their answer to Q2 — whole-round
visibility is load-bearing, and answering a four-question widget blind to the
remaining five destroys it.

## Settling a question

**Silence is not consent.** A question settles only on an **explicit** answer.
Explicit delegation — _"3 and 5: your call"_ — is an answer. A non-response is
not, and neither is an answer that addressed a neighbouring question.

When work must move past an unsettled question, adopt your `➡️` recommendation
as a **stated assumption** and say so in one line. **The question stays open.**
An assumption is a way to keep moving, never a way to close a question.

Maintain an **open list** across the whole session:

- Restate it at every round boundary, above the new frontier.
- Restate it in the closing hand-off, marked as what the next step inherits.
- A question leaves the list only when the operator answers it. Nothing else
  removes it — not an assumption, not elapsed rounds, not the work having
  succeeded under it.

## Facts are yours, decisions are theirs

Finding **facts** is your job, never the operator's. When a frontier question
needs a fact from the environment — the filesystem, git history, a config, a
library's actual signature — go and get it. Never ask for something you could
look up.

Do not block on a lookup. A running exploration is an unsettled prerequisite, so
only the questions _downstream_ of it wait; ask the rest of the frontier now.
Where a lookup is broad enough that parallelism pays, dispatch a subagent
instead of serialising it — optional, never mandatory.

The **decisions** are the operator's. Put each one to them and wait.

## Ending

The session ends when the frontier is empty: every branch of the design tree
visited, nothing left silently assumed.

Close with three things:

1. **The settled design** — what was decided, in the operator's own vocabulary.
2. **The open list** — every question still unanswered, and the assumption
   currently standing in for each.
3. **One recommended exit**, not a menu:

   | If the understanding is about | Hand off to |
   | --- | --- |
   | Which experiment to run, and how to make the comparison fair | `/tml:round` |
   | Where to sit on the speed↔quality frontier, and for how long | `/tml:plan` |
   | Many measured iterations against one number under a locked harness | `/ar:start` |
   | A document an agent will read | `/mf:author` |
   | Work that is now specified well enough to build | Implementation, directly |

Do not act on the understanding — including the exit — until the operator
confirms it.

## Done when

- Every round asked the full frontier, and no frontier was trimmed to fit a
  carrier.
- Every question carried a recommendation and its reason.
- Every settled question was settled by an explicit answer; every unsettled one
  is on the open list with its standing assumption named.
- The closing hand-off names the settled design, the open list, and one exit.
