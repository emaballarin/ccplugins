# HP-42S RPN: the semantics that decide whether a program is right

Each rule was read in the source or exercised in the cores in October 2026. Sources: **[F]** Free42 3.4.1 (`thomasokken.com/free42/upstream`), **[SM]** SwissMicros' fork 3.3.10 (`github.com/swissmicros/free42` @ `a7c705e`), **[M]** DM42 user manual (`technical.swissmicros.com/dm42/doc/dm42_user_manual.html`), **[L]** DM42 function list v2.0.2, 22/04/2025. DM42/DM42n specifics live in [dm42n.md](dm42n.md).

## Program text

- One step per line; `@` starts a comment outside a string; indentation is free. LF and CRLF compile to byte-identical `.raw` files.
- **The text parser skips any line it cannot read, and the compiler still succeeds** — `txt2raw`, the SwissMicros decoder and `dm42sim compile` alike. A typo vanishes from the program silently, so every compile ends with a round trip: `scripts/roundtrip.py` compares the source steps with the compiled listing.
- These ASCII spellings round-trip: `*` `/` `X^2` `CHS` `RDN` `X<>Y` `X<=Y?` `X<Y?` `X>Y?` `X=Y?` `X=0?` `X<0?` `RCL+` `RCL-` `RCL*` `RCL/` `STO+` `STO-`, and `X!=0?`, `X#0?` or `X≠0?` for the not-equal tests. Register, flag and label numbers need two digits: `STO 5`, `RCL 5`, `SF 5`, `FS? 5`, `LBL 1`, `GTO 1`, `XEQ 1`, `ISG 5`, `VIEW 5` and the like vanish without a word, so write `STO 05`, `LBL 01`; `FIX`, `SCI`, `ENG` and `SIZE` accept one digit, `TONE` takes one. An argument after a command that takes none is dropped too: `PSE 5` compiles as `PSE`. Round-trip any other spelling before relying on it.
- A text literal or command argument holds at most 15 characters (`char text[15]` in `arg_struct`) [F]. Variable and label names: at most 7 characters, case-sensitive (`GrMod` and `GRMOD` are different variables).
- Two number lines in a row are two separate entries; the second lifts the stack.

## Stack and stack lift

- Four levels, X Y Z T. A number entry or a plain `RCL` pushes — **unless stack lift is disabled**, and `ENTER` (like `CLX`) disables it: the next number entry or `RCL` overwrites X. So `t ENTER 3 ×` gives 3t and loses the copy of t. `t ENTER ENTER 3 ×` keeps t (Y = t, X = 3t); and an operation between `ENTER` and the number re-enables lift, so `t ENTER SIN X<>Y 3 ×` leaves Y = sin t, X = 3t.
- `RCL+ RCL- RCL× RCL÷` combine with X in place, without lifting; `STO+` etc. update the variable.
- `R↓` (`RDN`) moves Y→X, Z→Y, T→Z, X→T. `X<>Y` swaps.
- A test (`X<Y?`, `FS? n`, …) runs the next line when true and skips it when false.
- Comment the stack after every step whose effect is not obvious (`@ Y: row, X: column`); stack-order mistakes are the commonest silent bug.

## Flags

- **25, ignore the next error**: when a step errors with flag 25 set, the error is swallowed, flag 25 is cleared, and execution continues [F `core_main.cc`]. Idiom: `SF 25`, the risky step, `FC?C 25` → branch on failure (and clear the flag on success).
- **34/35 select the AGRAPH mode**, 2·f34 + f35: 0 OR, 1 copy, 2 AND-NOT (erase), 3 XOR [F `core_display.cc`]. They do not affect `PIXEL`, which always ORs.
- **42 GRAD, 43 RAD**; both clear means DEG. `SF`/`CF` refuse flags 36–80 with _Restricted Operation_ [F `docmd_sf`], so set or restore the angle mode with `DEG`/`RAD`/`GRAD`; `FS?` reads any flag.
- A program that changes flags restores them; save a flag's state in a local first (`0 FS? 25 1 LSTO "F25"`).

## Angle mode

`SIN`, `COS`, `TAN` and their inverses use the current mode; a reset leaves the calculator in DEG [F `hard_reset`]. A program computing in radians saves the mode (`0 FS? 43 1 FS? 42 2 LSTO "ANG"`), runs `RAD`, and restores with `DEG` or `GRAD` at the end.

## Variables and menus

- `LSTO` creates a local at the current call level: it shadows a global of the same name and is deleted at that level's `RTN`/`END` (verified: the user's own `X` survives a program that uses a local `X`). Working variables belong in locals.
- `MVAR` + `VARMENU` build an input menu from globals declared after a global `LBL`; `STOP` waits for R/S; `EXITALL` closes the menu. Give the label a distinctive name — two programs with the same global label collide.
- Matrices: `NEWMAT` (rows in Y, columns in X); matrix + scalar is elementwise; `INDEX` a variable, `STOIJ` takes I from Y and J from X and leaves the stack, `RCLEL` pushes the element, `STOEL` stores X [F]. `INDEX` on a local restores the previous index when the local goes.

## Keys and stopping

- While a program runs, **R/S and EXIT stop it**; any other key is queued (up to 15) and answers the next `GETKEY` at once [F `core_main.cc`].
- `GETKEY` **halts the program** on R/S, EXIT and Shift-EXIT, so no restore code after it runs. `GETKEY1` halts only on R/S, and R/S again resumes after it [F `core_keydown.cc`; L]. Restore everything that does not need the key before waiting.

## Graphics (131×16; the DM42 modes are in dm42n.md)

- `PIXEL`: X is the column, Y the row, both 1-based; coordinates are rounded half away from zero; a dot off the screen is ignored without error; **a negative X draws the whole column |X|, a negative Y the whole row |Y|** [F/SM `pixel_helper`]. Guard every coordinate that could go negative.
- `AGRAPH` draws the ALPHA register as 8-pixel columns (bit 0 at the top) with its top-left at row Y, column X, clipped at the edges, combined per flags 34/35 [F `draw_pattern`]. `255 XTOA` makes an 8-pixel column.
- Every `PIXEL` and `AGRAPH` call flushes the display [F `docmd_pixel`]: per-pixel loops dominate running time.
- After `PIXEL`/`AGRAPH` the message flag keeps the picture on screen when the program stops, until the next key.

## Arithmetic

- Decimal128: 34 significant digits, rounded half to even (Intel BID library) [F `core_phloat.cc`].
- Adding an inexact step repeatedly drifts: from −1 in steps of 1/n, the middle slice lands up to 8.8e-33 away from 0 for n ≤ 200 (more for larger n), and the count of values below 1 varies with n. Loop over integers and divide.
- `IP` truncates towards zero, `FP` is the fractional part; `IP(x + 0.5)` rounds half up for x ≥ 0.

## Performance

Count executed steps (`dm42sim` reports them): they are the portable measure. Time on the device also depends on which instructions run and on display flushes, so confirm speed there. Hoist loop invariants; replace per-row erase loops with a floating horizon (a per-column record of the highest row drawn, slices front to back) — in a 400×240 hidden-line drawing that took the step count from 35.4 million to 1.0 million.
