# dm42sim — the DM42 emulator

`dm42sim` runs SwissMicros' own Free42 core (fork 3.3.10, the core under DM42PGM 3.26), compiled with the DM42 extensions on and without `DM42_OLDHW` — the configuration the manual describes for the DM42n, with every Free42 function. So the virtual variables, the 200×120 and 400×240 graphics modes, `WIDTH`/`HEIGHT` following `GrMod`, and decimal arithmetic are live. What DM42PGM adds on top of DMCP is re-implemented headless where a program can see it: the display hooks, and the rule that keys 1–6 keep their own functions while a menu shows. The core is compiled as published but for a two-line patch (`scripts/sim/core_display.patch`): `display_error()` also records the error it shows, which is how a command refused with an error is reported; nothing the calculator does changes. `/dm42:setup` builds it.

## Commands

Call it through the plugin's wrapper `scripts/dm42sim.sh` (`/dm42:rpn` gives its full path), which finds the build and fails with a message when there is none for this plugin version.

| Command              | Does                                                                                                                                                  |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `run ACTIONS`        | runs an action script (a file, or `-` for stdin) and prints one JSON object per line                                                                  |
| `compile IN OUT.raw` | program text (or a `.raw`) to `.raw`, like `txt2raw`; **lines the parser cannot read are dropped silently**; a file with no program steps is an error |
| `decode IN.raw`      | `.raw` to a numbered listing on stdout, like `raw2txt`, empty programs left out                                                                       |

Check every compile with the plugin's `scripts/roundtrip.py PROGRAM [OUT.raw]`: it compiles, decodes and compares step by step, names the first source line that did not survive, and writes `OUT.raw` only when every step did. Exit status 0 OK; 1 a step was lost or misread; 2 the check could not run, with the reason (emulator not built, unreadable input, unwritable output, bad usage).

## Action script

One action per line. A line starting with `#` is a comment; a `#` after an action is part of its argument. The calculator starts from a hard reset: DEG, `GrMod` 0, no programs.

| Action                | Effect                                                                                                                                                                                                                                                                                                                 |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `load FILE`           | adds the programs in a text or `.raw` file after the existing ones. Text goes into a new program, as `GTO ..` makes, so a program stopped before a `load` does not resume                                                                                                                                              |
| `xeq LABEL`           | types XEQ, ALPHA, the label, ENTER — as a person would — and runs until the calculator is idle. An error when there is no such global label, and for one-letter labels A–J and a–e, which XEQ reads as local labels (on the calculator they are run from the XEQ menu)                                                 |
| `key K …`             | presses keys in order (names below), each run until idle                                                                                                                                                                                                                                                               |
| `run`                 | R/S                                                                                                                                                                                                                                                                                                                    |
| `continue`            | resumes a program that `maxsteps` stopped, with a fresh step budget                                                                                                                                                                                                                                                    |
| `cmd NAME`            | executes a built-in command by name (`cmd CLST`, `cmd RAD`); an error when the calculator refuses it, by a squeak or with an error message such as _Divide by 0_, which the error event quotes. A test's Yes or No is not a refusal. An error raised by a program line that `cmd SST` runs is one, and ends the script |
| `text STRING`         | types characters during ALPHA entry (UTF-8, so `text ΣX` works); an error outside ALPHA entry, and for `÷`, which the core's text input cannot type                                                                                                                                                                    |
| `var NAME NUMBER`     | stores a real number exactly (`1.5`, `-2E-3`) in a global variable; NAME is 1–7 ASCII characters                                                                                                                                                                                                                       |
| `flag N 0\|1`         | sets a flag directly, system flags included — test setup only; flags the core recomputes (30, and those mirroring a mode) may not keep the value. Flag 80, the stack mode, is refused. Set directly, it would skip the Dynamic Stack Extension switch, a state the device cannot reach. Use `config dynstack 1` and then `cmd NSTK`, or `cmd 4STK`                                                                        |
| `mode DEG\|RAD\|GRAD` | sets the angle mode                                                                                                                                                                                                                                                                                                    |
| `config NAME 0\|1`    | sets a switch of the DM42's Free42 Configuration menu, all off as on a new calculator: `dynstack` (Dynamic Stack Extension, which allows `NSTK`; switching it off returns an `NSTK` stack to `4STK`, as on the device), `mxsing` (Singular Matrix Error), `mxovfl` (Matrix Overflow Error)                             |
| `grmod N`             | stores N in `GrMod` exactly as `STO "GrMod"` does (modulo 4, 1 becomes 0)                                                                                                                                                                                                                                              |
| `devid N`, `vbat V`   | the values `DevID` and `Vbat` report (defaults 0 and 3.0)                                                                                                                                                                                                                                                              |
| `maxsteps N`          | caps each following action at N steps (default 10⁹); a capped action reports `"capped": true` with the program still running                                                                                                                                                                                           |
| `state`               | prints the full state                                                                                                                                                                                                                                                                                                  |
| `snap FILE [SCALE]`   | writes the screen as a PNG: the 400×240 LCD while hi-res graphics show, else the core's 131×16 display. `snaplcd` and `snapclassic` force one; FILE may contain spaces                                                                                                                                                 |

Keys: `SIGMA+ 1/X SQRT LOG LN XEQ STO RCL RDN SIN COS TAN ENTER X<>Y CHS E BSP UP 7 8 9 / DOWN 4 5 6 * SHIFT 1 2 3 - EXIT 0 . R/S +`, or `#N` for key code N (1–37); a shifted function is `SHIFT` then its key. As on the DM42, the top-row keys `SIGMA+` … `XEQ` keep their own functions while a menu shows, and **`F1`–`F6` are the menu keys**; `F1`–`F6` with no menu are front-end shortcuts and an error here.

## Output

Every action except `state` prints `{"action", "arg", "steps", "running", "getkey", "capped", "screen", "rows"}`: `steps` executed by that action, `getkey` true while the program waits at `GETKEY`/`GETKEY1`, `screen` either `"lcd"` (the hi-res layer is showing) or `"classic"`, `rows` the two text lines. A program stopped by an error shows the message in `rows` with `running` false.

`state` prints `x` `y` `z` `t`, `depth` (stack levels: always 4 in `4STK`; under `NSTK` any number, 0 included, and only the levels that exist among `x` `y` `z` `t` are printed), `lastx`, `alpha`, `angle`, `grmod`, `width`/`height` (the current graphics size), `running`, `getkey`, `screen`, `lit` (lit pixels on the current screen), `draws`, `total_steps`, `rows`, `menu` (the six labels while a menu shows, as the DM42 draws them, `*` when highlighted; empty otherwise), `cmdline` (the number being entered), `flags` (100 characters, flag 0 first), `config` (the three switches, 0 or 1), and `vars` (locals as `NAME@level`). Numbers come in full precision whatever the calculator's display settings: a period as radix mark, no digit separators, `E` before the exponent.

- `steps` counts instructions that ran to completion; the one that stops the program or waits (`STOP`, the final `RTN`, `GETKEY`) is not counted.
- `draws` counts drawing calls into the display layer: one per pixel, so a negative-coordinate `PIXEL` line across 400×240 counts 400.
- The classic snapshot is the core's 131×16 display. It includes the menu row when the core draws a menu there; the DM42 shows menus in a bar of its own, and the labels are in `menu`.
- `snaplcd` shows the hi-res layer as last drawn, even after text output has replaced it on the DM42's screen.

An `{"event": "error"}` line stops the script with exit status 2: an unknown action or key, a malformed argument, an unreadable file, a missing or one-letter label, a refused command or character, F1–F6 with no menu, or power-off (`SHIFT EXIT`). `compile` and `decode` report unreadable input, unwritable output and files without program steps the same way.

## Faithful, and not

Faithful: the calculator core of fork 3.3.10 with its DM42 extensions, decimal arithmetic, programs, keys and menus with the DM42's top-row rule, the hi-res layer and its clearing rules, `GrMod` 2 pixel doubling. The Intel decimal library is built with the fork's patches, so `hypot` treats the smaller argument as negligible from an exponent gap of 69; SwissMicros' prebuilt firmware library uses 68 (DM42PGM's `lib/hypot_fix.patch`, confirmed in its ARM code). Both are safe, since 51 suffices at 34 digits; they differ only at a gap of exactly 68, where 40 random cases gave identical results.

Not emulated — check on the device:

- speed (count steps instead), and the effect of `RefLCD`;
- DMCP's screens, the DM42 stack display and fonts (`rows` holds the core's two-line display), and what the LCD shows after a program ends in hi-res mode;
- timed displays: `SHOW`, `MEM` and the other displays that clear after a delay clear at once here;
- the DM42's direct letter keys in ALPHA entry (type with `text`), the F-key shortcuts without a menu, printing (discarded), and power-off;
- memory limits (`MEM` reports about 1 GB free): a program that leaves values on the stack, or builds data, in a loop never runs out here, so watch `depth` and the variables after it ends;
- the clock: the date is fixed at 01/01/2026 00:00 and the random seed at 42;
- which configuration a given unit runs: fork 3.3.10 may differ from its firmware, and the original DM42 leaves out `N→BS N→BD N→DS N→DD BS→N DS→N` from firmware 3.25 (manual §2.8.1) — they run here.

## Recipe: run a program and look at the result

```
load prog.42
mode DEG
# stops at the program's menu or first STOP: inspect "menu" and "rows"
xeq NAME
# inputs set directly here; they can also be typed with key and text
var HATX 300
# R/S; "getkey" turns true when the program waits for a key
run
state
snap out.png 2
key EXIT
# the calculator after the program: angle, grmod, vars
state
```

For a DM42 target, run it once more under the endless stack: `config dynstack 1` and `cmd NSTK` before `xeq`, then check `depth` in the last `state` against what the program's header says it leaves on the stack. It must not grow with the size of the run.

Open the PNG and look at it before trusting any count. When a result matters, compute the expected output independently — a few lines of Python with `decimal` at 34 digits, following the program step by step — compare it pixel for pixel or digit for digit, and run one negative control (a deliberately different input that must not match) so the comparison is known to discriminate.
