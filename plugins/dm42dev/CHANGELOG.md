# Changelog

## 0.1.0 — 2026-10-24

First release.

- `/dm42:rpn` (model-invoked): workflow for HP-42S-family programs, the DM42n first — reference, program text in house style, compile with a round trip, emulator runs over every input and exit path, independent verification, device hand-over.
- `/dm42:setup` (user-only): builds `dm42sim` from SwissMicros' Free42 fork 3.3.10 (commit `a7c705e`, the core under DM42PGM 3.26) with the DM42 extensions enabled, decimal arithmetic and the DM42n's function set, then smoke-tests it.
- `scripts/sim/`: `dm42sim` — action scripts in, JSON lines out; `compile` and `decode` for `.raw` files. Re-implemented headless after DM42PGM: the hi-res layer and its clearing rules, 2×2 drawing in the 200×120 mode, the core display restored after a menu drawn over a message, and F1–F6 as the menu keys while the top row keeps its own functions. Script mistakes, unreadable files, missing labels, refused commands and power-off end the run with an error event and exit status 2.
- `scripts/dm42sim.sh`: runs the built emulator from anywhere, or says that `/dm42:setup` is needed.
- `scripts/roundtrip.py`: catches program lines the text parser drops silently (`STO 5`, a typo), naming the source line; accepts the spellings the parser accepts and numbered listings.
- References: `rpn-semantics.md`, `dm42n.md`, `dm42sim.md`, each rule with its source.
- Validated on a 242-step graphics program: its 400×240 frame matches an independent 34-digit decimal model with 0 differing pixels (a negative control differs in 16,085), and `dm42sim compile` produces the same `.raw` as `txt2raw`.
