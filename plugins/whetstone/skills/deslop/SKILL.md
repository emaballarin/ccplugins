---
name: deslop
description: A behaviour-preserving cleanup pass over the change under review — strips comment slop, defensive-check slop, type laundering, unrequested fallbacks and style drift from the diff before /code-review. Never repo-wide, never functional.
disable-model-invocation: true
allowed-tools: [Read, Edit, Glob, Grep, Bash]
---

# /ws:deslop — clean the diff before review

Clean only the change under review. Preserve behaviour absolutely.

## 1. Scope

Take the first that applies, and state it in one line before starting:

1. What the operator named — a commit range, a branch, a set of files.
2. On a branch other than the default (`origin/HEAD`, else `main`): everything
   since the merge base, `git diff $(git merge-base HEAD <default>)`.
3. Otherwise the uncommitted work: `git diff HEAD`.

Add untracked files (`git ls-files --others --exclude-standard`) to cases 2
and 3 as wholly new hunks — `git diff` never shows them. Changed hunks are the
only targets. The lines around a hunk are the standard it is judged against; the
pass never runs repo-wide.

## 2. Checklist

Inspect every changed hunk for:

1. **Comment slop** — comments a human maintainer would not write: narration of
   the next line, syntax explanation, prose that merely restates the code,
   history in comments ("now uses X instead of Y"). Docstrings and status
   comments on unfinished work are outside this item; the project's
   documentation conventions govern them.
2. **Defensive slop** — checks, `try`/`except` or `try`/`catch` blocks, `None`
   guards, `getattr`/`hasattr`/`.get(key, default)` on attributes and keys that
   always exist — abnormal for the surrounding module, or protecting only
   imagined states. Validation at a system boundary (user input, I/O, external
   APIs) and guards against silent data corruption are not slop. In numerical
   code this includes guards that mask an upstream fault instead of fixing it:
   `nan_to_num`, a clamp to `eps`, a broad `except` around a step that produces
   NaNs.
3. **Type laundering** — casts that assert a type rather than establish it:
   `as any`, `as unknown as T`, `typing.cast(Any, …)`, widen-to-`Any`-then-narrow
   flows, and `# type: ignore`, `# noqa` or `@ts-ignore` with no code and no
   reason.
4. **Needless indirection** — intermediate variables and one-use helpers that
   add no domain meaning, remove no duplication, and simplify no control flow.
5. **Unrequested fallbacks** — compatibility shims, aliases, retries and
   fallback branches with no named contract that needs them and no plan to
   remove them.
6. **Style drift** — naming, control flow, imports, formatting and idiom that
   conflict with the surrounding file.

## 3. Rules

1. **No functional edits.** If a cleanup could change behaviour, leave it and
   report it. Removing a guard, a `try`/`except` or a fallback (items 2 and 5)
   changes what happens on the path it guarded, so those are report-only unless
   the guarded state provably cannot occur.
2. **Fix inline only what is trivial and behaviour-neutral.** Everything else is
   noted for the author, with its `file:line`.
3. **Re-run what covers the touched code.** If any line other than a comment
   changed, run the smallest tests covering the touched files.

## 4. Report

One to three sentences: whether anything changed, and every non-trivial item
left for the author.

This pass is quality-only. Run it before `/code-review`, never instead of it —
correctness and safety still need that review.
