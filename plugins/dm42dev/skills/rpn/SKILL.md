---
name: rpn
description: HP-42S-family RPN programs, the SwissMicros DM42n first (also DM42, Free42, Plus42). Use when writing, porting, reviewing or debugging a calculator program (program text such as a .42 file, or a .raw file), converting between text and .raw, or running a program here in the DM42 emulator.
---

# /dm42:rpn — HP-42S-family programs, DM42n first

The program will run on a real calculator, where a silent mistake costs a reflash and a wasted run. Every step below exists so that the first run on the device is the last one: the parser drops lines without a word, stack lift turns one wrong `ENTER` into a plausible wrong result, and a `GETKEY` that halts skips the code meant to clean up.

## Steps

1. **Load the reference.** Read `${CLAUDE_PLUGIN_ROOT}/references/rpn-semantics.md` before writing or reviewing a single step; also read `${CLAUDE_PLUGIN_ROOT}/references/dm42n.md` whenever the program targets a DM42/DM42n or draws (`PIXEL`, `AGRAPH`, `GrMod`, virtual variables). Done when you can name, for this program, every place stack lift matters, every flag and mode it changes, and every way it can stop or wait.

2. **Write or review the program text.**
    - Header comment: what it does, the devices it targets, how to run it, what it changes in the calculator and what it restores.
    - One step per line, comments aligned, and the stack (`@ Y: row, X: column`) after every step whose effect is not obvious.
    - Working variables in locals (`LSTO`); flags, the angle mode and `GrMod` saved and restored; menu inputs validated before any computation, with an `AVIEW` message and a return to the menu on bad input; loops over integers.
    - Everything restorable is restored before a wait for a key; only what must follow the key comes after it.

    For a review, trace the stack through every branch, loop boundary and error path, and check every rule of the reference against the code. Done when each step's stack effect is accounted for and each rule was checked, with a finding or a pass.

3. **Compile with a round trip.** Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/roundtrip.py" PROGRAM.42 PROGRAM.raw`. Exit status 2 means the check could not run, and the message says why; when it is the emulator not being built for this plugin version, ask the person to run `/dm42:setup`, and until then compile with `txt2raw`/`raw2txt` if installed, comparing the listing with the source step by step. Done when it prints `ROUND TRIP: OK`. A failure names the source line the parser dropped or misread: fix that line.

4. **Run it in the emulator** with `bash "${CLAUDE_PLUGIN_ROOT}/scripts/dm42sim.sh" run ACTIONS`. Write the action script following `${CLAUDE_PLUGIN_ROOT}/references/dm42sim.md` and cover every input path (defaults, edge values, invalid input), at least one start in DEG plus every other mode the program must survive, and every way out of each wait (an ordinary key, EXIT, R/S). Read the JSON: `rows` for error messages, the stop reason, `steps`, and the final `state` against what the header promises to restore. Snapshot every picture and open the PNG before trusting a count. Done when every path has run and every final state matches the promise.

5. **Verify the output independently** whenever it is a picture or a number someone will rely on: compute it in Python with `decimal` at 34 digits following the program's own steps, compare pixel for pixel or digit for digit, and run one negative control. Done when the comparison shows no difference and the control shows one.

6. **Hand over** the `.raw` path, the round-trip result, the executed steps measured, and the checks only the device can make (the "Only the device shows" list in `dm42n.md`), written as concrete things for the person to try.
