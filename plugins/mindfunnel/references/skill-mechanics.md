# Skill mechanics

The skill-specific branch of `/mf:author`: what changes when the document being written is a skill — frontmatter, the invocation choice, and router skills. Everything else about writing it is the universal reference in that skill's `SKILL.md`.

## Frontmatter

A skill is a directory containing a `SKILL.md` whose YAML frontmatter carries:

- **`name`** — must equal the directory name. This is what the human types after the plugin prefix: a skill at `skills/spinup/` inside plugin `mf` is invoked as `/mf:spinup`.
- **`description`** — the skill's top-level context pointer. Who reads it depends on the invocation choice below.
- **`allowed-tools`** _(optional)_ — a list restricting the skill to a tool subset. Omit it to inherit the session's tools. A read-only skill that declares `[Read, Glob, Grep]` cannot silently start writing.
- **`disable-model-invocation`** _(optional)_ — `true` makes the skill user-only. See below.

Bundled material sits beside the `SKILL.md` (`skills/<name>/…`) when only that skill uses it, or at the plugin root (`references/…`, `templates/…`, `scripts/…`) when several skills share it. Reference it as a bare path token — `references/ledger.md` — rather than a relative link, so the reference stays legible from wherever the skill is installed.

## Invocation

Two choices, trading the two loads:

- A **model-invoked** skill keeps a `description` the agent can see, so it fires autonomously — and other skills can reach it. You can still type its name: model-invocation always _includes_ user reach; a description only ever adds agent discovery, it never removes the human's. That description is a context pointer forced to stay loaded at all times — permanent context load in exchange for discoverability. A model-invoked skill whose content is all reference is also one home for shared reference: another skill can invoke it, so material needed by several skills lives in one place. Mechanics: omit `disable-model-invocation`, and write a model-facing description carrying the trigger branches (the pointer rules in the parent skill apply in full).
- A **user-invoked** skill strips the description from the agent's reach: only the human typing its name can invoke it, and no other skill can. Zero context load, but it spends cognitive load — you are the index that must remember it exists. Mechanics: set `disable-model-invocation: true`, and rewrite the `description` as **human-facing** — a one-line summary of what the skill is for, with trigger lists stripped, since no model reads it.

Pick model-invocation only when the agent must reach the skill on its own, or another skill must. If it only ever fires by hand, make it user-invoked and pay no context load.

Two further tests, both worth applying before defaulting to model-invocation:

- **Side effects.** A skill that mutates the filesystem, creates branches, or writes outside a scratch directory is a poor autonomous trigger — the human should drive it. Reach for user-only.
- **Interaction mode.** A skill that changes _how the conversation runs_ rather than what one task produces has a blast radius the size of the whole session. A task skill that misfires leaves a visible, revertible artifact; an interaction skill that misfires rewrites the exchange. Reach for user-only.

Shared reference that two user-invoked skills both need can live in neither — with no agent-visible descriptions, neither can fire the other. Push it to a plain file outside the skill system, reachable by a pointer from both.

## Splitting by invocation

The invocation cut of splitting — the sequence cut lives in the parent skill. Split off a model-invoked skill when you have a distinct leading word that should trigger it on its own (a trigger word you actually use in your prompts), or when another skill must reach it. You pay context load for the new always-loaded description, so that independent reach has to be worth it.

## Router skills

When user-invoked skills multiply past what you can remember, that piled-up cognitive load is cured by a **router skill**: one user-invoked skill that names the others and says when to reach for each, so the human has one name to remember instead of many. It can only hint, never fire them — user-invoked skills have no agent-visible description, so nothing but the human can reach them.

A router is the one document that goes stale invisibly. A skill it never mentions, or one it still routes to after a rename, is a router that lies. Re-read it whenever a user-reachable skill is added, renamed, removed, or changes what it is for.
