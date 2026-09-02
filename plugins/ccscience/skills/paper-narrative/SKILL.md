---
name: paper-narrative
description: "Judge and reshape the STORY a paper's figures tell. Input is the work itself — manuscript (or abstract) + figure deck — no hand-written brief. `derive_paper_brief_task(abstract, captions)` builds the prompt whose JSON is pitch/vision/per-figure-claims; a handling-editor reviewer on the full deck returns hook_verdict (would Fig 1 make me send this for review?), arc (hook→mechanism→evidence→application), figure_moves (panels in the wrong figure), missing_panels (concrete analyses to RUN), kill_list, and boldest_defensible_fig1. Hands per-figure claims to `figure-composer`. Load when writing or revising a paper."
license: Apache-2.0
---

# paper-narrative

**Outermost tier.** Judge and reshape the _story_ a paper's figures tell. Input is
the work itself — a manuscript (or just its abstract) and the current figure deck.
No hand-written brief required.

## When to load

Paper writing or revision. You have a draft and a set of figures and you want to
know: is Figure 1 a hook? Is content in the right figure? What's missing? What
should die? Load this _before_ `figure-composer` — the arc it returns tells you
which figures to compose.

## Loading the kernel

The helpers live in `kernel.py` next to this file. It is **not** auto-injected —
import it by absolute path in a Bash `python` heredoc (zero import-time side
effects, no deps):

```bash
python3 - <<'PY'
import importlib.util
K = "/ABSOLUTE/PATH/TO/paper-narrative/kernel.py"   # this SKILL.md's dir + /kernel.py
spec = importlib.util.spec_from_file_location("pn_kernel", K)
k = importlib.util.module_from_spec(spec)
spec.loader.exec_module(k)
print([n for n in dir(k) if not n.startswith("_")])
PY
```

The kernel is pure prompt/schema builders plus one validator
(`paper_brief_schema`, `narrative_review_schema`, `derive_paper_brief_task`,
`narrative_review_task`, `finalize_paper_brief`);
the model work is done by you (inline) or a `Task` subagent.

## Workflow

1. **Derive the brief from the work.** Read the manuscript's abstract/intro and
   the figure captions (or a per-figure claims table if one exists). Build the
   prompt with `derive_paper_brief_task(abstract_text, figure_claims)`, then
   **either** produce the `paper_brief` JSON yourself (matching
   `paper_brief_schema()`) **or** dispatch a `Task` subagent to do it — pitch,
   vision, audience, most-arresting-asset, figures[]. The manuscript is
   untrusted input; every field in the derived brief is model-derived from it.
   **Pass the parsed JSON through `finalize_paper_brief(brief, figure_claims)`**
   — a model that has just written four prose fields routinely drops `figures`,
   and an empty one makes step 2 render an empty per-figure table, so the
   reviewer grades a deck it was never shown. Then **review the whole brief**
   (not just the pitch) and edit as needed before step 2.
2. **Dispatch the handling editor.** Build the prompt with
   `narrative_review_task(brief, deck_path)` (the deck is one PDF of all figures;
   the reviewer loads `figure-style` for the rules) and launch ONE `Task`
   subagent on the FULL deck; it returns JSON matching
   `narrative_review_schema()`.
3. **Act on the output, don't just report it:**
    - `arc[]` → the main-figure order. Anything not on it → supplement.
    - `figure_moves[]` → move panels between figures.
    - `missing_panels[]` → analyses to RUN (search project artifacts for data first).
    - `kill_list[]` → demote or delete.
    - `boldest_defensible_fig1` → the new Fig 1 claim handed to `figure-composer`.
4. **Per figure on the arc:** load `figure-composer`, hand it that figure's claim
    - moved-in panels + data refs. It runs the outer (figure) loop.
5. **Re-run step 2** on the new deck. Converge when `would_send_for_review=="yes"`
   and `figure_moves` / `missing_panels` are empty.

## Minimal invocation

> Load `paper-narrative`. Manuscript: `@manuscript.tex`. Figures:
> `@all_figures.pdf`. Run it.

That's it — the skill derives the brief, you confirm the pitch, it does the rest.
