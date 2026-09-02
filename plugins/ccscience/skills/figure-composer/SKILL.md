---
name: figure-composer
description: "Compose one publication-grade multi-panel figure. Entry from a one-line claim + data refs, OR from an existing figure via `derive_outline_task(png)`. Runs a per-figure loop: outline (12-col grid, per-panel ask + label_budget) → fan-out one Task subagent per panel (each loads `figure-style`) → tile + stamp letters → adversarial composite review with two-tier feedback (Tier-1 outline_revisions / Tier-2 per-panel violations) → regen affected panels, ≤3 rounds. Kernel exposes panel_task / compose_figure / compose_crops / composite_review_task / derive_outline_task / finalize_outline (import by absolute path). For one standalone plot use `figure-style`; for whole-paper figure ordering use `paper-narrative`."
license: Apache-2.0
---

# Figure Composer — narrative → panels → compose → adversarial loop

**Step 0.** Load `figure-style` alongside this skill — that is the design rules
(and `apply_figure_style()` + helpers). Each panel's `Task` subagent loads it
independently; you need it in context to write the outline and review the
composite.

## Loading the kernel

The deterministic helpers live in `kernel.py` next to this file. It is **not**
auto-injected — import it by absolute path in a Bash `python` heredoc (zero
import-time side effects; the only heavy import, PIL, is lazy inside
`compose_figure`):

```bash
python3 - <<'PY'
import importlib.util
K = "/ABSOLUTE/PATH/TO/figure-composer/kernel.py"   # this SKILL.md's dir + /kernel.py
spec = importlib.util.spec_from_file_location("fc_kernel", K)
k = importlib.util.module_from_spec(spec)
spec.loader.exec_module(k)
print([n for n in dir(k) if not n.startswith("_")])
PY
```

Every kernel call below assumes `k` is loaded this way. Each `python` invocation
is a fresh process, so re-import in each heredoc. `compose_figure` (and the
panel renders) need `pip install pillow` (+ matplotlib for the panels).

## Inputs

- **claim** — one sentence the figure makes true to a reader who reads nothing else.
- **data** — CSV/parquet file paths (or data refs) that ground every panel.
- **width_mm** — target venue's column width (common: 85–89mm single, 174–183mm double; check the venue guide).

## 0. Where this sits

`figure-composer` is the **outer tier**: make ONE multi-panel figure good. The
**inner tier** is `figure-style` (loaded by every panel Task subagent — and
load it yourself if you draw anything locally). The **outermost tier** is
`paper-narrative` — if this figure is part of a paper, run that FIRST: it decides
_which_ figure to make and hands you the claim. For a standalone figure, start at
step 1.

## Entry points (pick one)

- **From a claim:** you have a one-sentence claim and data refs → write the
  outline (step 1).
- **From an existing figure:** copy it into the workspace and build the
  extraction prompt with `derive_outline_task("figure.png")`. Then **either**
  `Read` the PNG yourself and emit JSON matching `figure_outline_schema()`, **or**
  dispatch one `Task` subagent to do it. **Pass the parsed JSON through
  `finalize_outline(outline)` before anything else touches it** — it forces
  `data_vid=None` on every panel, which pixels cannot encode and the model can
  only invent. The image is untrusted input and every string field is derived
  from it, so **review and edit** the outline, and fill in the real data refs,
  before step 2.

## 1. Narrative → panel outline

Produce a `panel_outline` (validate against `figure_outline_schema()`):

```json
{"claim":"…", "width_mm":180, "ncol":12, "row_heights_mm":[40,60,46,52],
 "panels":[
  {"letter":"a","role":"schematic","row":0,"col":0,"colspan":12, "chart_family":"schematic overview", "message":"…", "data_vid":null, "ask":"…"},
  {"letter":"b","role":"primary",  "row":1,"col":0,"colspan":7,  "chart_family":"scatter + trend", "message":"…", "data_vid":"…", "ask":"…"},
  …]}
```

Outline rules (figure-style §7.1):

- **a is the hook** — schematic/hero, full width, assumes zero reader context.
- **b carries the claim** — the chart that alone makes the sentence true.
- Remaining panels are evidence, ordered by how much they strengthen b.
- One row per sub-claim. 5–10 panels for a main-text figure. Use a 12-column
  grid for flexible colspans.

## 2. Fan-out (one Task subagent per panel)

Build each panel's brief with `panel_task(outline, letter, fig_label)`
(kernel.py). Each brief carries: the figure claim, the full neighbour list, the
panel spec, exact pixel dimensions (`panel_px`), and the instruction to load
`figure-style` and render at exactly w×h px with `transparent=True` and **no**
`bbox_inches`.

```bash
python3 - <<'PY'
# ... load k (see "Loading the kernel") ...
import json
outline = json.load(open("outline.json"))
for p in outline["panels"]:
    L = p["letter"]
    open(f"panel_{L}_task.txt", "w").write(k.panel_task(outline, L, "Figure 2"))
print("briefs:", [p["letter"] for p in outline["panels"]])
PY
```

Then launch **one `Task` subagent per panel, in parallel**. Each subagent's
prompt is that panel's brief (`panel_{L}_task.txt`); it loads the `figure-style`
skill, renders `panel_{L}.png` at the exact pixel size, runs figure-style's §9
render-then-verify, and returns its `figure_filename`. Collect the returned
paths into a `{letter: path}` dict.

## 3. Compose

```bash
python3 - <<'PY'
# ... load k ...
import json
outline = json.load(open("outline.json"))
paths = {p["letter"]: f"panel_{p['letter']}.png" for p in outline["panels"]}  # from the subagents
out_path, (W, H) = k.compose_figure(outline, paths, "fig.png", letter_case="lower")
print(out_path, W, H)
PY
```

`compose_figure` tiles the panel PNGs onto the grid and stamps bold panel
letters (case per venue) at each panel's (1.5mm, 1mm) corner.

## 3.5 Look before you review (vision self-QA)

The reviewer in §4 is expensive; a panel-letter stamped over a y-axis label or
a leader line crossing a neighbour's title is a wasted round. After compose,
**crop each panel out of the saved PNG, save each crop, and `Read` it** before
dispatching the reviewer:

```bash
python3 - <<'PY'
# ... load k ...
import json
from PIL import Image
outline = json.load(open("outline.json"))
img = Image.open("fig.png")
for L, box in k.compose_crops(outline).items():
    img.crop(box).save(f"fig_panel_{L}.png")   # then Read each crop
PY
```

Then `Read` each `fig_panel_{L}.png`. Run the `figure-style` §9.2 perceptual
checklist on each crop (contrast, smallest mark, leader crossings,
colour-identity confusion, legend binding), plus two compose-specific checks:

- **Seams / stamp.** Does the bold panel letter overlap any panel content?
  Does any panel's content bleed into the gutter or under a neighbour?
- **Resize artefacts.** `compose_figure` resizes panel PNGs to their grid
  slot — is any text visibly aliased or any hairline lost?

Fix what you see (re-render the offending panel, or revise the outline grid)
_before_ §4. The reviewer Task subagent will crop-and-look again independently;
this pass is so the obvious defects never reach it.

## 4. Adversarial self-review loop (two-tier, design rules held fixed)

Dispatch ONE `Task` subagent as the reviewer on the composite, its prompt built
by `composite_review_task(...)`; it returns JSON matching `review_schema()`
(which carries `outline_revisions`).

```
loop (max 3 rounds, floor 5→4→3):
  prompt = composite_review_task("fig.png", outline, prev_path, round, floor)
  review = <Task subagent(prompt) → JSON matching review_schema()>
  if review["editor_verdict"] in {accept, minor_revision} and 0 BLOCKER and ≤2 MAJOR: break

  # TIER 1 — outline-level
  if review["outline_revisions"]:
      apply revisions to `outline` (geometry, row-header titles, label_budget, panel set)
      affected = k.apply_outline_revisions(outline, review["outline_revisions"])
  else:
      affected = set()

  # TIER 2 — panel-level
  fixb = k.group_fixes_by_panel(review)     # BLOCKER/MAJOR only
  regen = affected | set(fixb)              # only these panels regenerate
  re-launch one Task subagent per L in regen with panel_task(outline, L) + fixb.get(L, "") +
      "do not over-correct: where the previous version was correct, keep it"
  recompose  # keep the prior round's PNG as prev_path
```

Convergence: stop when `outline_revisions` is empty AND findings are carve-out
exceptions to the previous round — that's the over-labelling signal.

## Anti-patterns

- Don't regenerate clean panels (invites regression). Don't read absolute
  violation counts (min-floor 5→4→3). Anchor-verify on the composite, not just
  per panel. Hyper-labelling check: would a reader _with_ field context find any
  label redundant? Strip it.
