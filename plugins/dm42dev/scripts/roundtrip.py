"""Round-trip check for HP-42S program text: every source step must survive compilation.

The core's text parser (behind txt2raw, the SwissMicros decoder and dm42sim compile) skips
lines it cannot read and still succeeds, so a typo silently vanishes from the .raw. This
compiles with dm42sim, decodes the result, and compares the steps one by one.

    python3 roundtrip.py PROGRAM [OUT.raw] [--sim DM42SIM]

PROGRAM is program text or a numbered listing. Exit status 0 when every step survives (and
OUT.raw is written if given), 1 when one does not, 2 when the check could not run: the
message says why (dm42sim not built, unreadable input, unwritable output, bad usage).
"""

import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent

# One canonical spelling for each sign the listing and hand-written text spell differently.
SIGNS = [
    ("ᴇ", "E"),
    ("→", "->"),
    ("├", "|-"),
    ("⊢", "|-"),
    ("÷", "/"),
    ("×", "*"),
    ("≤", "<="),
    ("≥", ">="),
    ("≠", "!="),
    ("↑", "^"),
    ("↓", "DN"),
    ("▸", ""),
    ("+/-", "CHS"),
]


def norm(step: str) -> str:
    """Canonical spelling of one program step; text inside quotes is left as it is."""
    parts = step.strip().split('"')
    for i in range(0, len(parts), 2):  # even parts lie outside quotes
        p = parts[i]
        for a, b in SIGNS:
            p = p.replace(a, b)
        p = re.sub(r"\bX#(0|Y)\?", r"X!=\1?", p)
        parts[i] = re.sub(r"\s+", " ", p)
    s = '"'.join(parts)
    s = re.sub(r"^([+-]?(?:\d+\.?\d*|\.\d+))e([+-]?\d+)$", r"\1E\2", s)  # 1e3 is 1E3
    # Only these accept a one-digit argument, which the listing writes with two digits;
    # elsewhere (STO 5, LBL 1, ...) the parser drops the line, and the check must see that.
    return re.sub(r"^(FIX|SCI|ENG|SIZE) (\d)$", r"\1 0\2", s)


def strip_comment(line: str) -> str:
    """The line up to an '@' that lies outside quotes."""
    quoted = False
    for i, ch in enumerate(line):
        if ch == '"':
            quoted = not quoted
        elif ch == "@" and not quoted:
            return line[:i]
    return line


def is_listing(text: str) -> bool:
    """A numbered listing, as dm42sim decode, raw2txt or Free42's copy produce."""
    return re.search(r"^\s*00\s*\{", text, re.MULTILINE) is not None


def listing_steps(text: str) -> list[tuple[int, str]]:
    """(line number, step) of a numbered listing, without the '{ n-Byte Prgm }' headers."""
    out = []
    for n, line in enumerate(text.replace("\r", "").splitlines(), 1):
        m = re.match(r"^\s*\d+\s?(.*)$", strip_comment(line))
        if m and m.group(1).strip() and not m.group(1).startswith("{"):
            out.append((n, m.group(1).strip()))
    return out


def source_steps(text: str) -> list[tuple[int, str]]:
    """(line number, step) of program text: '@' starts a comment outside quotes."""
    if is_listing(text):
        return listing_steps(text)
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        code = strip_comment(line).strip()
        if code:
            out.append((n, code))
    return out


def sim_command() -> list[str]:
    """dm42sim through the plugin's wrapper, unless --sim names a binary."""
    if "--sim" in sys.argv:
        i = sys.argv.index("--sim")
        path = sys.argv[i + 1]
        del sys.argv[i : i + 2]
        return [path]
    return ["bash", str(HERE / "dm42sim.sh")]


def main(sim: list[str], src: str, raw_out: str | None = None) -> int:
    """Compile src with dm42sim, decode it back, and report the first step that did not survive."""
    with tempfile.TemporaryDirectory() as tmp:
        raw = pathlib.Path(tmp) / "prog.raw"
        comp = subprocess.run([*sim, "compile", src, str(raw)], capture_output=True, text=True, check=False)
        if comp.returncode != 0:
            print(f"dm42sim compile failed (exit {comp.returncode}): {comp.stdout}{comp.stderr}".strip())
            return 2
        dec = subprocess.run([*sim, "decode", str(raw)], capture_output=True, text=True, check=False)
        if dec.returncode != 0:
            print(f"dm42sim decode failed (exit {dec.returncode}): {dec.stdout}{dec.stderr}".strip())
            return 2
        try:
            want = source_steps(pathlib.Path(src).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as e:
            print(f"cannot read {src} as UTF-8 text: {e}")
            return 2
        got = [s for _, s in listing_steps(dec.stdout)]
        if len(got) == len(want) + 1 and norm(got[-1]) == "END" and (not want or norm(want[-1][1]) != "END"):
            got.pop()  # the core closes the last program with an END the source may omit
        print(f"{src}: {len(want)} source steps, {len(got)} compiled steps, {raw.stat().st_size} bytes")
        for i in range(max(len(want), len(got))):
            w = want[i] if i < len(want) else None
            g = got[i] if i < len(got) else None
            if w is None or g is None or norm(w[1]) != norm(g):
                where = f"source line {w[0]}: {w[1]!r}" if w else "after the last source line"
                print(f"  step {i + 1}, {where}, compiled as {g!r}")
                print("ROUND TRIP: FAIL — the parser dropped or misread this step; fix that line")
                return 1
        if raw_out:
            try:
                shutil.copyfile(raw, raw_out)
            except OSError as e:
                print(f"compiled, but cannot write {raw_out}: {e}")
                return 2
        print("ROUND TRIP: OK")
        return 0


if __name__ == "__main__":
    command = sim_command()
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        sys.exit(2)
    sys.exit(main(command, *sys.argv[1:]))
