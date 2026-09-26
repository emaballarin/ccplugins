---
name: test-audit
description: Audit and consolidate an existing test suite — low-value, implementation-coupled or duplicated tests, duplicated setup, and the test-only production seams they keep alive. Evidence first, then one approved batch of edits. Campaign mode prunes a whole subsystem's test surface.
disable-model-invocation: true
---

# /ws:test-audit — prune and consolidate a test suite

Audits the tests in the scope the operator names: tests that re-assert source,
duplicate stronger proof, couple behaviour to implementation, or keep test-only
production seams alive — and the duplicated setup `/ws:test-gate` deliberately
left behind. Optimise for confidence, not deletion count. Continue a broad audit
as separate coherent batches.

The value bar, junk patterns, retention bar, and the notes file live in
`references/test-value.md`; read it first. **Campaign mode** prunes one
subsystem's whole test surface — every test file one package or area owns —
in one change; before starting one, read `references/campaign.md`.

## 1. Scope and seed

- The scope is exactly what the operator named.
- Read the root and scoped `AGENTS.md` / `CLAUDE.md` and `PROJECT.md` first.
- Seed the candidate list with every `ws:test-gate` entry in the notes file
  that falls inside the scope.

## 2. Discovery — read-only

Hunt for the junk patterns and for duplicated setup. For a broad scope, run
parallel read-only discovery lanes through Task subagents, split along
production-owner boundaries — core packages, plugins or extensions, apps and
scripts and tooling, plus one cross-cutting pattern sweep. Outside campaign mode,
prefer a few high-confidence candidates over a large speculative inventory.

Before judging a candidate, read the complete test and its production owner, the
owner's entry point, callers, callees, sibling implementations, overlapping
tests, CI routing, and relevant history. When the test claims dependency-backed
behaviour, inspect the dependency's source or types directly.

While reading production owners, flag code that looks **experimental or
unsettled** — behind an experiment flag or config switch, described as
experimental in comments, docs or commit messages, or still churning in recent
history. It stays in scope; it goes at the top of the report, saying what it is
and what state it looks to be in, because consolidating around a shape that may
not survive is premature.

## 3. Candidate evidence

Record every field before proposing an edit. A missing field means the
candidate is not ready:

- exact test name and location;
- what failure it can actually detect;
- non-test callers of the covered production or support seam;
- stronger remaining owner-boundary proof, or why no proof is needed;
- relevant history and the reason the test or seam exists;
- production or test-support deletion unlocked;
- risk and the focused validation command.

A setup-consolidation candidate also records the tests that share the setup, the
fixture scope and seed each one runs under, and the fixture that would absorb
it.

## 4. Report, then wait

Report the experimental flags, the candidates with their evidence, and the one
batch you propose. Then stop. Edit nothing until the operator approves the
batch; an approval covers that batch only, and the experimental items are
consolidated only if the operator says so.

## 5. Edit shape

Apply one coherent owner-boundary batch. Delete obsolete test-only exports,
globals, wrappers, and dead production paths instead of preserving aliases. Move
retained regressions to their canonical owners. Consolidate repeated assertions
into one generic contract, and duplicated setup into a shared fixture that keeps
each test's fixture scope and seed — a fixture shared at module scope shares its
state, which a per-test copy never did.

Prefer net-negative production LOC. Replacement tests that restate the same
implementation, and uncertain candidates converted into cleanup to raise the
deletion count, both lower confidence rather than raising it.

## 6. Validation

Leave the source and tests untouched while a test run is in progress in the
checkout.

1. Before editing, record the pass/fail state of every test the batch touches.
2. After editing, run the smallest owner and sibling tests.
3. For a removed source grep or plan assertion, run the executable script or dry
   run that owns the real contract.
4. For each consolidated contract, make one deliberate mutation of the
   production owner and confirm the keeper goes red, then restore the source
   byte for byte.
5. Run the project's formatter on the touched files, then `git diff --check`.
6. Run the full gate the project requires before a change lands.
7. Inspect `git diff --numstat`; report production and tooling separately from
   tests and test support.
8. Run `/code-review` on the result.

## 7. Landing and continuation

Commit, push, or open a PR only when authorised. Land one coherent batch at a
time; after landing, refresh from the current default branch and rerun
read-only discovery for the next high-confidence batch.

## 8. Notes and hand-off

In the notes file, remove the `ws:test-gate` entries this batch resolved (or
tick them, where the file uses checkboxes), and leave every other line alone.

Report:

- experimental code flagged, and what was decided for it;
- root cause and removed low-value categories;
- production owner simplifications;
- retained false positives and why they remain valuable;
- focused and full proof actually run;
- production versus test LOC;
- commit or PR state;
- named follow-ups.
