---
name: test-gate
description: Gate for every test being written or changed — four questions it must answer, the junk-pattern check, red-before-green for regression tests, and extend-don't-restructure for the tests already there. Use when adding tests for new code or an experimental condition, writing a regression test for a bug fix, or changing an existing test's assertions. Runs silently; speaks only for a test that fails the gate or for concerns about the surrounding tests, which it reports and notes rather than fixes. Do NOT use to audit, prune or consolidate an existing suite — that is /ws:test-audit, which the operator invokes.
---

# /ws:test-gate — a test lands only if it earns its place

Applies while tests are being written. The bar itself — the value bar, the junk
patterns, the retention bar, and where concerns are noted — lives in
`references/test-value.md`; read it before the first test of the session.

The gate is **silent**. A test that passes it gets nothing beyond the task's
normal summary. Speak only when a test fails the gate, or when the survey in
step 5 finds a concern.

## 1. Four questions

Before adding a test, answer four. A missing answer means the test is not added
yet:

1. What observable behaviour, invariant, or independent contract does it
   protect?
2. What credible regression makes it fail?
3. Why does existing coverage not already catch that failure? Each contract has
   one primary test owner at the strongest boundary; another layer needs its own
   distinct risk, such as a transport or lifecycle failure the owner cannot
   reach. Prefer a new row in an existing parametrised table, or an existing
   fixture reused as it is, over a near-duplicate test.
4. Does it need a production seam — export, flag, wrapper, injection hook — that
   no production caller needs? If yes, move the test to the real boundary
   instead.

## 2. Junk check

Check the test against every junk pattern. A match fails the gate unless the
retention bar names the contract it independently guards. A test that would
break under behaviour-preserving refactoring asserts implementation; rewrite it
at the owning boundary before landing it.

## 3. Regressions go red first

A bug regression test must fail on the pre-fix code for the intended reason, and
pass after the repair at the owner boundary. See it red: write the test before
the fix, or revert only the fix's production hunk, run the test, and restore the
hunk byte for byte — the file must end identical to how it was before the
revert. A regression test that never demonstrably failed proves the mock, not
the fix.

One regression at the owner boundary covers the bug; one scenario gets one test,
not one per layer it crosses.

## 4. Extend, don't restructure

Every existing test keeps executing exactly what it executed before. Within
that, extend freely: a new test, a new row in an existing table, a new fixture
or helper used only by new tests, a new optional parameter whose default leaves
every existing caller unchanged, and existing setup reused as it is.

Moving, merging, or rewriting existing setup is **consolidation**, and it
belongs to `/ws:test-audit`, later, once the code under test has settled. A
change that bundles a test refactor with the thing being tested cannot tell
which of the two broke, and an experiment that is discarded should leave with
one revert. The one exception is a restructure too trivial to change what any
existing test executes; name it in the hand-off.

Where extending leaves duplicated setup, keep the duplicate and note it in
step 5. Tests whose asserted behaviour the task deliberately changes are part of
the task, not of this rule.

## 5. Survey and note

Question 3 already put the tests around the contract in front of you. From
those — not a wider sweep, which is the audit's job — collect:

- junk-pattern matches in existing tests;
- duplicated setup, including any this change just left;
- several tests owning the same contract.

Edit none of them. Report them once, in one short block at the end of the task,
with `/ws:test-audit` as the suggested next step, and note each one as
`references/test-value.md` describes, skipping any already noted.

## Done when

- Every new or changed test has four answers and passed the junk check, or was
  kept by a retention contract named in the hand-off.
- Every regression test was seen red on the pre-fix code.
- Every existing test executes what it executed before, or the trivial
  restructure is named.
- Every concern the survey found is reported and noted.
