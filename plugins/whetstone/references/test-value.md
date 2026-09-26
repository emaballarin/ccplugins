# Test value — the shared bar

One bar for two skills: `/ws:test-gate` applies it to a test being written,
`/ws:test-audit` to tests that already exist. Each rule lives here once.

## Value bar

Tests justify their maintenance cost by protecting behaviour, a credible
regression, or an independently meaningful contract. A test that would break
under behaviour-preserving refactoring is asserting implementation, not
behaviour. The gate rejects a new one; in an audit, an existing one is suspect,
not automatically deletable.

## Junk patterns

The shared checklist: the gate rejects a new test that matches one, and audits
hunt for existing tests that do. A match fails unless the
[retention bar](#retention-bar) names the contract the test independently
guards.

- assertion-free coverage probes, including shape-, dtype- or type-only checks
  standing in for a value contract no other test owns;
- self-comparisons and identity copiers;
- copied fixtures, inventories, manifests, or export lists;
- exact source, import, or string greps;
- private predicate or call-shape tests duplicated at real boundaries;
- duplicate invocations of the same contract;
- replays of a shared helper's tests inside each of its callers;
- tests whose only purpose is preserving test-only exports, globals, or
  wrappers;
- dead production code whose only callers are tests;
- expected values produced by the helper or renderer under test, including
  golden values regenerated from the code they check;
- mocks that implement the asserted behaviour, or one identical mock standing in
  for different APIs;
- fixtures that supply the result, state, or ordering the code under test should
  produce itself, or persistence asserted against a store the path never writes;
- capability tests that restate a declared flag instead of exercising what the
  flag promises;
- negative controls that pass for an unrelated reason, such as a rejection from
  a different guard or one the production path never reaches;
- tolerances loose enough to pass a plausible bug: perturb the output by the
  smallest plausible error (a sign flip, a missing `N−1`, an off-by-one step)
  and the assertion must fail. `numpy.allclose`'s default `atol=1e-8` passes an
  all-zeros result against values near `1e-10`, and a bug's size scales with
  the input — a missing `N−1` moves a variance 1.5× at `n=3` and 0.1% at
  `n=1000`;
- names or fixtures that promise more than the input exercises — a "retires the
  window" test asserting the window was _not_ cleared, or a degenerate input
  that hides a plausible bug: square shapes hide a transpose, batch size 1 a
  wrong reduction axis, identity or symmetric weights `W` versus `Wᵀ`, zero-mean
  data a missing centring step.

## Retention bar

Keep a test when it independently enforces a public API, SDK, protocol, config,
migration, storage, security, platform, default, prompt-byte, generated
cross-language, package, release, or architecture contract. Also keep:

- call ordering when order is observable behaviour;
- regressions with a credible failure mode;
- source inspection when it is the cheapest independent guard: it fails when the
  contract changes (the user-facing key, byte, or path) and survives an
  identifier-only refactor;
- a numerical tolerance derived from the computation's precision — machine
  epsilon (`≈1.2e-7` for float32) times the error the computation accumulates —
  that still sits below the smallest plausible bug;
- a retained test that fails on the baseline: treat it as a possible product
  bug, reproduce it, and repair the owner rather than deleting it.

Static or slow is not a deletion reason. A test that resembles implementation
may still be the independent contract; prove otherwise before removing it.

## Noting concerns

The gate notes what it finds and the audit reads the same place, so a concern
outlives the session that found it. Pick the first that applies:

1. A file the project already keeps for test notes (`TESTS.md` or similar).
2. For a concern that is a concrete action item, a to-do file the project
   already keeps (`TODO.md`, `TO_DO.md`).
3. Otherwise `./.ws/test-notes.md`, created on first use. Leave it to the
   project whether it is committed or ignored.

One line per concern, in the file's existing list style: the date, the test
location(s), the pattern or concern, the suggested action, and the tag
`ws:test-gate`. A concern already listed is not added twice. The tag marks the
only lines either skill may edit — every other line in the file belongs to
someone else.
