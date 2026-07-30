# Scientific, nuisance, and fixed hyperparameters

Adapted from `L-PLAYBOOK`. This is the single most load-bearing idea in the
plugin: it is what turns "try a thing and look at the number" into an experiment
whose answer means something.

---

## 1. The three roles

For **a given experimental goal**, every hyperparameter is exactly one of:

| Role           | Definition                                                                    | In the study                                        |
| -------------- | ----------------------------------------------------------------------------- | --------------------------------------------------- |
| **scientific** | Its effect on performance is what you are trying to measure                   | Varied, and compared across its values              |
| **nuisance**   | Must be optimised over so that comparisons between scientific values are fair | Tuned separately **within each** scientific setting |
| **fixed**      | Held constant this round                                                      | Constant — and becomes a caveat on the conclusion   |

**The role is a property of the goal, not of the hyperparameter.** Activation
function is scientific in "is ReLU or tanh better here?", nuisance in "is the
best 5-layer model better than the best 6-layer model, allowing either
activation?", and fixed in "for ReLU nets, does adding normalisation here help?".
An agent that assigns roles from a lookup table rather than from the stated goal
has already made the experiment meaningless.

**Every fixed hyperparameter is a caveat.** Fixing `x = v` means the conclusion
reads "…when `x = v`", not "…". Write the caveat down when you fix it, because
it will not be obvious three rounds later.

---

## 2. Assignment procedure

1. **Name the goal in one sentence.** If it needs "and", it is two goals and
   wants two rounds (`study-design.md` §1).
2. **Identify the scientific hyperparameters** — the ones the goal is about.
   Usually one; rarely more than two.
3. **Everything else starts as nuisance.** This is the default, and with
   unlimited budget it is where you would stop.
4. **Demote nuisance → fixed, deliberately, under budget pressure.** Each
   demotion buys trials and costs generality. Demote the ones that interact
   _least_ with the scientific hyperparameters, and record the caveat.

The trade in step 4 is real in both directions. Tuning too many nuisance
hyperparameters risks tuning **none of them well enough**, which produces a
confident wrong answer — worse than a narrow right one.

---

## 3. Rules of thumb

These are defaults, overridden by the goal.

- **Optimiser hyperparameters are nuisance, almost always.** Learning rate,
  momentum, schedule parameters, Adam's betas. They interact with everything, and
  "what is the best learning rate for the current pipeline?" is not an insight —
  it changes with the next pipeline change anyway. There is also no _a priori_
  reason to prefer one value: they do not affect the cost of a forward or
  backward pass. Fix them only under resource pressure or with strong evidence of
  non-interaction.
- **The optimiser itself is scientific or fixed**, never nuisance. Scientific
  when the goal is to compare optimisers; fixed when prior rounds settled it, or
  when its training curves are easier to reason about, or when it fits in memory
  and the alternative does not. See `optimisers.md` §3.
- **Regularisation strength is nuisance; whether to regularise at all is
  scientific or fixed.** "No dropout vs dropout" is the scientific question;
  the dropout rate is the nuisance parameter tuned under each. Once dropout is
  adopted, its rate is nuisance forever after.
- **Architectural hyperparameters are usually scientific or fixed**, because they
  move serving cost, latency, and memory — you are not free to optimise them away
  silently. Depth especially.
- **Batch size is none of the three.** It is chosen once, for time-to-target, and
  then held fixed — see `tier-b-systems.md` B14. It is not a quality knob, and it
  is not swept inside a study.

---

## 4. Conditional hyperparameters

A hyperparameter that **only exists for some values of a scientific
hyperparameter** is conditional. Comparing Nesterov momentum against Adam makes
`optimizer` scientific, and introduces `{learning_rate, momentum}` under one
value and `{learning_rate, β₁, β₂, ε}` under the other.

**Two conditional hyperparameters that share a name are not the same
hyperparameter.** The `learning_rate` under SGD+momentum and the `learning_rate`
under Adam play a similar role and their good ranges typically differ by orders
of magnitude. Give them separate search spaces. This is the same class of error
as reading Adan's `β₂` as Adam's `β₂` (`optimisers.md` §1.2), and it is worth
being suspicious of any shared name across a conditional boundary.

Conditional hyperparameters are also the reason to prefer **one study per
scientific setting** over a single joint search space (`study-design.md` §2):
a joint space cannot cleanly express "these four knobs exist only when
`optimizer = adam`".

---

## 5. Recording the assignment

The assignment is an artifact, not a thought. `templates/study-spec.md` §2 is its
home, and it is what makes a round auditable later — including by whoever reads
the results without having designed the study, which is the normal case when
`/tml:analyze` runs on results it did not produce (`regime.md` §4).

A round whose role assignment was never written down cannot be checked for
fairness afterwards, because "was this nuisance parameter tuned under both
settings?" has no recorded answer.
