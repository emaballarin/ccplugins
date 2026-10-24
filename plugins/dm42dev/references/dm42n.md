# SwissMicros DM42 / DM42n specifics

Sources as in [rpn-semantics.md](rpn-semantics.md), plus **[PGM]** DM42PGM (`github.com/swissmicros/DM42PGM` @ `3270592`, `dm/dm42_fns.cc`). **The DM42 manual is authoritative for device behaviour**; where it and the fork's source differ, follow the manual and confirm on the device.

## The platform

- DM42n and DM42: 400×240 transflective memory LCD; DM42n Cortex-M33 at up to 160 MHz, DM42 Cortex-M4F at up to 80 MHz; decimal128 arithmetic [M, specification table].
- DMCP, SwissMicros' closed operating system, runs DM42PGM, an open front end around SwissMicros' open fork of Free42; DM42PGM carries patches for DMCP5, the generation the DM42n runs. As of 24/10/2026 the latest are DM42PGM 3.26 (15/12/2025) and fork 3.3.10 (14/11/2025), which DM42PGM's `main.h` names as its Free42 version. The manual gives the DM42n one specification with the DM42 "unless stated" [M §2.1].
- **DM42 and DM42n differ in six functions**: from firmware 3.25 the original DM42 leaves out `N→BS N→BD N→DS N→DD BS→N DS→N` for lack of space — they can be entered, but stop with _Function not avail._ — while "the DM42n still implements all Free42 functions" [M §2.8.1]. `dm42sim` is built that way (without `DM42_OLDHW`); which configuration a given unit's firmware uses is not visible from the published sources, so try the six on the device when they matter.
- Program files: `.raw` (the HP-42S byte format) through the USB disk; text to `.raw` with `txt2raw`, the SwissMicros online decoder, or `dm42sim compile`.

## Virtual variables [M §3.1; SM `core_aux.cc`]

| Name     | Access     | Value                                                                                                                                                                                                                                                                  |
| -------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GrMod`  | read-write | graphics mode: 0 = 131×16, 2 = 200×120, 3 = 400×240; stored modulo 4, with 1 stored as 0                                                                                                                                                                               |
| `ResX`   | read-only  | width of the current mode: 131, 200 or 400                                                                                                                                                                                                                             |
| `ResY`   | read-only  | height of the current mode: 16, 120 or 240                                                                                                                                                                                                                             |
| `RefLCD` | read-write | LCD refresh during program runs, a bitmask: 1 main area, 2 goose, 4 annunciators; 0 refreshes nothing ("maximize performance" [M §3.1.1]) except the `VIEW`/`AVIEW` message area, which always repaints; a negative value refreshes those zones once, leaving the mask |
| `DevID`  | read-only  | hardware model                                                                                                                                                                                                                                                         |
| `Vbat`   | read-only  | battery voltage                                                                                                                                                                                                                                                        |

- **Access them indirectly**, as the manual recommends [M §3.1.2]. Through the stack this needs no registers: `"ResX" ASTO ST X RCL IND ST X`; `"GrMod" ASTO ST X 3 STO IND ST Y`. The manual's own example goes through numbered registers (`"GrMod" ASTO 10 … 3 STO IND 10`). In the fork, any named `RCL`/`STO` that finds no real variable falls back to these, direct or indirect [SM `core_variables.cc`]; a real variable of the same name hides them.
- **Detect a DM42** without breaking on Free42 or Plus42: `SF 25 "ResX" ASTO ST X RCL IND ST X FC?C 25 GTO <not a DM42>`.
- `GrMod` persists after the program ends: save it, and restore it once the user has seen the picture (after a `GETKEY1`).

## Free42 Configuration [PGM `dm42_fns.cc`]

- SETUP → Settings → Free42 Configuration holds three switches: Dynamic Stack Extension (allows `NSTK`, the endless stack), Singular Matrix Error and Matrix Overflow Error. A calculator starts with all three off (`stat_config_ptr`). They live in RAM that survives a reset, not in the state file, so Load Clean State keeps them.
- With Dynamic Stack Extension on, a program that leaves values on the stack can run out of memory: see the endless stack in [rpn-semantics.md](rpn-semantics.md). Matrix Overflow Error acts in the linear-algebra routines, a matrix product for one, not in element-wise matrix arithmetic [F `core_linalg1.cc`]. `dm42sim` sets the three with `config`.

## Graphics modes [M §3.4; PGM; SM `core_display.cc`, `core_commands2.cc`]

- In mode 2 or 3, `PIXEL` and `AGRAPH` take columns 1…`ResX` and rows 1…`ResY`, with the same rounding and negative-coordinate lines as in the classic mode.
- Hi-res drawing goes to a full-screen layer: **the first `PIXEL` or `AGRAPH` after text clears the whole LCD**; `CLLCD` clears the whole LCD while hi-res is showing; any text output (`AVIEW`, a message, the stack) switches the screen back to text.
- Mode 2 draws every pixel as a 2×2 block on the 400×240 LCD.
- `WIDTH`/`HEIGHT` exist in the fork and return the current mode's size [SM `core_commands7.cc`], but the DM42 function list omits them [L]. On a DM42 use `ResX`/`ResY`; `WIDTH`/`HEIGHT` serve Free42 (always 131×16) and Plus42 (its window).

## Keys

While a menu is shown, **F1–F6 are the menu keys and the top-row keys Σ+ … XEQ keep their own functions** (unlike the HP-42S, where that row doubles as the menu keys) [PGM `no_menu_key`]. With no menu, F1–F6 are front-end shortcuts outside the calculator core — F1 help, F2 main menu, F4 volume, F5 stack layout and font, F6 font size [PGM].

## Only the device shows

Speed; the effect of `RefLCD`; DMCP's screens and its stack display; what the LCD shows after a program ends in a hi-res mode; power-off. `dm42sim` emulates the calculator core, not DMCP.
