# Execution regime — parallelism, location, and what you are allowed to conclude

`L-PLAYBOOK` was written against a study service running tens to hundreds of
concurrent trials. Most pipelines this plugin will meet are not that. Ported
verbatim, its advice prescribes experiments that cannot be run; ported by
guessing, it becomes folklore. So the regime is **established first, explicitly**,
and the procedure branches on it.

Establish the regime at the start of `/tml:round` and `/tml:plan`. It is three
questions, and none of them is answerable by reading the code.

---

## 1. Question 1 — how many trials can run concurrently?

| Regime     | Concurrent trials | Consequence                                                              |
| ---------- | ----------------- | ------------------------------------------------------------------------ |
| **high**   | ≳ 20              | `L-PLAYBOOK` applies as written                                          |
| **low**    | 2–19              | Fallbacks below; conclusions narrow                                      |
| **serial** | 1                 | Fallbacks below, plus Bayesian optimisation becomes genuinely attractive |

Ask for the number; do not infer it from GPU count, because a trial may need
several devices and a queue may cap what a person is willing to occupy.

**What changes in the low and serial regimes** — every one of these is a
documented fallback from `L-PLAYBOOK` itself, not an invention:

- **Fewer scientific values per round.** Compare two, not six. This is the
  desideratum to sacrifice first (`study-design.md` §4), because a narrow
  conclusion is still a conclusion, whereas an unfairly-tuned comparison is not.
- **Fewer nuisance hyperparameters, more of them fixed** — and each demotion
  written down as a caveat (`hyperparameter-roles.md` §1).
- **Grid search becomes acceptable in 1–2 dimensions.** `L-PLAYBOOK` permits it
  there explicitly. It does **not** become acceptable in higher dimensions, where
  `L-BERGSTRA12`'s result — grid's failure is the rule rather than the exception
  — governs.
- **In the serial regime, Bayesian optimisation is attractive earlier**, because
  its whole advantage is using previous trial results to choose the next one, and
  that advantage is largest when trials are sequential. It costs interpretability
  (§2).
- **Say what got weaker.** A round run at 6 trials instead of 60 does not produce
  the same claim more cheaply; it produces a weaker claim. Record which
  desideratum was cut.

---

## 2. Sampling algorithm follows from the phase and the regime

**Exploration defaults to quasi-random** — a randomly-shifted low-discrepancy
sequence, i.e. jittered shuffled grid search — for five reasons that all matter
during exploration and stop mattering during exploitation:

1. Non-adaptive sampling means the objective can be **changed post hoc** without
   re-running anything: best-at-any-point, best-at-end, a different metric.
2. It is **statistically reproducible** across implementations and versions.
3. Uniform coverage makes **search-space boundary diagnosis** meaningful
   (`diagnostics.md` §2) — an adaptive sampler may have neglected a region for
   reasons that have nothing to do with its quality.
4. Running `n` trials in parallel or in sequence gives **statistically identical**
   results, unlike adaptive algorithms.
5. Infeasible/divergent points do not confuse it.

Anecdotally it is hard for an adaptive algorithm to beat quasi-random search
given **2× its budget**, especially at high parallelism. `Grade` —
`measured-elsewhere` with `source-uncertainty`; `L-PLAYBOOK` states this as
experience and footnotes the counterexamples.

**Exploitation defaults to Bayesian optimisation / TPE.** Adaptivity is what you
want once the space is refined and you no longer care about interpreting it.

### 2.1 Concretely, in Optuna

If the operator uses Optuna — verified present in its samplers reference:

| Phase                | Sampler                                        |
| -------------------- | ---------------------------------------------- |
| Exploration          | `optuna.samplers.QMCSampler` (low-discrepancy) |
| Exploitation         | `optuna.samplers.TPESampler`                   |
| 1–2 dims, low regime | `optuna.samplers.GridSampler`                  |
| Baseline / fallback  | `optuna.samplers.RandomSampler`                |

This is the entire two-phase prescription, one line each, in a library already in
use. TPE is adaptive and therefore an **exploitation** tool: reaching for it
during exploration silently forfeits all five properties above. If a
low-discrepancy sampler is genuinely unavailable, pseudo-random uniform is an
acceptable substitute and is slightly less efficient; grid is not, above two
dimensions.

---

## 3. Question 2 — where does it run?

**Local** — the pipeline, the trials and the analysis are on the same machine.
Nothing special.

**Remote** — trials run on a cluster, a queue, or a rented machine, and results
come back. Then `/tml:round` must emit a **self-contained study bundle**, because
the thing that runs the trials cannot ask follow-up questions. The bundle lives
at `./.tml/rounds/NNN/` and contains:

- the study spec (`templates/study-spec.md`),
- the **configuration matrix** — one row per trial, fully resolved, with seeds,
- a launch stub the operator adapts to their scheduler,
- a **return manifest**: exactly which artifacts must come back.

The return manifest is the load-bearing part, because the cost of discovering an
omission is a re-run of the whole study. Default contents, per trial: the
best-so-far metric and the step at which it occurred; the final metric; the full
metric-vs-step series for at least the best few trials; an infeasibility flag
with its reason (diverged / NaN / OOM / crashed); the resolved hyperparameters;
the seed; and wall-clock. Ask for the curves for **all** trials if storage
permits — `diagnostics.md` §5 cannot be run without them, and they are small.

---

## 4. Question 3 — did this plugin design the round?

`/tml:analyze` must work on results it did not produce: someone else's sweep, an
old export, a run from before the plugin existed. In that mode there is no study
spec, so:

- **Do not fabricate the role assignment.** Ask which hyperparameters the
  question is about; everything else is treated as nuisance-or-fixed-unknown, and
  the fairness question (`diagnostics.md` §1) is answered "cannot be determined"
  rather than "yes".
- **Ingest whatever exists.** `templates/results-example.jsonl` is the shape the
  analysis expects; a CSV or a tracker export is coerced into it. Required per
  trial: an identifier, the hyperparameters, and the objective. Everything else
  is optional and its absence disables specific checks — say which.
- **Report the disabled checks.** An analysis missing the curves cannot detect
  problematic overfitting or late-training variance; that is a stated limitation
  of the verdict, not a silent omission.

Analysis-only mode is the common case for a first contact with a pipeline, and it
is not degraded mode — it just has a narrower set of answerable questions.
