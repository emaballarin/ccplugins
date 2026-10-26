# Changelog

## 0.2.2 — 2026-10-26

### Added

- **`build.sh` holds `hypot` to an exponent gap of 69.** From that gap between the two exponents on, the Intel decimal library's `bid128_hypot` returns the larger argument without computing. `dm42sim` uses 69, the value Intel's own library writes as `35+34` from 2.0 Update 3 (April 2024) on, up to the current 2.0 Update 5; the fork's patches already give it. SwissMicros' prebuilt firmware library uses 68 (DM42PGM's `lib/hypot_fix.patch`). A fork pin with any other gap now stops the build with an error, where before it would have changed results without notice. Only the spellings `69` and `35+34` are accepted. The check reads the patched library source on every build, so caches built before 0.2.2 are checked too. A refused build also withdraws the ready stamp, so `build.sh --path` and `dm42sim.sh` stop using the binary until a build passes.

### Fixed

- **`sed` is listed** among the required tools, in `build.sh`, `/dm42:setup` and the README. The fork's library script always needed it, and `build.sh` now calls it as well.

### Verified

- **The check**: it accepts the pinned source (`69`), Intel's 2.0 Update 5 source (`35+34`) and `35 + 34`. It refuses 68, 35, `35 + 33`, `34+35`, `0105`, a missing or duplicated shortcut line, a missing file and two library trees, 12 cases in all. A real build on a cache copy patched to 68 stopped before compiling, left no build stamp, and `build.sh --path` then refused the binary it had been serving.
- **Smoke test**: 28 checks, OK.

### Install

- After updating, run `/dm42:setup` again. Only the compile step reruns.

## 0.2.1 — 2026-10-25

### Fixed

- **`TIME` and `DATE` crashed `dm42sim`** with a segmentation fault, in every build since 0.1.0. The core asks the emulator's clock for only part of the time and date, and passes `NULL` for the rest. The emulator wrote all three values regardless. It now fills in only what is asked for. The clock stays fixed at Thursday 01/01/2026 00:00: `TIME` gives 0, `DATE` 1.012026 (2026.0101 in YMD) and shows THU, and `DATE` then `DOW` gives 4.
- **Smoke test**: 28 checks, up from 25. The three new ones read `TIME` and `DATE`, in MDY and YMD, and all three fail on 0.2.0.

### Verified

- **The crash search**: every built-in command with an ASCII name (297 of them) was run through `cmd` on two starting stacks, 594 runs. The only crashes were `TIME` and `DATE`, and nothing hung.
- **The callbacks**: every call from the core to the emulator's callbacks that passes `NULL` was checked. Only the clock call wrote through one; the print callback ignores its arguments.

### Install

- After updating, run `/dm42:setup` again. Only the compile step reruns.

## 0.2.0 — 2026-10-24

A program that ran out of memory on a DM42n with the endless stack passed every test in 0.1.0. `dm42sim` had no Dynamic Stack Extension switch, so `NSTK` was refused, and its `cmd` let that refusal through without an error. Only setting flag 80 directly reached the endless stack, skipping the switch.

### Fixed

- **`cmd` and `text` stop on errors.** A command the calculator refuses with an error message now ends the script with an error event quoting it. Before, only a squeak counted, so _Big Stack Disabled_, _Divide by 0_ and _Invalid Data_ all passed in silence, contrary to `dm42sim.md`. To see the error, the core is compiled with a two-line patch (`scripts/sim/core_display.patch`): `display_error()` also records the error it shows. `build.sh` applies the patch to a copy of that file, leaving the downloaded source as fetched, and the patch is part of the build stamp.
- **`flag 80` is refused.** It is the stack mode. Set directly, `flag 80 1` skipped the Dynamic Stack Extension check: the device cannot reach that state, and a later `L4STK` restore fails in it with _Big Stack Disabled_. `flag 80 0` left extra levels on a 4-level stack. The error points to `config dynstack 1` with `cmd NSTK`, and to `cmd 4STK`.

### Added

- **`config dynstack|mxsing|mxovfl 0|1`**: the three switches of the DM42's Free42 Configuration menu (Dynamic Stack Extension, Singular Matrix Error, Matrix Overflow Error). They start off, as on a new calculator, and are set as DM42PGM sets them. Switching `dynstack` off returns an `NSTK` stack to `4STK`.
- **New `state` fields**: `depth` (stack levels) and `config` (the three switches).
- **Smoke test**: 25 checks, up from 18. It now covers error refusals, all three switches, and the stack under `NSTK` and back. It also covers two things that must not count as refusals: an `AVIEW` of an error's text, and a test's Yes or No. On the 0.1.0 build the five refusal and stack checks fail and the two guards pass. The Yes/No guard was added after a draft of this release reported every test as refused.
- **References**:
    - `rpn-semantics.md` explains the endless stack and `L4STK`: it records the mode, runs on four levels and restores the mode on return; the abandoned-run and _Big Stack Disabled_ exceptions are included.
    - `dm42n.md` covers the Free42 Configuration switches: where they live, their defaults, and what Matrix Overflow Error covers.
    - `dm42sim.md` covers the new action, the new fields, the patch, memory limits and a recipe for running under the endless stack.
- **`/dm42:rpn` step 4**: one run under the endless stack for a DM42 target, with `depth` checked against the promise.

### Verified

- Two regression suites were rerun on the new build:
    - 20 action scripts of a 252-step graphics program, against the 0.1.0 build: no differences beyond the new fields, and 9 of 9 frames byte-identical.
    - 10 endless-stack scripts, against a 0.1.0 build with Dynamic Stack Extension forced on: no differences beyond the new fields.

### Install

- After updating, run `/dm42:setup` again. The build stamp changed, so the wrapper refuses the 0.1.0 build until then. Only the compile step reruns; the downloaded core and the Intel library are reused.

## 0.1.0 — 2026-10-24

First release.

- `/dm42:rpn` (model-invoked): workflow for HP-42S-family programs, the DM42n first — reference, program text in house style, compile with a round trip, emulator runs over every input and exit path, independent verification, device hand-over.
- `/dm42:setup` (user-only): builds `dm42sim` from SwissMicros' Free42 fork 3.3.10 (commit `a7c705e`, the core under DM42PGM 3.26) with the DM42 extensions enabled, decimal arithmetic and the DM42n's function set, then smoke-tests it.
- `scripts/sim/`: `dm42sim` — action scripts in, JSON lines out; `compile` and `decode` for `.raw` files. Re-implemented headless after DM42PGM: the hi-res layer and its clearing rules, 2×2 drawing in the 200×120 mode, the core display restored after a menu drawn over a message, and F1–F6 as the menu keys while the top row keeps its own functions. Script mistakes, unreadable files, missing labels, refused commands and power-off end the run with an error event and exit status 2.
- `scripts/dm42sim.sh`: runs the built emulator from anywhere, or says that `/dm42:setup` is needed.
- `scripts/roundtrip.py`: catches program lines the text parser drops silently (`STO 5`, a typo), naming the source line; accepts the spellings the parser accepts and numbered listings.
- References: `rpn-semantics.md`, `dm42n.md`, `dm42sim.md`, each rule with its source.
- Validated on a 242-step graphics program: its 400×240 frame matches an independent 34-digit decimal model with 0 differing pixels (a negative control differs in 16,085), and `dm42sim compile` produces the same `.raw` as `txt2raw`.
