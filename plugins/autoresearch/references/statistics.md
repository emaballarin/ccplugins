# autoresearch — keep/revert statistics

The arithmetic that stops the loop banking noise or quietly gaming its own
scorer. Read this before deciding any iteration's verdict.

---

## Direction

`direction` in `ar.config.json` is `minimize` or `maximize`. Every comparison
honours it. Define the signed improvement of a candidate against the current best
once, and use it everywhere:

```
improvement = (best - candidate)   if direction == "minimize"
improvement = (candidate - best)   if direction == "maximize"
```

Positive improvement means better. Negative or zero is never a keep.

---

## Noise floor

Measured once when the run starts, from `baselineRepeats` repeats (default 5) of the
**unmodified** baseline:

- `baseline` — the median of the repeats. Median, not mean: one pathological run
  should not move the reference point.
- `noiseFloor` — the standard deviation across repeats, or the median absolute
  deviation when repeats are few or visibly skewed. MAD is the safer default at
  N=5.

Both are persisted in the config header and never recomputed mid-segment. A noise
floor that drifts with the run is not a floor.

**Degenerate case:** if `noiseFloor` comes out at exactly zero — a fully
deterministic harness — treat it as zero and keep on any strict improvement, but
record `confidence: null`. Do not divide by it.

## The keep threshold

```
keep  ⟺  improvement > noiseFloor × noiseFloorMultiple
```

with `noiseFloorMultiple` defaulting to 1.0. An improvement smaller than the
instrument's own scatter is not an improvement; it is a re-roll of the same
distribution. Keeping it banks noise into the branch and every later comparison
inherits the error.

---

## MAD confidence — advisory only

```
confidence = improvement / noiseFloor
```

| Tier       | Ratio       | Meaning                                                  |
| ---------- | ----------- | -------------------------------------------------------- |
| **Green**  | ≥ 2.0×      | Comfortably outside the noise. Keep.                     |
| **Yellow** | 1.0× – 2.0× | Real by the threshold, but fragile. Re-run across seeds. |
| **Red**    | < 1.0×      | Indistinguishable from noise. Discard.                   |

Record the tier on every result line and surface it in the status block. It
**never auto-discards** beyond the keep threshold already applied — it is there
to be read, and to trigger the seed re-run below. A tiering scheme that also
acted would double-count the same evidence.

---

## Borderline re-runs

When `1.0× ≤ confidence < 2.0×`, do not decide on one measurement. Re-run the
candidate across `borderlineSeeds` (default `[0, 1, 2]`):

```bash
for s in 0 1 2; do AR_SEED=$s bash ./.ar/benchmark.sh; done
```

Compare the **mean across seeds** against the baseline mean, and re-apply the
keep threshold to that comparison. Record every seed's value in the result line's
`seedMetrics`, not just the aggregate — a candidate that wins on mean while
losing on two of three seeds is a finding worth keeping in the record.

If the harness ignores `AR_SEED`, seed re-runs are meaningless: they will return
the same number three times and manufacture false confidence. Check that the
values actually differ; if they do not, say so and fall back to the single
measurement.

---

## Locked harness

`benchmark.sh`, `checks.sh`, `evaluator.py` and whatever emits the metric are
off-limits for the entire run. The reason is direct: an agent optimising a number
it is also allowed to define will, eventually and without intending to, improve
the number by weakening the measurement. Loosening a tolerance, dropping a hard
test case, or widening an early-stopping window all read as progress and are all
pure score inflation.

Enforce mechanically, not by good intentions — reject any diff touching a
`lockedPaths` entry (see `protocol.md` §2.3). If the harness genuinely needs to
change, that ends the segment: stop, change it deliberately, re-measure the
baseline and noise floor, and open a new segment. Metrics either side of a
harness change are not comparable and must never share a segment.
