# dm42

**dm42** — write, review and debug HP-42S-family RPN programs, the SwissMicros
DM42n first, and run them here before they reach the calculator.

Two skills. One is the workflow and the verified reference for the language and
the DM42's extensions. One builds `dm42sim`, an emulator made from SwissMicros'
own calculator core, so a program can be run, inspected and measured from a
script.

## Install

```
/plugin marketplace add emaballarin/ccplugins
/plugin install dm42@ccplugins
```

Then run `/dm42:setup` once to build the emulator.

## Skills

| Skill         | When                                                                     | What it does                                                                                                                                                                                                                                                                   |
| ------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `/dm42:rpn`   | Automatically, whenever a calculator program is written, reviewed or run | Reference first, then the program text in house style, a compile with a round trip that catches lines the parser drops, emulator runs over every input and exit path, an independent check of any picture or number, and a hand-over listing what only the device can confirm. |
| `/dm42:setup` | Once, and after a plugin update changes the emulator                     | Downloads SwissMicros' Free42 core at a pinned commit, compiles it as for the device with decimal arithmetic, and runs a smoke test of the DM42 graphics modes, virtual variables and precision.                                                                               |

`/dm42:rpn` is model-invoked. `/dm42:setup` is **user-only**: it downloads and
compiles, so it starts only when you type it.

## dm42sim

SwissMicros publishes no desktop simulator, and DMCP, the DM42's operating
system, is closed. Their Free42 fork is open, though, and its DM42 extensions
sit behind `#ifdef ARM`: `dm42sim` compiles the fork with `ARM` defined and
re-implements, headless, what SwissMicros' DM42PGM front end adds on the device
where a program can see it: the display hooks, and the DM42's rule that F1–F6
are the menu keys while the top row keeps its own functions. It is the DM42n
build: the original DM42 lacks six of its functions, the conversions
to and from IEEE binary and decimal number formats. The result runs programs with the DM42's virtual
variables (`GrMod`, `ResX`, `ResY`, `RefLCD`, `DevID`, `Vbat`), its 200×120 and
400×240 graphics modes, and 34-digit decimal arithmetic.

It reads an action script — load, `xeq`, keys, variables, flags, snapshots —
and answers in JSON lines: the screen's text rows, the stack, `ALPHA`,
variables (locals marked by level), flags, the graphics mode, executed steps,
and PNG snapshots on request. It also compiles program text to `.raw` and
decodes it back; `scripts/dm42sim.sh` runs it from anywhere, and
`scripts/roundtrip.py` checks that every source line survived a compile. The manual is
[references/dm42sim.md](references/dm42sim.md).

What it cannot show is DMCP's side: speed, the effect of `RefLCD`, DMCP's own
screens and stack display, and power management. Executed steps are the
portable measure; the device has the last word.

Requirements: bash, curl, tar, gzip, patch, make, gcc, g++, awk, od, which,
Python 3.14+, sha256sum, and
network on the first build. The build lives in `~/.cache/dm42/<commit>/`
(`$XDG_CACHE_HOME/dm42` when that is set; override with `DM42SIM_HOME`).

## References

| File                                            | Holds                                                                                                                                                    |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [rpn-semantics.md](references/rpn-semantics.md) | Program text rules, stack lift, flags, angle mode, locals and menus, keys and stopping, graphics, decimal arithmetic, performance — each with its source |
| [dm42n.md](references/dm42n.md)                 | The DM42/DM42n platform, virtual variables and how to reach them, graphics modes, F-keys, and what only the device shows                                 |
| [dm42sim.md](references/dm42sim.md)             | The emulator: commands, actions, JSON output, what is faithful and what is not, a worked recipe                                                          |

## Licence

MIT — see [LICENSE](LICENSE). [NOTICE](NOTICE) records the third-party code the
build downloads (SwissMicros' Free42 fork, GPL-2.0; the Intel decimal library,
BSD-3-Clause) and the DM42PGM front-end behaviour (BSD-3-Clause) that `dm42sim`
adapts, with its licence text.
