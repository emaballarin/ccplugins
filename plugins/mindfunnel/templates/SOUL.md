# SOUL.md: Who you're working with

> Copy this file to `SOUL.md` (or run `/mf:setup` which does it automatically
> if no existing `SOUL.md` is found) and fill in the sections below. This
> file describes *you* to the agent — your role, your workflow, your
> preferences, the things that trip you up. It's gitignored by default.

## Who

<!-- Name. Role. Field. 1-2 lines. -->
<!-- Example: "Senior ML researcher. Publishes in RL and representation
     learning. Based in <city>." -->

## Philosophy

<!-- 1-2 quotes or aphorisms that capture how you approach the work. -->
<!-- Example: "Turning the scaling knob is easy. Getting the maths right is
     subtle." -->

## How I work

<!-- Concrete behavioural notes — the rhythm of a normal interaction. -->
<!-- Examples:
  - One variable at a time. Run, compare in tables, decide.
  - "Let's try this just for fun" — thorough, curious. Symmetric exploration
    often leads to the best findings.
  - I run experiments myself. Edit the script, run it, paste the output.
    Defer to me for execution, especially long / remote runs.
  - I will edit files between messages. Watch for system reminders about
    file changes.
  - I will call out bullshit directly. When I say "you are still bullshitting
    me", STOP. Re-examine every assumption from scratch.
  - I will interrupt with corrections mid-stream. Listen immediately.
-->

## How to communicate with me

<!-- Tone and register preferences. What you find useful, what you find
     annoying. -->
<!-- Examples:
  - Don't mince words when asked for clarity. Be precise about what each
    step does and what assumptions it makes.
  - Don't be sycophantic. Match my curiosity and directness.
  - Negative results are valuable. "The model doesn't help here" is a valid
    finding. Log honestly, don't force positives.
  - Failures are useful results, not waste. Stay open to revisiting seemingly
    settled questions.
  - Don't over-explain tools and modes. I know them.
-->

## What to avoid

<!-- Specific anti-patterns you've hit before. -->
<!-- Examples:
  - Don't call design choices "bugs" unless they demonstrably are.
  - Don't say "cheating" for legitimate experimental results.
  - Don't propose "fixes" that require knowing things you wouldn't have in
    the real scenario.
  - Don't suggest scaling before exhausting structure.
-->

## Experimental workflow

<!-- The shape of a normal experimental loop. -->
<!-- Examples:
  - Short discussion → edit → run → paste results → interpret → next.
  - Plan mode only for structural changes. No unnecessary deliberation.
  - Decision criteria up-front. Before a run, list the possible outcomes
    and the next step each triggers.
  - HP sweeps: present as tables, identify the pattern, suggest ONE next
    experiment.
  - Bug forensics: trace the full causal chain before fixing. WHY, not just
    a fix.
-->

## Technical environment

<!-- Tools, libraries, paths, cluster info. Internal packages, private
     indexes, custom optimisers, cluster mount points, etc. -->
<!-- Examples:
  - Language: Python 3.X, run with `python -O`, usually from `src/`.
  - DL stack: PyTorch, JAX, … (whatever you use daily).
  - Internal libraries: `<your-lib>` at `<private-index-url>`.
  - Cluster: `<hostname>:/<path>`. Partition: `<name>`.
  - Shell: <bash|zsh|fish>. Alias quirks: <list what trips you up>.
-->
