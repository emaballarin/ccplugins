# Round NNN — <one-line goal>

> Written by `/tml:round` on <YYYY-MM-DD>. Read by `/tml:analyze`, possibly in a
> different session, possibly by someone who did not design this study. Anything
> not written here cannot be checked later.

## 1. Goal and phase

**Goal** — <one sentence. If it needs an "and", split the round.>

**Phase** — `exploration` (insight: what matters, what interacts) ·
`exploitation` (one best configuration)

**Why now** — <what the previous round settled, or what `/tml:plan` ordered.>

## 2. Role assignment

| Hyperparameter | Role       | Range / value              | Notes         |
| -------------- | ---------- | -------------------------- | ------------- |
| `<name>`       | scientific | `{a, b, c}`                |               |
| `<name>`       | nuisance   | log-uniform `[1e-5, 1e-1]` |               |
| `<name>`       | fixed      | `<value>`                  | caveat → §2.1 |

### 2.1 Caveats introduced by fixing

Every fixed hyperparameter narrows the conclusion. Write the narrowing out:

- Fixing `<name> = <value>` means the conclusion reads "…**when `<name>` =
  `<value>`**", and does not extend to other values.

### 2.2 Conditional hyperparameters

<Knobs that exist only under some scientific values. Two conditional
hyperparameters sharing a name are **not** the same hyperparameter and get
separate search spaces — the learning rate under two optimisers is the standard
case.>

## 3. Regime

|                   |                                               |
| ----------------- | --------------------------------------------- |
| Concurrent trials | `<n>` → regime `high` / `low` / `serial`      |
| Execution         | `local` / `remote (<where>)`                  |
| Sampler           | `<QMCSampler / TPESampler / GridSampler / …>` |
| Sampler seed      | `<seed>`                                      |

**Desideratum sacrificed** — <which of: number of scientific values compared ·
width of the nuisance space · sampling density. And what that costs the
conclusion. In a `high` regime, "none".>

## 4. Studies

| Study | Scientific setting | Nuisance space | Trials |
| ----- | ------------------ | -------------- | ------ |
| `S1`  | `<name> = a`       | `{lr, wd}`     | `<n>`  |
| `S2`  | `<name> = b`       | `{lr, wd}`     | `<n>`  |

**Fixed across all studies** — `max_train_steps = <n>` (never swept), plus the
harness, the data, the eval protocol and the seed policy.

## 5. Configuration matrix

<One fully-resolved row per trial: trial id, every hyperparameter, the seed.
Machine-readable — CSV or JSONL alongside this file.>

## 6. Return manifest

Required back from every trial for `/tml:analyze` to work. **Remote rounds: this
is the load-bearing section** — an omission costs a re-run of the whole study.

| Field                 | Required | Gates                                         |
| --------------------- | -------- | --------------------------------------------- |
| `trial_id`            | ✅       | everything                                    |
| `params`              | ✅       | isolation plots, axis plots                   |
| `objective`           | ✅       | the comparison itself                         |
| `best_step`           | ⬜       | `max_train_steps` refinement                  |
| `curve`               | ⬜       | overfitting, late variance, saturation checks |
| `infeasible` + reason | ⬜       | infeasible-fraction diagnosis                 |
| `seed`                | ⬜       | trial-variance characterisation               |
| `wallclock_s`         | ⬜       | time-to-target pricing                        |

Ask for `curve` on **all** trials if storage permits; they are small and several
checks are impossible without them.

## 7. What would change the answer

<Stated before results arrive: what result would make this round's conclusion
wrong, and what would make it inconclusive. Written now so it cannot be written
to fit the outcome.>
