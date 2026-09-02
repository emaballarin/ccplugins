# Changelog

All notable changes to the `ws` (whetstone) plugin are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

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
