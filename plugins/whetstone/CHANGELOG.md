# Changelog

All notable changes to the `ws` (whetstone) plugin are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## 0.2.0 — 2026-09-26

### Added — three skills for the work itself, from OpenClaw

`ws` widens from "sharpen the thinking before the work" to "…and the work
before it lands". Three skills adapted from `test-audit` (with its
`CAMPAIGN.md`) and `deslop` in [openclaw/openclaw](https://github.com/openclaw/openclaw)
(MIT), `.agents/skills/` at `f61e10a`. See [NOTICE](NOTICE).

- **`/ws:test-gate`** — model-invoked. Gates every test as it is written: four
  questions it must answer, the junk-pattern check, red-before-green for
  regression tests. Silent unless a test fails the gate or the tests around it
  raise a concern.
- **`/ws:test-audit`** — user-only. Audits and consolidates an existing suite,
  evidence first and one approved batch at a time. Campaign mode, for one
  subsystem's whole test surface, lives in `references/campaign.md`.
- **`/ws:deslop`** — user-only. A behaviour-preserving cleanup pass over the
  change under review, before `/code-review`, never instead of it.
- **`references/test-value.md`** — the value bar, junk patterns, retention bar
  and notes-file rule, shared by both test skills so each rule has one home.

Deliberate deviations from the source, test skills:

- **One skill split in two.** The source is one model-invocable skill with three
  modes. Here the authoring gate is model-invoked, because it must fire on its
  own whenever a test is written; audit and campaign are user-only, because
  they delete tests and production seams. They share one reference file.
- **Extend, don't restructure.** The source's gate says to "consolidate
  duplicated setup in the same change". Here every existing test keeps
  executing what it executed before; the gate may add tests, table rows,
  fixtures and optional parameters, and reuse setup as it is, but moving,
  merging or rewriting existing setup is left to the audit. A change that
  bundles a test refactor with the thing being tested cannot tell which broke,
  and a discarded experiment should leave with one revert. Aligns with the
  "Respect scope" baseline in `mf`'s `templates/AGENTS.md`.
- **Survey and notes (new).** The gate reports junk patterns, duplicated setup
  and over-multiplied contracts it sees in the tests it already read, fixes
  none of them, and notes each one — in an existing `TESTS.md`-style file, else
  a project to-do file for concrete action items, else `./.ws/test-notes.md`.
  The audit seeds its candidates from those notes and clears the ones it
  resolves.
- **Approval before edits.** The source's audit reports evidence and then
  proceeds; here it reports and waits for the operator to approve one batch.
  Campaign mode waits the same way after its layer plans.
- **Experimental code flagged (new).** The audit covers exactly the scope it is
  given, but reports code that looks experimental or unsettled at the top, as a
  reminder, and consolidates it only on an explicit yes.
- **Setup consolidation in the audit**, which the source's audit did not
  cover, guarded by fixture scope and seed, a before/after pass/fail record,
  and a mutation per consolidated contract (from the campaign's preservation
  review).
- **Numerical code.** One new junk pattern — a tolerance loose enough to pass a
  plausible bug — with its retention counterpart, a tolerance derived from the
  computation's precision. Shape/dtype-only checks and degenerate inputs are
  folded into existing patterns as examples. Three OpenClaw-flavoured patterns
  (provider-local replays, receipt/admission fixtures, delivery flags) are
  generalised.
- **Removed:** Vitest runners, `check-changed.mjs`, `$openclaw-testing`,
  `$crabbox`, `$openclaw-pr-maintainer`, the `scripts/pr` flow, the
  `src/`/`packages/`/`extensions/` lane names, and shrink-only line-cap
  baselines. The Telegram campaign's lessons are kept, unnamed. `$autoreview`
  becomes `/code-review`.

Deliberate deviations from the source, `/ws:deslop`:

- **Diff scope** for commit-to-main workflows: an operator-named range, else the
  branch since its merge base, else the uncommitted work — plus untracked
  files, which `git diff` never shows. The source assumes a PR branch against
  `origin/main`.
- **Docstrings and status comments are exempt** from comment slop; the
  project's documentation conventions govern them. Unexempted, the pass would
  strip exactly the one-line docstrings `mf`'s `templates/AGENTS.md`
  baseline requires.
- **Boundary validation and corruption guards are exempt** from defensive slop;
  guards that mask an upstream numerical fault (`nan_to_num`, a clamp to `eps`)
  are added to it.
- **Language-neutral type laundering**, with Python forms beside the TypeScript
  ones; the Oxlint note is removed.
- **Guard, `try`/`except` and fallback removals are report-only** unless the
  guarded state provably cannot occur — the source's own no-functional-edits
  rule, made explicit for the items it bites hardest.
- **Re-run tests** covering the touched files whenever a non-comment line
  changed (new).
- **User-only**, matching how the source is invoked (`$deslop`, by name).

`/ws:grill` is unchanged. The README's "read-only and stateless" design note now
describes `/ws:grill` alone.

## 0.1.3 — 2026-09-23

Housekeeping — coordinated marketplace version alignment alongside the `ccsci`
0.8.0 release (the new `paper-review` skill). Nothing in this plugin was edited.
No skill logic changed.

## 0.1.2 — 2026-09-02

Housekeeping — coordinated marketplace version alignment alongside the `mf`
guidance update and the `ccsci` 0.7.0 release. Nothing in this plugin was
edited. No skill logic changed.

## 0.1.1 — 2026-08-06

Formatter pass over `README.md` and `skills/grill/SKILL.md` (table alignment and
list indentation only) plus coordinated marketplace version alignment. No skill
logic changed.

## 0.1.0 — 2026-08-06

First release. One skill, `/ws:grill`.

Adapted from the `grilling` skill in [mattpocock/skills](https://github.com/mattpocock/skills)
(MIT). The design tree, the frontier, the round structure, the recommendation
attached to every question, and the facts-are-yours / decisions-are-theirs split
are all from the original. See [NOTICE](NOTICE).

Four deliberate deviations from the source:

- **Frontier-before-carrier.** The frontier is computed and written down before
  a display format is chosen, so no widget's cardinality limit can shrink the
  question set.
- **A hard carrier test for `AskUserQuestion`.** The tool caps at four questions
  of two-to-four options each, and cannot express an open question at all —
  `options` has a hard minimum of two, so an open question forces you to invent
  a menu, which anchors the answer. Markdown is therefore the default carrier;
  the tool takes a whole round only on three enumerable conditions. Scoped
  explicitly to grilling rounds, so it does not contradict general
  `AskUserQuestion` usage, or `/tml:plan`'s narrower rule for a single framed
  decision.
- **Silence is not consent, enforced.** A question settles only on an explicit
  answer. Where work must proceed, the agent adopts its recommendation as a
  stated assumption and the question **stays open**, tracked on an open list
  restated at every round boundary and in the closing hand-off. This aligns with
  `/tml:plan` hard rule 1, which already states `Silence is not consent` for the
  operating-point decision.
- **Named exits.** The original ends when the frontier empties; this one closes
  with the settled design, the open list, and one recommended hand-off to
  `/tml:round`, `/tml:plan`, `/ar:start`, `/mf:author`, or implementation.

User-only (`disable-model-invocation: true`): it changes how the conversation
runs rather than what one task produces, so it costs zero context load and
starts only when invoked by name.
