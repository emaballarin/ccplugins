"""Smoke test for a dm42sim build: graphics modes, virtual variables, decimal arithmetic,
number formatting, menus, PNG snapshots, compile/decode, refused commands, the Free42
Configuration switches, and the stack depth under NSTK."""

import json
import pathlib
import struct
import subprocess
import sys
import tempfile
import zlib

HERE = pathlib.Path(__file__).resolve().parent
THIRD = "3." + "3" * 33 + "E-1"  # 34 significant digits, as the core formats them in ALL mode
LIT_400X240 = 1 + 1 + 400 + 240 - 1 + 8  # two dots, row 5, column 7 (sharing one pixel), an 8-pixel AGRAPH

EXPECTED = [
    # (state index, field, value)
    (0, "screen", "lcd"),
    (0, "width", 400),
    (0, "height", 240),
    (0, "lit", LIT_400X240),
    (0, "vars.RX", "400"),
    (0, "vars.RY", "240"),
    (0, "vars.WD", "400"),
    (0, "vars.HT", "240"),
    (0, "vars.THIRD", THIRD),
    (0, "vars.BIG", "1234567.25"),
    (0, "vars.HUGE", "1" + "0" * 30),
    (1, "screen", "lcd"),
    (1, "width", 200),
    (1, "lit", 4 + 2 * 16),
    (2, "menu", ["FCN", "PGM", "REAL", "CPX", "MAT", "MEM"]),
    (3, "menu", []),
]


# (actions, error message expected in the error event, or None for a clean run)
SQUARE = "cmd ENTER\ncmd *\n"
REFUSALS = [
    ("cmd 1/X\n", "Divide by 0"),  # an error, not a squeak: needs core_display.patch
    ("cmd NSTK\n", "Big Stack Disabled"),  # Dynamic Stack Extension is off by default
    ("key SHIFT ENTER\ntext Divide by 0\nkey ENTER\ncmd AVIEW\n", None),  # a message is not an error
    ("cmd X=0?\ncmd X<0?\n", None),  # nor is a test's Yes or No, which the core shows as an error code
    ("config mxsing 1\nkey 2 ENTER 2\ncmd NEWMAT\ncmd INVRT\n", "Singular Matrix"),
    ("config mxovfl 1\nkey 1 ENTER 1\ncmd NEWMAT\nkey 9 E 4 9 9\ncmd +\n" + SQUARE * 4, "Out of Range"),
]
STACK = "config dynstack 1\ncmd NSTK\nkey 1 ENTER 2 ENTER 3 ENTER 4 ENTER 5\nstate\nconfig dynstack 0\nstate\n"


def config_checks(binary: str) -> list[str]:
    """Commands refused with an error, the config switches, and the stack depth under NSTK."""
    bad = []
    for actions, want in REFUSALS:
        proc = subprocess.run([binary, "run", "-"], input=actions, capture_output=True, text=True, check=False)
        errors = [e["error"] for e in map(json.loads, proc.stdout.splitlines()) if e.get("event") == "error"]
        if want is None and (proc.returncode != 0 or errors):
            bad.append(f"{actions!r}: expected no error, got exit {proc.returncode} {errors}")
        elif want is not None and (proc.returncode != 2 or not errors or want not in errors[0]):
            bad.append(f"{actions!r}: expected an error naming {want!r}, got exit {proc.returncode} {errors}")
    proc = subprocess.run([binary, "run", "-"], input=STACK, capture_output=True, text=True, check=False)
    states = [e for e in map(json.loads, proc.stdout.splitlines()) if e.get("event") == "state"]
    got = [(s["depth"], s["flags"][80], s["config"]["dynstack"]) for s in states]
    if got != [(9, "1", 1), (4, "0", 0)]:
        bad.append(f"NSTK, then dynstack 0: expected depth 9 then 4, got {got}")
    return bad


def png_lit(path: pathlib.Path) -> tuple[int, int, int]:
    """(width, height, black pixels) of an 8-bit greyscale PNG as dm42sim writes it."""
    data = path.read_bytes()
    width, height = struct.unpack(">II", data[16:24])
    pos, idat = 8, b""
    while pos < len(data):
        (n,) = struct.unpack(">I", data[pos : pos + 4])
        if data[pos + 4 : pos + 8] == b"IDAT":
            idat += data[pos + 8 : pos + 8 + n]
        pos += 12 + n
    raw = zlib.decompress(idat)
    rows = [raw[r * (width + 1) + 1 : (r + 1) * (width + 1)] for r in range(height)]
    return width, height, sum(row.count(0) for row in rows)


def main(binary: str) -> int:
    """Run the smoke program and the compile/decode round in dm42sim; compare with EXPECTED."""
    bad = []
    with tempfile.TemporaryDirectory() as tmp:
        png = pathlib.Path(tmp) / "lcd.png"
        actions = (
            f"load {HERE / 'smoke.42'}\nmode RAD\nxeq SMOKE\nstate\nsnaplcd {png}\nrun\nstate\n"
            "key SHIFT +\nstate\nkey EXIT\nstate\n"
        )
        proc = subprocess.run([binary, "run", "-"], input=actions, capture_output=True, text=True, check=False)
        events = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
        states = [e for e in events if e.get("event") == "state"]
        if proc.returncode != 0 or len(states) != 4 or any(e.get("event") in {"error", "fatal"} for e in events):
            print(f"smoke: FAIL (exit {proc.returncode}, {len(states)} states)\n{proc.stdout}{proc.stderr}")
            return 1
        for i, field, want in EXPECTED:
            got = states[i]
            for part in field.split("."):
                got = got.get(part) if isinstance(got, dict) else None
            if got != want:
                bad.append(f"state {i} {field}: expected {want!r}, got {got!r}")
        if png_lit(png) != (400, 240, LIT_400X240):
            bad.append(f"snapshot: expected (400, 240, {LIT_400X240}), got {png_lit(png)}")
        raw = pathlib.Path(tmp) / "smoke.raw"
        subprocess.run([binary, "compile", str(HERE / "smoke.42"), str(raw)], check=False)
        listing = subprocess.run([binary, "decode", str(raw)], capture_output=True, text=True, check=False).stdout
        steps = [line for line in listing.splitlines() if line[:2].isdigit() and not line[2:].lstrip().startswith("{")]
        source = [
            line.split("@")[0].strip()
            for line in (HERE / "smoke.42").read_text(encoding="utf-8").splitlines()
            if line.split("@")[0].strip()
        ]
        if not steps or '"SMOKE"' not in steps[0] or len(steps) != len(source):
            bad.append(f"compile/decode: {len(source)} source steps, {len(steps)} decoded")
    bad += config_checks(binary)
    if bad:
        print("smoke: FAIL\n  " + "\n  ".join(bad))
        return 1
    print(f"smoke: OK ({len(EXPECTED) + 2 + len(REFUSALS) + 1} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
