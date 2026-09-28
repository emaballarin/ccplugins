r"""
Bibliography-audit helpers for Claude Code. There is no auto-injection: load
this file by its path (see SKILL.md). The public entrypoints are:

    audit, resolve, rewrite_tex

`audit` verifies, corrects, dedupes, strips, rekeys, tidies and validates a
`.bib` file, writes its outputs and a change log, and leaves the entries it could
not settle in a findings queue. `resolve` records the agent's (or the
maintainer's) answer for one queued entry, and the next `audit` applies it.
`rewrite_tex` migrates `\cite{}` keys in `.tex` files through a key map.

Kept as one file on purpose: ccsci loads each kernel by path with no package
context, so submodules would need `sys.path` edits at import time (a side effect
every kernel avoids) and a change to the tests' loader — navigation gained,
correctness not. Revisit if the file becomes hard to change safely.

The module has zero import-time side effects: the top level is imports, function
definitions and literal constants only; everything that touches the network, the
filesystem or a subprocess happens inside a function body. Standard library
only. The polite-pool contact email comes from LITREVIEW_CONTACT_EMAIL, the same
variable `literature-review` reads.
"""

import functools
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


# ── BibTeX parsing and serialisation ────────────────────────────────────────

_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")


_TOKEN_RE = re.compile(r"[A-Za-z0-9_:.+\-/']+")
_FIELD_RE = re.compile(r"([^\s=,{}\"#()]+)\s*=")
_ENTRY_RE = re.compile(r"@\s*([A-Za-z]+)\s*([{(])")
_NEXT_ENTRY_RE = re.compile(r"\n\s*@\s*[A-Za-z]+\s*[{(]")
_KEY_RE = re.compile(r"\s*([^\s,{}()=\"#]*)\s*,")
# Compiled patterns are matched at a position (`p.match(s, i)`), never on a
# slice: slicing a multi-megabyte proceedings file per field is quadratic.


class BibSyntaxError(ValueError):
    """A span of the input that cannot be read as a BibTeX entry."""


def _skip_ws(s: str, i: int) -> int:
    while i < len(s) and s[i].isspace():
        i += 1
    return i


def _read_braced(s: str, i: int) -> tuple[str, int]:
    """Read a `{...}` group starting at s[i] == '{'; return (inner, index after)."""
    depth, j = 0, i
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1 : j], j + 1
        j += 1
    raise BibSyntaxError(f"unbalanced braces from offset {i}")


def _read_quoted(s: str, i: int) -> tuple[str, int]:
    """Read a `"..."` value starting at s[i] == '"' (braces inside are balanced)."""
    depth, j = 0, i + 1
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == '"' and depth == 0:
            return s[i + 1 : j], j + 1
        j += 1
    raise BibSyntaxError(f"unterminated quoted value from offset {i}")


def _read_value(s: str, i: int, strings: dict[str, str]) -> tuple[str, bool, int]:
    """Read a field value (parts joined by `#`); return (value, is_bare_macro, end)."""
    parts, bare = [], False
    while True:
        i = _skip_ws(s, i)
        if i >= len(s):
            raise BibSyntaxError("value runs past end of input")
        c = s[i]
        if c == "{":
            v, i = _read_braced(s, i)
            parts.append(v)
        elif c == '"':
            v, i = _read_quoted(s, i)
            parts.append(v)
        else:
            m = _TOKEN_RE.match(s, i)
            if not m:
                raise BibSyntaxError(f"unexpected {c!r} at offset {i}")
            tok = m.group(0)
            i = m.end()
            if tok.isdigit():
                parts.append(tok)
            elif tok.lower() in _MONTHS:
                parts.append(tok.lower())
                bare = len(parts) == 1
            elif tok.lower() in strings:
                parts.append(strings[tok.lower()])
            else:
                parts.append(tok)
                bare = len(parts) == 1
        i = _skip_ws(s, i)
        if i < len(s) and s[i] == "#":
            i += 1
            bare = False
            continue
        return "".join(parts), bare and len(parts) == 1, i


def _read_fields(s: str, i: int, close: str, strings: dict[str, str]) -> tuple[dict, list[str], int]:
    """Read `name = value` pairs up to the closing delimiter; return (fields, bare, end)."""
    fields: dict[str, str] = {}
    bare: list[str] = []
    while True:
        i = _skip_ws(s, i)
        if i < len(s) and s[i] == ",":
            i += 1
            continue
        if i < len(s) and s[i] == close:
            return fields, bare, i + 1
        m = _FIELD_RE.match(s, i)
        if not m:
            raise BibSyntaxError(f"expected a field name at offset {i}")
        name = m.group(1).lower()
        v, is_bare, i = _read_value(s, m.end(), strings)
        fields[name] = v
        if is_bare:
            bare.append(name)


def parse_bib(text: str) -> dict:
    """Parse BibTeX text.

    Returns {"entries", "strings", "preamble", "garbage"}. Each entry is
    {"type", "key", "fields", "bare", "raw"}: field names are lower-cased,
    values are the inner text (outer delimiters removed, `#` concatenation and
    @string macros resolved), `bare` lists fields whose value was a bare macro
    such as `month = jan`, and `raw` is the entry's source span. Spans that
    cannot be read as an entry land in `garbage` with the reason, instead of
    aborting the parse."""
    entries, garbage, preamble = [], [], []
    strings: dict[str, str] = {m: m for m in _MONTHS}
    i = 0
    while True:
        at = text.find("@", i)
        if at < 0:
            break
        m = _ENTRY_RE.match(text, at)
        if not m:
            i = at + 1
            continue
        kind, opener = m.group(1).lower(), m.group(2)
        close = "}" if opener == "{" else ")"
        body = m.end()
        nxt = _NEXT_ENTRY_RE.search(text, body)
        fallback_end = nxt.start() if nxt else len(text)
        try:
            if kind == "comment":
                _, end = _read_braced(text, body - 1) if opener == "{" else (None, text.find(")", body) + 1)
                i = end
                continue
            if kind == "preamble":
                v, end = (
                    _read_braced(text, body - 1)
                    if opener == "{"
                    else (text[body : text.find(")", body)], text.find(")", body) + 1)
                )
                preamble.append(v)
                i = end
                continue
            if kind == "string":
                fields, _, end = _read_fields(text, body, close, strings)
                strings.update({k.lower(): v for k, v in fields.items()})
                i = end
                continue
            km = _KEY_RE.match(text, body)
            if not km or not km.group(1):
                raise BibSyntaxError("entry has no citation key")
            fields, bare, end = _read_fields(text, km.end(), close, strings)
            entries.append({"type": kind, "key": km.group(1), "fields": fields, "bare": bare, "raw": text[at:end]})
            i = end
        except BibSyntaxError as e:
            garbage.append({"raw": text[at:fallback_end].strip(), "reason": str(e)})
            i = fallback_end
    return {"entries": entries, "strings": strings, "preamble": preamble, "garbage": garbage}


def dump_entry(entry: dict) -> str:
    """Serialise one entry; final layout is left to bibtex-tidy."""
    bare = set(entry.get("bare", ()))
    lines = [f"@{entry['type']}{{{entry['key']},"]
    for name, value in entry["fields"].items():
        lines.append(f"  {name} = {value}," if name in bare else f"  {name} = {{{value}}},")
    lines.append("}")
    return "\n".join(lines)


def dump_bib(entries: list[dict], preamble: tuple[str, ...] | list[str] = ()) -> str:
    """Serialise entries (and any @preamble) into BibTeX text."""
    head = [f"@preamble{{{p}}}" for p in preamble]
    return "\n\n".join(head + [dump_entry(e) for e in entries]) + "\n"


# ── LaTeX → text, folding, names ────────────────────────────────────────────

_ACCENTS = {
    "'": "\u0301",
    "`": "\u0300",
    "^": "\u0302",
    '"': "\u0308",
    "~": "\u0303",
    "=": "\u0304",
    ".": "\u0307",
    "u": "\u0306",
    "v": "\u030c",
    "H": "\u030b",
    "c": "\u0327",
    "k": "\u0328",
    "r": "\u030a",
    "d": "\u0323",
    "b": "\u0331",
}
_LETTERS = {
    "ss": "ß",
    "o": "ø",
    "O": "Ø",
    "aa": "å",
    "AA": "Å",
    "ae": "æ",
    "AE": "Æ",
    "oe": "œ",
    "OE": "Œ",
    "l": "ł",
    "L": "Ł",
    "i": "ı",
    "j": "ȷ",
    "dh": "ð",
    "DH": "Ð",
    "th": "þ",
    "TH": "Þ",
    "ng": "ŋ",
    "NG": "Ŋ",
}
_SYMBOLS = {"&": "&", "%": "%", "$": "$", "_": "_", "#": "#", "{": "{", "}": "}", " ": " "}
_TEXT_SYMBOLS = {
    "textregistered": "®",
    "texttrademark": "™",
    "textcopyright": "©",
    "textdegree": "°",
    "textendash": "–",
    "textemdash": "—",
    "textquoteright": "’",
    "textquoteleft": "‘",
    "ldots": "…",
    "dots": "…",
    "textellipsis": "…",
    "textasciitilde": "~",
    "textbackslash": "\\",
    "textbar": "|",
    "textless": "<",
    "textgreater": ">",
}
"""LaTeX text-symbol commands, read as their characters (bibtex-tidy writes
"®" as "\textregistered{}")."""
# ASCII folding for letters that NFKD does not decompose.
_FOLD = str.maketrans({
    "ß": "ss",
    "ø": "o",
    "Ø": "O",
    "å": "a",
    "Å": "A",
    "æ": "ae",
    "Æ": "AE",
    "œ": "oe",
    "Œ": "OE",
    "ł": "l",
    "Ł": "L",
    "ı": "i",
    "ȷ": "j",
    "ð": "d",
    "Ð": "D",
    "þ": "th",
    "Þ": "Th",
    "ŋ": "ng",
    "Ŋ": "Ng",
    "đ": "d",
    "Đ": "D",
    "–": "-",
    "—": "-",
    "’": "'",
    "‘": "'",
    "“": '"',
    "”": '"',
})


def detex(s: str, keep_math: bool = True) -> str:
    r"""LaTeX-encoded BibTeX text → plain Unicode (NFC).

    Accent commands in every common spelling (`{\"u}`, `\"{u}`, `\"u`,
    `\c{c}`, `\v z`, `{\'\i}`) become precomposed letters; `\ss`, `\o`, `\l`
    and friends become their letters; other commands are dropped but their
    arguments kept; braces vanish. Math spans are kept as their bare text, or
    removed when `keep_math` is False."""
    if not keep_math:
        s = re.sub(r"(?<!\\)\$[^$]*\$", " ", s)
    s = s.replace("---", "—").replace("--", "–")
    s = re.sub(r"\\([&%$_#{} ])", lambda m: _SYMBOLS[m.group(1)], s)

    def accent(m: re.Match) -> str:
        base = m.group(2) or m.group(3) or ""
        base = _LETTERS.get(base.lstrip("\\"), base.lstrip("\\")) if base.startswith("\\") else base
        if base in ("ı", "ȷ"):
            base = "i" if base == "ı" else "j"
        return base + _ACCENTS[m.group(1)]

    sym = r"\\([`'^\"~=.])\s*(?:\{\s*(\\?[A-Za-z]+)\s*\}|(\\[A-Za-z]+|[A-Za-z]))"
    word = r"\\([uvHckrdb])(?:\s*\{\s*(\\?[A-Za-z]+)\s*\}|\s+(\\[A-Za-z]+|[A-Za-z]))"
    s = re.sub(sym, accent, s)
    s = re.sub(word, accent, s)
    s = re.sub(r"\\(ss|aa|AA|ae|AE|oe|OE|dh|DH|th|TH|ng|NG|[oOlLij])(?![A-Za-z])\s?", lambda m: _LETTERS[m.group(1)], s)
    s = re.sub(r"\\(" + "|".join(_TEXT_SYMBOLS) + r")(?![A-Za-z])(?:\{\}|\s)?", lambda m: _TEXT_SYMBOLS[m.group(1)], s)
    s = re.sub(r"\\[A-Za-z]+\*?\s*", "", s)
    s = s.replace("{", "").replace("}", "").replace("~", " ")
    s = re.sub(r"(?<!\\)\$", "", s) if keep_math else s
    return unicodedata.normalize("NFC", " ".join(s.split()))


def fold(s: str) -> str:
    """Strip diacritics and map special letters to ASCII (Buzsáki → Buzsaki)."""
    s = unicodedata.normalize("NFKD", s.translate(_FOLD))
    return "".join(c for c in s if not unicodedata.combining(c)).translate(_FOLD)


def _split_top(s: str, sep_re: str) -> list[str]:
    """Split `s` on `sep_re` matches at brace depth 0."""
    out, depth, last = [], 0, 0
    i = 0
    while i < len(s):
        c = s[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif depth == 0:
            m = re.match(sep_re, s[i:])
            if m and m.end() > 0:
                out.append(s[last:i])
                i += m.end()
                last = i
                continue
        i += 1
    out.append(s[last:])
    return [p.strip() for p in out]


def _words(s: str) -> list[str]:
    """Split a name part into words at depth-0 whitespace, keeping `{...}` groups whole."""
    return [w for w in _split_top(s, r"\s+") if w]


def _is_von(word: str) -> bool:
    """BibTeX's von test: the first alphabetic character at depth 0 is lower case."""
    depth = 0
    for i, c in enumerate(word):
        if c == "{":
            depth += 1
            if depth == 1 and word[i + 1 : i + 2] == "\\":
                m = re.match(r"\{\\[A-Za-z'`^\"~=.]+\s*\{?\s*([A-Za-z])", word[i:])
                if m:
                    return m.group(1).islower()
        elif c == "}":
            depth -= 1
        elif depth == 0 and c.isalpha():
            return c.islower()
    return False


def split_name(name: str) -> dict:
    """One BibTeX name → {"first", "von", "last", "jr"} per BibTeX's own rules."""
    parts = _split_top(name, r",")
    if len(parts) == 1:
        w = _words(parts[0])
        if not w:
            return {"first": "", "von": "", "last": "", "jr": ""}
        if len(w) == 1:
            return {"first": "", "von": "", "last": w[0], "jr": ""}
        vs = [i for i, x in enumerate(w[:-1]) if _is_von(x)]
        if vs:
            a, b = vs[0], vs[-1]
            return {"first": " ".join(w[:a]), "von": " ".join(w[a : b + 1]), "last": " ".join(w[b + 1 :]), "jr": ""}
        return {"first": " ".join(w[:-1]), "von": "", "last": w[-1], "jr": ""}
    head, jr, first = parts[0], (parts[1] if len(parts) == 3 else ""), parts[-1]
    w = _words(head)
    k = 0
    while k < len(w) - 1 and _is_von(w[k]):
        k += 1
    return {"first": first, "von": " ".join(w[:k]), "last": " ".join(w[k:]), "jr": jr}


def split_authors(field: str) -> list[dict]:
    """A BibTeX author/editor field → list of split names ("others" kept as a marker)."""
    names = _split_top(field, r"\s+and\s+")
    return [{"others": True} if n.strip().lower() == "others" else split_name(n) for n in names if n.strip()]


def join_name(n: dict) -> str:
    """A split name → canonical `von Last, Jr, First` BibTeX form."""
    if n.get("others"):
        return "others"
    last = " ".join(x for x in (n.get("von", ""), n.get("last", "")) if x)
    if n.get("jr"):
        return f"{last}, {n['jr']}, {n.get('first', '')}".rstrip(", ")
    return f"{last}, {n['first']}" if n.get("first") else last


def name_tokens(n: dict) -> set[str]:
    """Folded, lower-cased word tokens of every part of a name (order-free)."""
    txt = fold(detex(" ".join(n.get(k, "") for k in ("first", "von", "last")))).lower()
    return {t for t in re.split(r"[^a-z0-9]+", txt) if len(t) > 1}


def surname(n: dict) -> str:
    """Folded surname including particles, for comparison (`van der Waals` → `vanderwaals`)."""
    return re.sub(
        r"[^a-z0-9]", "", fold(detex(" ".join(x for x in (n.get("von", ""), n.get("last", "")) if x))).lower()
    )


# ── Polite HTTP ──────────────────────────────────────────────────────────────

_UA = "ccsci-bib-audit/1.0"

_NET_ERRORS = (urllib.error.URLError, OSError, ValueError)
"""Everything a fetch-and-decode can raise."""

_CACHE_ERRORS = (OSError, ValueError, KeyError)
"""A cache file that cannot be read or decoded."""

_SHAPE_ERRORS = (TypeError, KeyError, IndexError, ValueError)
"""A source record without the expected nesting."""

_JSON_FILE_ERRORS = (OSError, ValueError)
"""A state file that is missing or not JSON."""

_GAP = {
    "export.arxiv.org": 3.0,
    "api.crossref.org": 0.25,
    "api.openreview.net": 12.0,
    "api2.openreview.net": 3.0,
    "api.semanticscholar.org": 1.1,
    "sparql.dblp.org": 1.0,
    "api.openalex.org": 0.2,
}
"""Minimum seconds between two requests to one host: arXiv asks for 3 s, and
OpenReview allows 20 requests a minute on api2 and 5 on the older api
(`ratelimit-policy: 20;w=60`, `5;w=60`)."""

_RETRY_CODES = (429, 500, 502, 503, 504)

_BEST_EFFORT = frozenset({"api.semanticscholar.org"})
"""Sources that without credentials mostly refuse service (Semantic Scholar's
shared pool answers 429): their absence never makes an entry `unchecked` unless
the user supplied a key for them."""

_BREAK_AFTER = 3
"""Consecutive failed attempts after which a host is skipped for the rest of the
run. Throttled services answer slowly (arXiv takes up to a minute to send a 503),
so without a breaker one struggling host stalls every worker."""


def _contact() -> str | None:
    """LITREVIEW_CONTACT_EMAIL, or None — no placeholder `mailto:` is ever sent."""
    import os

    return (os.environ.get("LITREVIEW_CONTACT_EMAIL") or "").strip() or None


def credentials() -> dict[str, dict[str, str]]:
    """Per-host headers from the environment, each optional — without them every
    source is still asked anonymously:

    - `S2_API_KEY` → Semantic Scholar (`x-api-key`; 1 request/s instead of a
      shared pool that answers 429);
    - `OPENALEX_API_KEY` → OpenAlex (a larger daily budget);
    - `OPENREVIEW_TOKEN` → OpenReview, both APIs (for accounts with two-factor
      sign-in; otherwise `openreview_login` uses `OPENREVIEW_USERNAME` and
      `OPENREVIEW_PASSWORD`, the official client's variables).

    Keys go only into request headers: never into a URL, the cache or a report."""
    import os

    def env(name: str) -> str:
        return (os.environ.get(name) or "").strip()

    auth: dict[str, dict[str, str]] = {}
    if env("S2_API_KEY"):
        auth["api.semanticscholar.org"] = {"x-api-key": env("S2_API_KEY")}
    if env("OPENALEX_API_KEY"):
        auth["api.openalex.org"] = {"Authorization": f"Bearer {env('OPENALEX_API_KEY')}"}
    if env("OPENREVIEW_TOKEN"):
        for host in ("api.openreview.net", "api2.openreview.net"):
            auth[host] = {"Authorization": f"Bearer {env('OPENREVIEW_TOKEN')}"}
    return auth


def openreview_login(net) -> bool:
    """Sign in to OpenReview with OPENREVIEW_USERNAME / OPENREVIEW_PASSWORD (one
    token serves both APIs). Degrades to anonymous access with a note.

    What it buys today is limited: the signed-in token is sent with the title
    searches (whose limits may be higher). OpenReview's docs say signed-in
    clients also skip the challenge that walls anonymous bulk listings, which
    would allow an index of ICLR 2018/2019 accepted papers (the years the
    conference sites do not list) — not built yet; DBLP covers those years."""
    import os

    user = (os.environ.get("OPENREVIEW_USERNAME") or "").strip()
    password = os.environ.get("OPENREVIEW_PASSWORD") or ""
    if not (user and password) or "api2.openreview.net" in net.auth:
        return False
    data = net.post_json("https://api2.openreview.net/login", {"id": user, "password": password})
    token = data.get("token") if isinstance(data, dict) else None
    if token:
        for host in ("api.openreview.net", "api2.openreview.net"):
            net.auth[host] = {"Authorization": f"Bearer {token}"}
        net.notes.append(f"OpenReview: signed in as {user}")
        return True
    why = (
        "two-factor sign-in needs OPENREVIEW_TOKEN"
        if isinstance(data, dict) and data.get("mfaPending")
        else "sign-in refused"
    )
    net.notes.append(f"OpenReview: {why}; continued anonymously")
    return False


def _cache_root():
    """Machine-wide cache for immutable upstream data (past proceedings, arXiv versions)."""
    import os
    from pathlib import Path

    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "ccsci" / "bibaudit"


CACHE_MAX_AGE_DAYS = 180
CACHE_MAX_MB = 200
"""Machine-wide cache limits (overridable with BIBAUDIT_CACHE_MAX_AGE_DAYS and
BIBAUDIT_CACHE_MAX_MB): responses unused for longer are removed, then the least
recently used ones until the cache fits. Anything removed is simply fetched
again when needed."""


def prune_cache(root=None, max_age_days: float | None = None, max_mb: float | None = None) -> dict:
    """Apply the age limit, then the size limit, to the machine-wide response
    cache. Returns what was removed."""
    import os
    from pathlib import Path

    root = Path(root) if root else _cache_root() / "http"
    age = (
        max_age_days
        if max_age_days is not None
        else float(os.environ.get("BIBAUDIT_CACHE_MAX_AGE_DAYS") or CACHE_MAX_AGE_DAYS)
    )
    cap = (
        (max_mb if max_mb is not None else float(os.environ.get("BIBAUDIT_CACHE_MAX_MB") or CACHE_MAX_MB)) * 1024 * 1024
    )
    if not root.exists():
        return {"removed": 0, "freed_mb": 0.0}
    files = []
    for f in root.glob("*.json"):
        try:
            st = f.stat()
            files.append((st.st_mtime, st.st_size, f))
        except OSError:
            continue
    now, removed, freed = time.time(), 0, 0
    keep = []
    for mtime, size, f in files:
        if now - mtime > age * 86400:
            try:
                f.unlink()
                removed, freed = removed + 1, freed + size
            except OSError:
                pass
        else:
            keep.append((mtime, size, f))
    total = sum(size for _, size, _ in keep)
    for mtime, size, f in sorted(keep):
        if total <= cap:
            break
        try:
            f.unlink()
            removed, freed, total = removed + 1, freed + size, total - size
        except OSError:
            pass
    return {"removed": removed, "freed_mb": round(freed / 1048576, 1)}


class Net:
    """Polite HTTP client with explicit state: per-host pacing, bounded retries
    with backoff (honouring Retry-After), an on-disk cache for URLs whose content
    cannot change, and per-host call statistics for the report. `offline=True`
    serves only from the cache.

    A host that fails `_BREAK_AFTER` attempts in a row is taken out of the run:
    its later requests return None at once instead of waiting through retries,
    and `down` names it for the report.

    Safe to share between threads: request *starts* are spaced per host (so
    arXiv's one-request-per-3-s rule holds however many workers ask), while
    requests to different hosts overlap; a URL or a parsed index is fetched or
    built once, other workers waiting for it rather than repeating it.

    `auth` maps a host to the headers that authenticate it (`credentials`). A
    host that answers 401/403 to them loses them for the rest of the run and is
    asked again anonymously; `notes` says so for the report."""

    def __init__(self, cache_dir=None, offline: bool = False, auth: dict[str, dict[str, str]] | None = None):
        import threading

        self.cache_dir = cache_dir if cache_dir is not None else _cache_root()
        self.offline = offline
        self.auth: dict[str, dict[str, str]] = dict(auth or {})
        self.notes: list[str] = []
        self.last: dict[str, float] = {}
        self.stats: dict[str, dict[str, int]] = {}
        self.failures: list[str] = []
        self.strikes: dict[str, int] = {}
        self.not_before: dict[str, float] = {}
        self.down: set[str] = set()
        self.bodies: dict[str, str | None] = {}
        self.parsed: dict[tuple, object] = {}
        self._lock = threading.Lock()
        self._locks: dict[tuple, Any] = {}
        self._tls = threading.local()

    def begin(self) -> None:
        """Start tracking, for the calling thread, whether a request met a host
        that was taken out of the run (see `missed`)."""
        self._tls.skipped = False

    def missed(self) -> bool:
        """Whether this thread asked a skipped host since `begin`."""
        return bool(getattr(self._tls, "skipped", False))

    def _lock_for(self, key: tuple):
        import threading

        with self._lock:
            return self._locks.setdefault(key, threading.Lock())

    def once(self, key: tuple, compute) -> Any:
        """Memoise a parsed result for this run: proceedings indices run to
        megabytes and many entries consult the same one."""
        with self._lock_for(("once", *key)):
            if key not in self.parsed:
                self.parsed[key] = compute()
            return self.parsed[key]

    def _stat(self, host: str, what: str) -> None:
        with self._lock:
            self.stats.setdefault(host, {"calls": 0, "cached": 0, "failed": 0, "blocked": 0, "skipped": 0})[what] += 1

    def _heed(self, host: str, headers) -> float | None:
        """Honour a server's rate-limit headers: when `Retry-After` is given, or
        the window's remaining budget reaches zero, hold the host's next request
        until the reset. Returns the wait imposed, or None when there was no
        guidance."""
        if headers is None:
            return None
        wait = None
        ra = headers.get("Retry-After")
        if ra and ra.strip().isdigit():
            wait = float(ra)
        remaining = headers.get("ratelimit-remaining") or headers.get("x-ratelimit-remaining")
        reset = headers.get("ratelimit-reset")
        if remaining is not None and remaining.strip() == "0" and reset and reset.strip().isdigit():
            wait = max(wait or 0.0, float(reset))
        if wait is not None:
            with self._lock:
                self.not_before[host] = max(self.not_before.get(host, 0.0), time.time() + wait + 0.5)
        return wait

    def _counts(self, host: str) -> bool:
        """Whether this host's absence leaves an entry unchecked (see `_BEST_EFFORT`)."""
        return host not in _BEST_EFFORT or host in self.auth

    def _strike(self, host: str) -> bool:
        """Count a failed attempt; True once the host has just been taken out."""
        with self._lock:
            self.strikes[host] = self.strikes.get(host, 0) + 1
            if self.strikes[host] >= _BREAK_AFTER and host not in self.down:
                self.down.add(host)
                return True
            return host in self.down

    def _fail(self, host: str, what: str) -> None:
        self._stat(host, "failed")
        with self._lock:
            if len(self.failures) < 50:
                self.failures.append(what)

    def _cache_path(self, key: str):
        import hashlib

        return self.cache_dir / "http" / (hashlib.sha1(key.encode()).hexdigest() + ".json")

    def get(
        self, url: str, *, accept: str | None = None, ttl: float | None = None, expect_json: bool = False
    ) -> str | None:
        """GET `url` → body text, or None on failure.

        `ttl` enables the disk cache: seconds of validity, or `float("inf")` for
        content that never changes. A JSON endpoint answering with an HTML page is
        treated as blocked (bot walls such as DBLP's) rather than as data."""
        host = urllib.parse.urlsplit(url).netloc
        with self._lock_for(("url", url)):
            if url not in self.bodies:
                self.bodies[url] = self._fetch(url, host, accept, ttl, expect_json)
            return self.bodies[url]

    def post_json(self, url: str, payload, ttl: float | None = None) -> Any:
        """POST a JSON body and decode the JSON answer (object or list), memoised
        and cached like `get`, keyed on URL and body; None on failure."""
        import hashlib

        data = json.dumps(payload, sort_keys=True).encode()
        key = f"{url}#{hashlib.sha1(data).hexdigest()}"
        host = urllib.parse.urlsplit(url).netloc
        with self._lock_for(("url", key)):
            if key not in self.bodies:
                self.bodies[key] = self._fetch(url, host, "application/json", ttl, True, data=data, key=key)
            body = self.bodies[key]
        try:
            return json.loads(body) if body else None
        except ValueError:
            return None

    def _fetch(
        self,
        url: str,
        host: str,
        accept: str | None,
        ttl: float | None,
        expect_json: bool,
        data: bytes | None = None,
        key: str | None = None,
    ) -> str | None:
        """One request (GET, or POST with `data`) through the disk cache, pacing,
        credentials and retries (see `get`)."""
        path = self._cache_path(key or url) if ttl is not None else None
        if path is not None and path.exists():
            try:
                rec = json.loads(path.read_text())
                if time.time() - rec["t"] < ttl:
                    self._stat(host, "cached")
                    try:
                        import os

                        os.utime(path)  # "last used", for the cache's age and size limits
                    except OSError:
                        pass
                    return rec["body"]
            except _CACHE_ERRORS:
                pass
        if self.offline:
            return None
        if host in self.down:
            self._stat(host, "skipped")
            self._tls.skipped = self.missed() or self._counts(host)
            return None
        c = _contact()
        headers = {"User-Agent": (_UA + (f" (mailto:{c})" if c else "")).encode("ascii", "ignore").decode()}
        if accept:
            headers["Accept"] = accept
        if data is not None:
            headers["Content-Type"] = "application/json"
        for attempt in range(5):
            creds = self.auth.get(host) or {}
            with self._lock_for(("host", host)):
                wait = max(
                    _GAP.get(host, 1.0) - (time.time() - self.last.get(host, 0.0)),
                    self.not_before.get(host, 0.0) - time.time(),
                )
                if wait > 0:
                    time.sleep(wait)
                self.last[host] = time.time()
            self._stat(host, "calls")
            try:
                req = urllib.request.Request(url, data=data, headers={**headers, **creds})
                with urllib.request.urlopen(req, timeout=40) as r:
                    body = r.read().decode("utf-8", "replace")
                    self._heed(host, r.headers)
            except urllib.error.HTTPError as e:
                if e.code in (401, 403) and creds:
                    with self._lock:
                        if self.auth.pop(host, None) is not None:
                            self.notes.append(f"{host}: credentials rejected (HTTP {e.code}); continued without them")
                    continue  # degrade: the same request, anonymously
                told = self._heed(host, e.headers)
                if e.code == 429 and told is not None and told <= 90 and attempt < 3:
                    continue  # the server said when to come back; the pacing above waits for it
                if e.code in _RETRY_CODES and self._strike(host):
                    self._fail(host, f"HTTP {e.code} {url} (host now skipped)")
                    self._tls.skipped = self.missed() or self._counts(host)
                    return None
                if e.code in _RETRY_CODES and attempt < 3:
                    ra = e.headers.get("Retry-After") if e.headers else None
                    time.sleep(min(float(ra), 30.0) if ra and ra.isdigit() else 2.0 * 2**attempt)
                    continue
                self._fail(host, f"HTTP {e.code} {url}")
                return None
            except _NET_ERRORS as e:
                if self._strike(host):
                    self._fail(host, f"{type(e).__name__} {url} (host now skipped)")
                    self._tls.skipped = self.missed() or self._counts(host)
                    return None
                if attempt < 3:
                    time.sleep(2.0 * 2**attempt)
                    continue
                self._fail(host, f"{type(e).__name__} {url}")
                return None
            with self._lock:
                self.strikes[host] = 0
            if expect_json and body.lstrip()[:1] == "<":
                self._stat(host, "blocked")
                return None
            if path is not None:
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = path.with_suffix(".tmp")
                    tmp.write_text(json.dumps({"t": time.time(), "url": url, "body": body}))
                    tmp.replace(path)
                except OSError:
                    pass
            return body
        return None

    def get_json(self, url: str, ttl: float | None = None) -> dict | None:
        """GET a JSON object; None for failures and for any non-object body."""
        body = self.get(url, accept="application/json", ttl=ttl, expect_json=True)
        try:
            data = json.loads(body) if body else None
        except ValueError:
            return None
        return data if isinstance(data, dict) else None


# ── Source records ───────────────────────────────────────────────────────────
# Every source returns candidates in one shape: {"source", "id", "type",
# "title", "authors" (split names), "year", "venue", "volume", "number",
# "pages", "publisher", "series", "doi", "arxiv", "url", "extra"}. Absent
# values are None; "type" is a BibTeX entry type or "preprint".

_INF = float("inf")
_MONTH = 30 * 86400


def _rec(source: str, rid: str, **kw) -> dict:
    base: dict = dict.fromkeys((
        "type",
        "title",
        "year",
        "venue",
        "volume",
        "number",
        "pages",
        "publisher",
        "series",
        "doi",
        "arxiv",
        "url",
    ))
    base.update(source=source, id=rid, authors=[], extra={})
    base.update({k: v for k, v in kw.items() if v not in (None, "", [])})
    return base


def _plain(s: str | None) -> str | None:
    """Strip HTML/MathML tags and entities that some sources put in titles."""
    import html

    if not s:
        return s
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", s)).split())


_DOTTED_INITIALS = re.compile(r"(?:[A-Z]\.-?)+")


def _surname_first(name: str) -> str | None:
    """A name printed surname first ("Cavazzoni S.", "Paris M. G. A.") as "Cavazzoni, S.";
    None for any other form. Only dotted initials count: an undotted "LEE" may be an
    all-caps surname."""
    w = [] if "," in name else name.split()
    k = next((i for i, x in enumerate(w) if _DOTTED_INITIALS.fullmatch(x)), 0)
    return f"{' '.join(w[:k])}, {' '.join(w[k:])}" if k and all(_DOTTED_INITIALS.fullmatch(x) for x in w[k:]) else None


def _full_names(names: list) -> list[dict]:
    """`First von Last` strings, or OpenReview's {"fullname": …} objects → split names.
    A byline printed surname first throughout ("Cavazzoni S., Razzoli L.") is read
    that way; one such name among `First Last` ones has a one-letter surname
    ("Weinan E.") and is read as written."""
    flat = [(n.get("fullname") or n.get("name") or "") if isinstance(n, dict) else str(n or "") for n in names]
    flat = [n.strip() for n in flat if n.strip()]
    flipped = [f for f in map(_surname_first, flat) if f]
    return [split_name(n) for n in (flipped if len(flat) > 1 and len(flipped) == len(flat) else flat)]


_CR_TYPES = {
    "journal-article": "article",
    "proceedings-article": "inproceedings",
    "book": "book",
    "monograph": "book",
    "edited-book": "book",
    "reference-book": "book",
    "book-chapter": "incollection",
    "book-section": "incollection",
    "book-part": "incollection",
    "reference-entry": "incollection",
    "posted-content": "preprint",
    "dissertation": "phdthesis",
    "report": "techreport",
    "standard": "techreport",
}


def _cr_year(m: dict, kind: str) -> int | None:
    """Conference year for proceedings (event start when recorded), issue year for articles."""
    order = (("event", "start"), ("issued",)) if kind == "inproceedings" else (("published-print",), ("issued",))
    for path in order:
        node = m
        for p in path:
            node = node.get(p) if isinstance(node, dict) else None
        if not isinstance(node, dict):
            continue
        try:
            return int(node["date-parts"][0][0])
        except _SHAPE_ERRORS:
            continue
    return None


_SERIES = re.compile(
    r"^(?:lecture notes in|communications in computer and information science|advances in intelligent systems"
    r"|smart innovation|studies in computational intelligence|springer proceedings|lecture notes)",
    re.IGNORECASE,
)
"""Book-series names Crossref lists as a chapter's first container title; the
conference volume's own title is the useful one."""


def _crossref_record(m: dict) -> dict:
    kind = _CR_TYPES.get(m.get("type", ""), "misc")
    title = _plain((m.get("title") or [""])[0]) or ""
    title = re.sub(
        r"^[IVXLCDM]+\.\s*(?:[-–—]\s*)?(?=[A-Z])", "", title
    )  # "LIII. On lines…": the journal's article number
    sub = _plain((m.get("subtitle") or [""])[0])
    if sub and title and sub.lower() not in title.lower():
        title = f"{title}: {sub}"
    authors = []
    for a in m.get("author") or []:
        if a.get("family"):
            authors.append({"first": a.get("given", ""), "von": "", "last": a["family"], "jr": a.get("suffix", "")})
        elif a.get("name"):
            authors.append({"first": "", "von": "", "last": "{" + a["name"] + "}", "jr": ""})
    containers = [c for c in (_plain(x) for x in m.get("container-title") or []) if c]
    event = (m.get("event") or {}).get("name")
    if kind == "incollection" and event:
        kind = "inproceedings"  # a conference paper Crossref files as a book chapter (Springer LNCS)
    venue = next((c for c in containers if not _SERIES.match(c)), containers[0] if containers else None)
    if kind == "preprint" and not venue:
        venue = ((m.get("institution") or [{}])[0] or {}).get("name")  # "bioRxiv", "SSRN", …
    if (
        kind == "inproceedings"
        and event
        and (not venue or _SERIES.match(venue) or re.search(r"\b(?:19|20)\d{2}\b", venue))
    ):
        venue = event
    pages = (m.get("page") or "").replace("-", "--") or m.get("article-number")
    return _rec(
        "crossref",
        m.get("DOI", "").lower(),
        type=kind,
        title=title,
        authors=authors,
        year=_cr_year(m, kind),
        venue=venue,
        volume=m.get("volume"),
        number=m.get("issue"),
        pages=pages,
        publisher=m.get("publisher"),
        doi=m.get("DOI", "").lower() or None,
        extra={
            "relation": m.get("relation") or {},
            "short_venue": (m.get("short-container-title") or [None])[0],
            "containers": containers,
            "event": event,
            "issn": list(m.get("ISSN") or []),
            "years": sorted(
                {
                    int(d["date-parts"][0][0])
                    for k in ("issued", "published-print", "published-online", "published")
                    if isinstance(d := m.get(k), dict)
                    and d.get("date-parts")
                    and d["date-parts"][0]
                    and d["date-parts"][0][0]
                }
                | ({y} if (y := _cr_year(m, kind)) else set())
            ),
            "year_from_event": kind == "inproceedings"
            and bool(((m.get("event") or {}).get("start") or {}).get("date-parts")),
        },
    )


def crossref_by_dois(net: Net, dois: list[str]) -> dict[str, dict]:
    """DOIs → Crossref records, 20 per request (OR'd `doi:` filters)."""
    out: dict[str, dict] = {}
    plain = [d for d in dict.fromkeys(x.lower() for x in dois) if "," not in d]
    odd = [d for d in dict.fromkeys(x.lower() for x in dois) if "," in d]
    for i in range(0, len(plain), 20):
        chunk = plain[i : i + 20]
        q = ",".join("doi:" + d for d in chunk)
        data = net.get_json(
            f"https://api.crossref.org/works?filter={urllib.parse.quote(q, safe=':,/')}&rows=40", ttl=_MONTH
        )
        for m in ((data or {}).get("message") or {}).get("items") or []:
            out[m.get("DOI", "").lower()] = _crossref_record(m)
    for d in odd:
        data = net.get_json("https://api.crossref.org/works/" + urllib.parse.quote(d, safe="/"), ttl=_MONTH)
        if data and data.get("message"):
            out[d] = _crossref_record(data["message"])
    return out


def crossref_search(
    net: Net, title: str | None, author: str | None, year: int | None = None, rows: int = 5, context: str = ""
) -> list[dict]:
    """Memoised for the run; see `_crossref_search`."""
    return net.once(
        ("crossref_search", title, author, year, rows, context),
        lambda: _crossref_search(net, title, author, year, rows, context),
    )


def _crossref_search(
    net: Net, title: str | None, author: str | None, year: int | None = None, rows: int = 5, context: str = ""
) -> list[dict]:
    """Bibliographic search. With a title, one citation string — title, first
    author's surname, then `context` (the entry's venue and year) — goes into
    `query.bibliographic`, which ranks the original above its reprints; a
    separate `query.author` would drop records whose name form differs
    ("Boguna" vs "Boguñá", Crossref's "M N" for a Dheeraj). With no title (a
    sparse entry) the author query and a year filter do the search."""
    params = {"rows": str(rows)}
    if title:
        params["query.bibliographic"] = " ".join(f"{title} {author or ''} {context}".split())
    elif author:
        params["query.author"] = author
    if not title and year:
        params["filter"] = f"from-pub-date:{year},until-pub-date:{year}"
    if len(params) == 1:
        return []
    data = net.get_json("https://api.crossref.org/works?" + urllib.parse.urlencode(params), ttl=_MONTH)
    return [_crossref_record(m) for m in ((data or {}).get("message") or {}).get("items") or []]


_ARXIV_ID = r"(?:\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})"


def _arxiv_entry(e: str) -> dict | None:
    def g(tag: str) -> str | None:
        m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", e, re.DOTALL)
        return " ".join(m.group(1).split()) if m else None

    rid = g("id") or ""
    m = re.search(rf"abs/({_ARXIV_ID})(v\d+)?$", rid)
    if not m:
        return None
    pub, upd = g("published") or "", g("updated") or ""
    cat = re.search(r'<arxiv:primary_category[^>]*term="([^"]+)"', e)
    import html

    title = html.unescape(g("title") or "")
    names = [html.unescape(n) for n in re.findall(r"<name>(.*?)</name>", e, re.DOTALL)]
    return _rec(
        "arxiv",
        m.group(1) + (m.group(2) or ""),
        type="preprint",
        title=title,
        authors=_full_names(names),
        year=int(pub[:4]) if pub[:4].isdigit() else None,
        arxiv=m.group(1),
        doi=(g("arxiv:doi") or "").lower() or None,
        extra={
            "version": int((m.group(2) or "v1")[1:]),
            "published": pub[:10],
            "updated": upd[:10],
            "comment": g("arxiv:comment"),
            "journal_ref": g("arxiv:journal_ref"),
            "category": cat.group(1) if cat else None,
        },
    )


def _datacite_record(r: dict) -> dict | None:
    """A DataCite record of an arXiv DOI (10.48550/arXiv.<id>) → an arXiv record.

    DataCite carries what the arXiv API does for the latest version — title,
    structured authors, first-submission year, version count, per-version
    submission dates, the comment, the primary category, and the published DOI
    the authors gave arXiv (`IsVersionOf`) — without arXiv's throttling."""
    a = r.get("attributes") or {}
    doi = str(r.get("id") or "").lower()
    if "arxiv." not in doi or not a.get("titles"):
        return None
    aid = doi.split("arxiv.", 1)[1]
    authors = []
    for c in a.get("creators") or []:
        if c.get("familyName"):
            authors.append({"first": c.get("givenName", ""), "von": "", "last": c["familyName"], "jr": ""})
        elif c.get("name"):
            org = c.get("nameType") == "Organizational" or "," not in c["name"]
            authors.append(
                {"first": "", "von": "", "last": "{" + c["name"] + "}", "jr": ""} if org else split_name(c["name"])
            )
    submitted = sorted(
        d["date"][:10] for d in a.get("dates") or [] if d.get("dateType") == "Submitted" and d.get("date")
    )
    comment = next(
        (d.get("description") for d in a.get("descriptions") or [] if d.get("descriptionType") == "Other"), None
    )
    published = next(
        (
            x["relatedIdentifier"].lower()
            for x in a.get("relatedIdentifiers") or []
            if x.get("relationType") == "IsVersionOf" and x.get("relatedIdentifierType") == "DOI"
        ),
        None,
    )
    cat = next(
        (
            m.group(1)
            for sub in a.get("subjects") or []
            if (m := re.search(r"\(([a-z\-]+(?:\.[A-Za-z\-]+)?)\)$", sub.get("subject") or ""))
        ),
        None,
    )
    year = a.get("publicationYear") or (submitted[0][:4] if submitted else None)
    return _rec(
        "arxiv",
        aid,
        type="preprint",
        title=" ".join(a["titles"][0].get("title", "").split()),
        authors=authors,
        year=int(str(year)) if str(year or "").isdigit() else None,
        arxiv=aid,
        doi=published,
        extra={
            "version": int(a.get("version") or len(submitted) or 1),
            "published": submitted[0] if submitted else None,
            "updated": submitted[-1] if submitted else None,
            "submitted": submitted,
            "comment": comment,
            "journal_ref": None,
            "category": cat,
        },
    )


def _datacite_arxiv(net: Net, ids: list[str]) -> dict[str, dict]:
    """Latest-version records for bare arXiv ids from DataCite, 25 per request."""
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 25):
        chunk = ids[i : i + 25]
        q = "doi:(" + " OR ".join(f"10.48550/arxiv.{x.lower()}" for x in chunk) + ")"
        data = net.get_json(
            "https://api.datacite.org/dois?" + urllib.parse.urlencode({"query": q, "page[size]": "50"}), ttl=86400.0
        )
        for r in (data or {}).get("data") or []:
            rec = _datacite_record(r)
            if rec:
                out[rec["arxiv"]] = rec
    for x in ids:
        if x.lower() not in out:
            data = net.get_json(
                "https://api.datacite.org/dois/" + urllib.parse.quote(f"10.48550/arxiv.{x.lower()}", safe="/"),
                ttl=86400.0,
            )
            rec = _datacite_record((data or {}).get("data") or {})
            if rec:
                out[rec["arxiv"]] = rec
    return {x: out[x.lower()] for x in ids if x.lower() in out}


def _arxiv_api(net: Net, ids: list[str]) -> dict[str, dict]:
    """Records from the arXiv API itself, 10 per request (larger batches draw
    HTTP 503/429 after a minute's wait). Used for pinned versions only: a
    versioned id's metadata never changes, so each is cached for good."""
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 10):
        chunk = ids[i : i + 10]
        body = net.get(
            "https://export.arxiv.org/api/query?"
            + urllib.parse.urlencode({"id_list": ",".join(chunk), "max_results": str(len(chunk))}),
            ttl=_INF,
        )
        for e in re.findall(r"<entry>(.*?)</entry>", body or "", re.DOTALL):
            r = _arxiv_entry(e)
            if r:
                out[r["id"] if r["id"] in chunk else r["arxiv"]] = r
    return out


def arxiv_by_ids(net: Net, ids: list[str]) -> dict[str, dict]:
    """arXiv ids → records: a bare id gives the latest version (from DataCite),
    `<id>vN` that exact version (from the arXiv API). `extra.updated` is the date
    of the version described, `extra.published` that of v1."""
    ids = list(dict.fromkeys(ids))
    pinned = [x for x in ids if re.search(r"v\d+$", x)]
    bare = [x for x in ids if x not in pinned]
    return {**_datacite_arxiv(net, bare), **_arxiv_api(net, pinned)}


def _or_value(c: dict, k: str):
    v = c.get(k)
    return v.get("value") if isinstance(v, dict) else v


def openreview_status(venueid: str, venue: str | None = None) -> str:
    """ "published" | "workshop" | "preprint" | "other" from an OpenReview venueid.

    An allowlist, because the failure it prevents is silent: only an accepted
    paper's venueid is exactly `<Venue>/<YYYY>/Conference` (or `TMLR`, or a
    non-CoRR DBLP record); submissions under review, rejected and withdrawn
    papers, `Public_Article` and `Archive` notes all carry something else and
    must never be cited as published."""
    vid = venueid or ""
    if vid.startswith("dblp.org/"):
        return "preprint" if "/CORR/" in vid.upper() else "published"
    if vid == "TMLR" or re.fullmatch(r"[^/\s]+(?:/[^/\s]+)?/\d{4}/Conference", vid):
        return "published"
    if re.fullmatch(r"[^/\s]+(?:/[^/\s]+)?/\d{4}/Workshop/[^/\s]+", vid):
        return "workshop"
    return "other"


def arxiv_search(net: Net, title: str, author: str | None = None) -> list[dict]:
    """arXiv records by title — DataCite's arXiv records first, then the arXiv
    API (phrase, then all words, narrowed by an author surname): how an entry
    whose eprint points at the wrong paper finds its own."""
    words = [w for w in re.split(r"[^A-Za-z0-9]+", fold(detex(title, keep_math=False))) if len(w) > 1][:12]
    if not words:
        return []
    content = [w for w in words if w.lower() not in _STOP][:8] or words[:8]
    data = net.get_json(
        "https://api.datacite.org/dois?"
        + urllib.parse.urlencode({
            "query": "titles.title:(" + " AND ".join(content) + ")",
            "client-id": "arxiv.content",
            "page[size]": "8",
        }),
        ttl=_MONTH,
    )
    hits = [r for r in (_datacite_record(x) for x in (data or {}).get("data") or []) if r]
    if hits:
        return hits
    who = re.sub(r"[^A-Za-z]", "", fold(author or ""))
    au = f" AND au:{who}" if who else ""
    out: list[dict] = []
    for q in (f'ti:"{" ".join(words)}"{au}', " AND ".join(f"ti:{w}" for w in words) + au):
        body = net.get(
            "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"search_query": q, "max_results": "5"}),
            ttl=_MONTH,
        )
        out = [r for r in (_arxiv_entry(e) for e in re.findall(r"<entry>(.*?)</entry>", body or "", re.DOTALL)) if r]
        if out:
            break
    return out


# ── Semantic Scholar, DBLP (SPARQL) and OpenAlex ───────────────────────────

_S2 = "https://api.semanticscholar.org/graph/v1"
_S2_FIELDS = "title,year,venue,publicationVenue,journal,externalIds,authors,publicationTypes"


def is_arxiv_doi(doi: str | None) -> bool:
    return bool(doi) and str(doi).lower().startswith("10.48550/arxiv.")


def _clean_name(name: str) -> str:
    """Registry names in one Unicode form: composed, "ı́" (dotless i with an accent)
    as "í", typographic hyphens as "-"."""
    return unicodedata.normalize(
        "NFC", unicodedata.normalize("NFC", name or "").replace("\u0131\u0301", "í")
    ).translate(str.maketrans({"\u2010": "-", "\u2011": "-"}))


def _s2_record(p: dict | None) -> dict | None:
    if not p or not p.get("title"):
        return None
    ext, pv, j = p.get("externalIds") or {}, p.get("publicationVenue") or {}, p.get("journal") or {}
    venue = pv.get("name") or j.get("name") or p.get("venue") or None
    preprint = not venue or bool(re.search(r"\b(?:arxiv|corr)\b", venue, re.IGNORECASE))
    types = p.get("publicationTypes") or []
    kind = (
        "preprint"
        if preprint
        else ("inproceedings" if "Conference" in types or pv.get("type") == "conference" else "article")
    )
    vol = (j.get("volume") or "").strip()
    return _rec(
        "s2",
        p.get("paperId") or "",
        type=kind,
        title=" ".join(p["title"].split()),
        authors=_full_names([_clean_name(a.get("name") or "") for a in p.get("authors") or []]),
        year=p.get("year"),
        venue=None if preprint else venue,
        volume=vol if re.fullmatch(r"[0-9IVXLC]+", vol) else None,
        pages=_pages((j.get("pages") or "").strip()) or None,
        doi=(ext.get("DOI") or "").lower() or None,
        arxiv=ext.get("ArXiv"),
        extra={
            "dblp": ext.get("DBLP"),
            "venue_type": pv.get("type"),
            "issn": [x for x in [pv.get("issn"), *(pv.get("alternate_issns") or [])] if x],
        },
    )


def s2_batch(net: Net, ids: list[str]) -> dict[str, dict]:
    """Semantic Scholar records for `DOI:…` / `ARXIV:…` ids, 500 per request, one
    request a second. Asked only with `S2_API_KEY`: the keyless shared pool
    answers 429 to every call."""
    out: dict[str, dict] = {}
    if "api.semanticscholar.org" not in net.auth:
        return out
    ids = list(dict.fromkeys(ids))
    for i in range(0, len(ids), 500):
        chunk = ids[i : i + 500]
        data = net.post_json(f"{_S2}/paper/batch?fields={_S2_FIELDS}", {"ids": chunk}, ttl=_MONTH)
        if isinstance(data, list):
            for key, p in zip(chunk, data, strict=False):
                r = _s2_record(p)
                if r:
                    out[key] = r
    return out


def s2_match(net: Net, title: str) -> list[dict]:
    """Semantic Scholar's single best title match (none when it has none; nothing
    asked without `S2_API_KEY`)."""
    if "api.semanticscholar.org" not in net.auth:
        return []
    q = urllib.parse.urlencode({"query": title[:300], "fields": _S2_FIELDS})
    data = net.get_json(f"{_S2}/paper/search/match?{q}", ttl=_MONTH)
    return [r for r in (_s2_record(p) for p in (data or {}).get("data") or []) if r]


_DBLP_SPARQL = "https://sparql.dblp.org/sparql"


def _dblp_record(b: dict) -> dict | None:
    v = {k: x.get("value", "") for k, x in b.items()}
    key = v.get("pub", "").removeprefix("https://dblp.org/rec/")
    title = re.sub(r"\.$", "", v.get("t", "")).strip()
    if not key or not title:
        return None
    venue = v.get("venue") or None
    if key.startswith("journals/corr/") and (venue or "CoRR") == "CoRR":
        kind, venue = "preprint", None
    elif key.startswith(("conf/", "journals/corr/")):
        kind = "inproceedings"  # journals/corr/ with another venue: an arXiv-published proceedings (ICLR 2014)
    elif key.startswith("journals/"):
        kind = "article"
    elif key.startswith("phd/"):
        kind = "phdthesis"
    else:
        kind = "book" if key.startswith("books/") else "misc"
    names = sorted(
        (int(o), re.sub(r"\s+\d{4}$", "", n))
        for o, n in (x.split("=", 1) for x in v.get("au", "").split("|") if "=" in x)
        if o.isdigit()
    )
    return _rec(
        "dblp",
        key,
        type=kind,
        title=title,
        authors=_full_names([n for _, n in names]),
        year=int(v["year"]) if v.get("year", "").isdigit() else None,
        venue=venue,
        pages=_pages(v.get("pages")) or None,
        doi=v.get("doi", "").removeprefix("https://doi.org/").lower() or None,
    )


def dblp_search(net: Net, title: str) -> list[dict]:
    """Memoised for the run; see `_dblp_search`."""
    return net.once(("dblp_search", title), lambda: _dblp_search(net, title))


def _dblp_search(net: Net, title: str) -> list[dict]:
    """DBLP records whose title holds every content word of `title`, through
    DBLP's SPARQL endpoint — the one DBLP service scripted clients can reach
    (dblp.org answers them with a bot-check page, and DBLP issues no API keys).
    Venue, year, pages, DOI and authors in order."""
    words = [
        w for w in re.split(r"[^a-z0-9]+", fold(detex(title, keep_math=False)).lower()) if len(w) > 2 and w not in _STOP
    ][:10]
    if len(words) < 2:
        return []
    query = (
        "PREFIX dblp: <https://dblp.org/rdf/schema#> PREFIX ql: <http://qlever.cs.uni-freiburg.de/builtin-functions/> "
        "SELECT ?pub ?t ?venue ?year ?pages ?doi "
        '(GROUP_CONCAT(DISTINCT CONCAT(STR(?o), "=", ?n); separator="|") AS ?au) WHERE { '
        f'?pub dblp:title ?t . ?text ql:contains-entity ?t . ?text ql:contains-word "{" ".join(words)}" . '
        "?pub dblp:yearOfPublication ?year . OPTIONAL { ?pub dblp:publishedIn ?venue } "
        "OPTIONAL { ?pub dblp:pagination ?pages } OPTIONAL { ?pub dblp:doi ?doi } "
        "OPTIONAL { ?pub dblp:hasSignature ?s . ?s dblp:signatureOrdinal ?o . ?s dblp:signatureDblpName ?n } } "
        "GROUP BY ?pub ?t ?venue ?year ?pages ?doi LIMIT 25"
    )
    body = net.get(
        f"{_DBLP_SPARQL}?{urllib.parse.urlencode({'query': query})}",
        accept="application/sparql-results+json",
        ttl=_MONTH,
        expect_json=True,
    )
    try:
        bindings = json.loads(body or "{}")["results"]["bindings"]
    except _SHAPE_ERRORS:
        return []
    return [r for r in (_dblp_record(b) for b in bindings) if r]


_OPENALEX = "https://api.openalex.org/works"
_OA_SELECT = "doi,display_name,authorships,publication_year,biblio,primary_location,type"


def _openalex_records(w: dict) -> list[dict]:
    """One OpenAlex work as two records for name evidence: the byline as printed
    (`raw_author_name`) and the registry's person names (`display_name`)."""
    if not w or not w.get("display_name"):
        return []
    b = w.get("biblio") or {}
    base = {
        "title": w["display_name"],
        "year": w.get("publication_year"),
        "venue": ((w.get("primary_location") or {}).get("source") or {}).get("display_name"),
        "volume": b.get("volume"),
        "pages": _pages("--".join(x for x in (b.get("first_page"), b.get("last_page")) if x) or None),
        "doi": (w.get("doi") or "").removeprefix("https://doi.org/").lower() or None,
        "type": "article",
    }
    auths = w.get("authorships") or []
    byline = _full_names([_clean_name(a.get("raw_author_name") or "") for a in auths])
    person = _full_names([_clean_name((a.get("author") or {}).get("display_name") or "") for a in auths])
    rid = base["doi"] or w["display_name"]
    src = (w.get("primary_location") or {}).get("source") or {}
    extra = {"issn": [x for x in [src.get("issn_l"), *(src.get("issn") or [])] if x]}
    return [
        _rec("openalex", rid, authors=byline, extra=extra, **base),
        _rec("openalex-registry", rid, authors=person, extra=extra, **base),
    ]


def openalex_by_dois(net: Net, dois: list[str]) -> dict[str, list[dict]]:
    """DOI → OpenAlex records (byline and registry names), 100 DOIs per request."""
    out: dict[str, list[dict]] = {}
    dois = list(dict.fromkeys(d.lower() for d in dois if d and "," not in d and "|" not in d))
    for i in range(0, len(dois), 100):
        q = urllib.parse.urlencode({
            "filter": "doi:" + "|".join(dois[i : i + 100]),
            "per_page": "100",
            "select": _OA_SELECT,
        })
        for w in (net.get_json(f"{_OPENALEX}?{q}", ttl=_MONTH) or {}).get("results") or []:
            recs = _openalex_records(w)
            if recs:
                out[recs[0]["doi"] or ""] = recs
    return out


_OA_SOURCES = "https://api.openalex.org/sources"


_CROSSREF_JOURNALS = "https://api.crossref.org/journals"


def journal_name_by_issn(net: Net, issn: str) -> str | None:
    """A journal's current name as its publisher deposits it with Crossref: the
    container title most of its five latest articles carry. The journal-level
    titles of Crossref and OpenAlex are catalogue forms ("Physical review. E",
    "Machine Learning Science and Technology") and are not used."""
    if not re.fullmatch(r"\d{4}-\d{3}[\dXx]", issn or ""):
        return None
    q = urllib.parse.urlencode({
        "rows": "5",
        "sort": "published",
        "order": "desc",
        "filter": "type:journal-article",
        "select": "container-title",
    })
    data = net.get_json(f"{_CROSSREF_JOURNALS}/{issn.upper()}/works?{q}", ttl=_MONTH) or {}
    names = [_plain(t[0]) for it in (data.get("message") or {}).get("items") or [] if (t := it.get("container-title"))]
    names = [n for n in names if n]
    return max(dict.fromkeys(names), key=names.count) if names else None


def journal_issns_by_search(net: Net, name: str) -> list[str]:
    """The ISSNs of the journal OpenAlex finds by `name` or abbreviation — the
    result whose name, alternate title or abbreviation agrees with it. Only the
    ISSNs are taken; the name itself comes from Crossref (`journal_name_by_issn`)."""
    q = urllib.parse.urlencode({
        "search": detex(name)[:200],
        "per_page": "5",
        "select": "display_name,alternate_titles,abbreviated_title,issn_l,issn",
    })
    for src in (net.get_json(f"{_OA_SOURCES}?{q}", ttl=_MONTH) or {}).get("results") or []:
        forms = [src.get("display_name"), src.get("abbreviated_title"), *(src.get("alternate_titles") or [])]
        if any(f and _venues_agree(name, f) for f in forms):
            return list(dict.fromkeys(str(i) for i in [src.get("issn_l"), *(src.get("issn") or [])] if i))
    return []


def load_journal_aliases(path=None) -> dict[str, str]:
    """The fallback alias table (references/journals.tsv): folded alias → name."""
    from pathlib import Path

    p = Path(path) if path else Path(__file__).with_name("references") / "journals.tsv"
    if not p.exists():
        return {}
    rows = [ln.split("\t") for ln in p.read_text().splitlines() if ln.strip() and not ln.startswith("#")]
    return {venue_key(r[0]): r[1].strip() for r in rows if len(r) >= 2 and r[0] != "alias"}


def canonical_journals(net: Net, items: list[tuple[str, list[str]]], venues: list[dict]) -> list[str | None]:
    """Names only; see `canonical_journals_with_source`."""
    return [name for name, _ in canonical_journals_with_source(net, items, venues)]


def canonical_journals_with_source(
    net: Net, items: list[tuple[str, list[str]]], venues: list[dict]
) -> list[tuple[str | None, str | None]]:
    """Each journal's name from one authority, aligned with `items` ((name, ISSNs)):
    Crossref by the entry's ISSN, else by the ISSN OpenAlex finds for the name,
    else the alias table, else None (keep the name). ML journals in the venue
    table keep the table's name. A current name that is another title — the
    journal was renamed after the article appeared ("The Bulletin of Mathematical
    Biophysics", now "Bulletin of Mathematical Biology") — is not taken: the
    article keeps the name it appeared under. When a source was out of the run,
    the item is (None, "unreachable"): nothing is known, and the caller retries it
    next run.

    One authority means the publisher's current styling is accepted wholesale —
    "PLOS One", "Journal of Neuroscience" without the article — in exchange for
    one consistent name per journal across the bibliography. Whether a name is a
    restyling or another title is `_venues_agree`'s call: a dropped subtitle
    counts as another title, so a 2004 article keeps "The European Physical
    Journal B - Condensed Matter"."""

    def tracked(key: tuple, compute) -> tuple[Any, bool]:
        """A memoised lookup with whether it met a host out of the run — kept
        together, so a later item reusing the answer learns of the miss too."""

        def run() -> tuple[Any, bool]:
            net.begin()
            return compute(), net.missed()

        return net.once(key, run)

    def by_issn(issns: list[str]) -> tuple[str | None, bool]:
        missed = False
        for i in dict.fromkeys(x.upper() for x in issns):
            found, m = tracked(("journal_name", i), lambda i=i: journal_name_by_issn(net, i))
            if found:
                return found, False
            missed = missed or m
        return None, missed

    aliases = load_journal_aliases()
    out: list[tuple[str | None, str | None]] = []
    for name, iss in items:
        if canonical_venue(name, venues):
            out.append((None, None))
            continue
        found, missed = by_issn(iss)
        if found:
            out.append((found, "crossref:issn") if _venues_agree(name, found) else (None, None))
            continue
        issns, m = tracked(("journal_issns", name), lambda n=name: journal_issns_by_search(net, n))
        found, m2 = by_issn(issns)
        if found:
            out.append((found, "crossref:name") if _venues_agree(name, found) else (None, None))
            continue
        if missed or m or m2:
            out.append((None, "unreachable"))
            continue
        alias = aliases.get(venue_key(name))
        out.append((alias, "journals.tsv") if alias else (None, None))
    return out


def openalex_slot(net: Net, volume: str, first_page: str, year: int | None) -> list[dict]:
    """The works OpenAlex places at a volume and first page (in a year): who
    really occupies a journal slot, for any journal OpenAlex indexes."""
    f = f"biblio.volume:{volume},biblio.first_page:{first_page}" + (f",publication_year:{year}" if year else "")
    data = net.get_json(
        f"{_OPENALEX}?{urllib.parse.urlencode({'filter': f, 'per_page': '10', 'select': _OA_SELECT})}", ttl=_MONTH
    )
    return [recs[0] for w in (data or {}).get("results") or [] if (recs := _openalex_records(w))]


_VIRTUAL = {
    "iclr": "International Conference on Learning Representations",
    "neurips": "Advances in Neural Information Processing Systems",
    "icml": "International Conference on Machine Learning",
}


def virtual_index(net: Net, conf: str, year: int) -> list[dict]:
    """Memoised for the run; see `_virtual_index`."""
    return net.once(("virtual_index", conf, year), lambda: _virtual_index(net, conf, year))


def _virtual_index(net: Net, conf: str, year: int) -> list[dict]:
    """Accepted main-track papers of one ICLR / NeurIPS / ICML year from the
    conference site's own list (`<conf>.cc/static/virtual/data/<conf>-<year>-orals-posters.json`):
    ICLR from 2020, and the NeurIPS / ICML years their proceedings indices do
    not cover yet. One download per year, kept for good once the year is over;
    OpenReview's bulk listing is closed to anonymous clients."""
    import datetime

    past = year < datetime.datetime.now().astimezone().year
    data = net.get_json(
        f"https://{conf}.cc/static/virtual/data/{conf}-{year}-orals-posters.json", ttl=_INF if past else _MONTH
    )
    out, seen = [], set()
    for r in (data or {}).get("results") or []:
        title = " ".join((r.get("name") or "").split())
        rid = r.get("paper_url") or r.get("uid") or title
        if not title or rid in seen or not str(r.get("decision") or "Accept").lower().startswith("accept"):
            continue
        seen.add(rid)
        people = r.get("authors") if isinstance(r.get("authors"), list) else []
        out.append(
            _rec(
                f"{conf}-site",
                f"{year}/{rid}",
                type="inproceedings",
                title=title,
                authors=_full_names([a.get("fullname") if isinstance(a, dict) else a for a in people]),
                year=year,
                venue=_VIRTUAL[conf],
                url=r.get("paper_url"),
            )
        )
    return out


def _openreview_record(n: dict) -> dict | None:
    c = n.get("content") or {}
    title, venue, vid = _or_value(c, "title"), _or_value(c, "venue"), _or_value(c, "venueid") or ""
    if not title:
        return None
    ym = re.search(r"\b(19|20)\d{2}\b", f"{venue or ''} {vid}")
    year = int(ym.group(0)) if ym else None
    stamp_ms = n.get("pdate") or n.get("odate")
    if year is None and isinstance(stamp_ms, (int, float)):
        year = time.gmtime(stamp_ms / 1000).tm_year
    status = openreview_status(vid, venue)
    bib = _or_value(c, "_bibtex") or ""
    bt = re.search(r"\bbooktitle\s*=\s*\{([^}]*)\}|\bjournal\s*=\s*\{([^}]*)\}", bib)
    link = _or_value(c, "html") or ""
    doi = re.search(r"doi\.org/(10\.\S+)", link)
    return _rec(
        "openreview",
        str(n.get("forum") or n.get("id") or ""),
        type="article" if vid == "TMLR" or vid.startswith("dblp.org/journals") else "inproceedings",
        title=title,
        authors=_full_names(_or_value(c, "authors") or []),
        year=year,
        venue=venue or (bt and (bt.group(1) or bt.group(2))),
        doi=doi.group(1).lower() if doi else None,
        url=link or None,
        extra={"venueid": vid, "status": status, "dblp": vid.startswith("dblp.org")},
    )


def openreview_search(net: Net, title: str, year: int | None = None) -> list[dict]:
    """Memoised for the run; see `_openreview_search`."""
    return net.once(("openreview_search", title, year), lambda: _openreview_search(net, title, year))


def _openreview_search(net: Net, title: str, year: int | None = None) -> list[dict]:
    """Title search over OpenReview (both API generations). Besides ICLR, TMLR and
    recent NeurIPS/ICML, OpenReview mirrors DBLP records (`venueid`
    `dblp.org/conf/<VENUE>/<YEAR>`), which stands in for DBLP itself — dblp.org
    answers scripted clients with a bot-check page. The older API is asked only
    when the newer one holds no publication with this exact title, and only for work
    from 2019 or earlier (what it alone still holds: ICLR 2018–2019 and older
    DBLP records). OpenReview allows 20 requests a minute on the newer API and 5
    on the older — the scarcest budgets of any source here."""
    out, seen = [], set()
    q = urllib.parse.quote(title[:250])
    for api in ("api2.openreview.net", "api.openreview.net"):
        if api == "api.openreview.net" and (
            any(r["extra"]["status"] == "published" and title_match(title, r["title"]) == "exact" for r in out)
            or (year is not None and year > 2019)
        ):
            break
        data = net.get_json(
            f"https://{api}/notes/search?term={q}&type=terms&content=title&source=forum&limit=10", ttl=_MONTH
        )
        for n in (data or {}).get("notes") or []:
            r = _openreview_record(n)
            if r and (r["title"], r["venue"]) not in seen:
                seen.add((r["title"], r["venue"]))
                out.append(r)
    return out


def neurips_index(net: Net, year: int) -> list[dict]:
    """Memoised for the run; see `_neurips_index`."""
    return net.once(("neurips_index", year), lambda: _neurips_index(net, year))


def _neurips_index(net: Net, year: int) -> list[dict]:
    """All papers of one NeurIPS year from papers.nips.cc (title, authors, track, hash)."""
    import datetime

    past = year < datetime.datetime.now().astimezone().year
    body = net.get(f"https://papers.nips.cc/paper_files/paper/{year}", ttl=_INF if past else _MONTH)
    out = []
    for li in re.findall(r"<li[^>]*>(.*?)</li>", body or "", re.DOTALL):
        m = re.search(
            r'href="/paper_files/paper/\d+/hash/([0-9a-f]+)-Abstract(?:-([A-Za-z_]+))?\.html">(.*?)</a>', li, re.DOTALL
        )
        if not m:
            continue
        au = re.search(r'class="paper-authors">(.*?)</span>', li, re.DOTALL)
        track = m.group(2) or "Conference"
        out.append(
            _rec(
                "neurips",
                f"{year}/{m.group(1)}",
                type="inproceedings",
                title=_plain(m.group(3)),
                authors=_full_names((_plain(au.group(1)) or "").split(",")) if au else [],
                year=year,
                venue="Advances in Neural Information Processing Systems",
                volume=str(year - 1987),
                extra={"hash": m.group(1), "track": track},
            )
        )
    return out


def neurips_bib(net: Net, rec: dict) -> dict:
    """Complete a NeurIPS index record (pages, publisher) from its official BibTeX."""
    year, h, track = rec["year"], rec["extra"]["hash"], rec["extra"].get("track", "Conference")
    ents = []
    for suffix in ("", f"-{track}"):
        body = net.get(f"https://papers.nips.cc/paper_files/paper/{year}/file/{h}-Bibtex{suffix}.bib", ttl=_INF)
        ents = parse_bib(body or "")["entries"]
        if ents:
            break
    if not ents:
        return rec
    f = ents[0]["fields"]
    return {
        **rec,
        "pages": f.get("pages") or rec["pages"],
        "publisher": f.get("publisher"),
        "volume": f.get("volume") or rec["volume"],
    }


def pmlr_volumes(net: Net) -> dict[tuple[str, int], int]:
    """Memoised for the run; see `_pmlr_volumes`."""
    return net.once(("pmlr_volumes",), lambda: _pmlr_volumes(net))


def _pmlr_volumes(net: Net) -> dict[tuple[str, int], int]:
    """(acronym, year) → PMLR volume, from the index labels ("Proceedings of ICML
    2023", "COLT 2020 Proceedings", "COLT 2019"); workshop volumes ("GRaM at ICML
    2024") do not match."""
    body = net.get("https://proceedings.mlr.press/", ttl=_MONTH)
    out = {}
    for v, label in re.findall(r'<li><a href="v(\d+)"><b>Volume \d+</b></a>\s*([^<]*)</li>', body or ""):
        m = re.match(r"\s*(?:Proceedings of )?([A-Za-z][A-Za-z\-]*) ((?:19|20)\d{2})(?: Proceedings)?\s*$", label)
        if m:
            out.setdefault((m.group(1).upper(), int(m.group(2))), int(v))
    return out


def pmlr_volume(net: Net, volume: int) -> list[dict]:
    """Memoised for the run; see `_pmlr_volume`."""
    return net.once(("pmlr_volume", volume), lambda: _pmlr_volume(net, volume))


def _pmlr_volume(net: Net, volume: int) -> list[dict]:
    """Every paper of one PMLR volume, from its bibliography.bib."""
    body = net.get(f"https://proceedings.mlr.press/v{volume}/assets/bib/bibliography.bib", ttl=_INF)
    out = []
    for e in parse_bib(body or "")["entries"]:
        f = e["fields"]
        if e["type"] != "inproceedings" or "title" not in f:
            continue
        out.append(
            _rec(
                "pmlr",
                f"v{volume}/{e['key']}",
                type="inproceedings",
                title=detex(f["title"]),
                authors=split_authors(f.get("author", "")),
                year=int(f["year"]) if f.get("year", "").isdigit() else None,
                venue=detex(f.get("booktitle", "")),
                volume=str(volume),
                pages=f.get("pages"),
                publisher=f.get("publisher") or "PMLR",
                series="Proceedings of Machine Learning Research",
                url=f.get("url"),
            )
        )
    return out


def jmlr_volume(net: Net, volume: int) -> list[dict]:
    """Memoised for the run; see `_jmlr_volume`."""
    return net.once(("jmlr_volume", volume), lambda: _jmlr_volume(net, volume))


def _jmlr_volume(net: Net, volume: int) -> list[dict]:
    """Every paper of one JMLR volume (title, authors, paper number, pages, year).
    Recent volumes read `(73):1−61, 2020` (paper number, pages); early ones
    `5(Nov):1457--1469, 2004` (month, pages) and leave `<dt>` unclosed."""
    import datetime

    past = volume < datetime.datetime.now().astimezone().year - 1999
    body = net.get(f"https://jmlr.org/papers/v{volume}/", ttl=_INF if past else _MONTH)
    out = []
    for dl in re.findall(r"<dl>(.*?)</dl>", body or "", re.DOTALL):
        t = re.search(r"<dt>(.*?)(?:</dt>|<dd>)", dl, re.DOTALL)
        a = re.search(r"<i>(.*?)</i>", dl, re.DOTALL)
        n = re.search(r"\((\w+)\):([0-9]+)\s*(?:&minus;|−|--|-|–)\s*([0-9]+),\s*((?:19|20)\d{2})", dl)
        pid = re.search(r"/papers/v\d+/([^\"'/]+)\.html", dl)
        if not (t and n):
            continue
        out.append(
            _rec(
                "jmlr",
                f"v{volume}/{pid.group(1) if pid else n.group(1)}",
                type="article",
                title=_plain(t.group(1)),
                authors=_full_names((_plain(a.group(1)) or "").split(",")) if a else [],
                year=int(n.group(4)),
                venue="Journal of Machine Learning Research",
                volume=str(volume),
                number=n.group(1) if n.group(1).isdigit() else None,
                pages=f"{n.group(2)}--{n.group(3)}",
            )
        )
    return out


# ── Identity: strict and soft matching ──────────────────────────────────────

_STOP = frozenset([
    "a",
    "an",
    "the",
    "of",
    "in",
    "on",
    "for",
    "to",
    "and",
    "or",
    "with",
    "without",
    "by",
    "from",
    "at",
    "as",
    "into",
    "onto",
    "via",
    "vs",
    "versus",
    "is",
    "are",
    "be",
    "towards",
    "toward",
    "about",
    "over",
    "under",
    "between",
    "through",
    "its",
    "it",
    "this",
    "that",
    "these",
    "those",
    "do",
    "does",
    "can",
    "der",
    "die",
    "das",
    "den",
    "dem",
    "des",
    "ein",
    "eine",
    "einer",
    "eines",
    "und",
    "oder",
    "zur",
    "zum",
    "zu",
    "im",
    "am",
    "vom",
    "von",
    "fur",
    "uber",
    "mit",
    "bei",
    "auf",
    "aus",
    "le",
    "la",
    "les",
    "un",
    "une",
    "des",
    "du",
    "de",
    "et",
    "ou",
    "au",
    "aux",
    "en",
    "sur",
    "pour",
    "par",
    "dans",
    "avec",
    "il",
    "lo",
    "gli",
    "i",
    "una",
    "uno",
    "di",
    "da",
    "del",
    "della",
    "dei",
    "delle",
    "degli",
    "nel",
    "nella",
    "per",
    "con",
    "su",
    "tra",
    "fra",
    "e",
    "o",
    "al",
    "alla",
    "el",
    "los",
    "las",
    "unos",
    "unas",
    "y",
    "con",
    "por",
    "para",
    "sobre",
])

SOFT_RATIO = 0.92
"""Character similarity (difflib) between normalised titles above which two
titles that differ by at most one content word count as a soft match. Pinned by
the fixtures in tests: typos and spelling variants pass, one-word-prefixed
follow-ups ("Improved …") do not."""


@functools.lru_cache(maxsize=1 << 16)
def title_tokens(title: str | None) -> tuple[str, ...]:
    """Title → folded lower-case content tokens: markup, math, punctuation and
    articles/prepositions (en, de, fr, it, es) dropped, so "The Brain's Code"
    and "brains code" compare equal."""
    t = fold(detex(_plain(title) or "", keep_math=False)).lower()
    t = re.sub(r"['’]s\b", "s", t)
    return tuple(w for w in re.split(r"[^a-z0-9]+", t) if w and w not in _STOP)


def _main_title(title: str) -> str:
    """The part of a title before its subtitle separator."""
    return re.split(r"\s*(?::|\?|\s[-–—]\s|\.\s)\s*", detex(title or ""), maxsplit=1)[0]


def title_match(a: str | None, b: str | None) -> str:
    """ "exact" | "soft" | "none" for two titles (see SOFT_RATIO and `_main_title`)."""
    import difflib

    ta, tb = title_tokens(a), title_tokens(b)
    if not ta or not tb:
        return "none"
    ja, jb = "".join(ta), "".join(tb)
    if ja == jb:
        return "exact"
    ma, mb = "".join(title_tokens(_main_title(a or ""))), "".join(title_tokens(_main_title(b or "")))
    if min(len(title_tokens(_main_title(a or ""))), len(title_tokens(_main_title(b or "")))) >= 2 and (
        ma == jb or mb == ja or ma == mb
    ):
        return "soft"
    if abs(len(ta) - len(tb)) <= 1 and difflib.SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio() >= SOFT_RATIO:
        return "soft"
    return "none"


def _same_person(x: dict, y: dict) -> bool:
    """Surname match tolerant of particles, missing accents and given/family swaps
    (OpenReview lists "Liu Ziyin" where DBLP has "Ziyin Liu")."""
    if x.get("others") or y.get("others"):
        return False
    sx, sy = surname(x), surname(y)
    if sx and sy and (sx == sy or sx.endswith(sy) or sy.endswith(sx)):
        return True
    lx, ly = (re.sub(r"[^a-z0-9]", "", fold(detex(n.get("last", ""))).lower()) for n in (x, y))
    if lx and lx == ly:
        return True  # "v. Neumann" and "von Neumann": particles spelled differently
    tx, ty = name_tokens(x), name_tokens(y)
    return bool(sx and sx in {re.sub(r"[^a-z0-9]", "", t) for t in ty}) or bool(
        sy and sy in {re.sub(r"[^a-z0-9]", "", t) for t in tx}
    )


def author_match(ea: list[dict], ca: list[dict]) -> str:
    """ "ok" (first authors agree) | "order" (entry's first author is among the
    candidate's first three) | "unknown" (either list empty) | "none"."""
    ea = [a for a in ea if not a.get("others")]
    if not ea or not ca:
        return "unknown"
    if _same_person(ea[0], ca[0]):
        return "ok"
    return "order" if any(_same_person(ea[0], c) for c in ca[1:3]) else "none"


def _same_author_list(ea: list[dict], ca: list[dict]) -> bool:
    """Two or more authors, the same people in the same order."""
    ea = [a for a in ea if not a.get("others")]
    return len(ea) >= 2 and len(ea) == len(ca) and all(_same_person(x, y) for x, y in zip(ea, ca, strict=True))


def same_work(entry_view: dict, cand: dict, linked: bool = False) -> str:
    """Identity verdict for an entry and a source record: "exact" | "soft" | "no".

    Strict: exact title and agreeing first author. Soft: an exact title with the
    author order off or unknown, or a soft title with agreeing first authors and
    a year within one (or any year when the two are linked by an identifier). A title
    that does not match, or a first author found nowhere near the top of the
    candidate's list, is never the same work."""
    t = title_match(entry_view.get("title"), cand.get("title"))
    a = author_match(entry_view.get("authors") or [], cand.get("authors") or [])
    if t == "none" and linked and _same_author_list(entry_view.get("authors") or [], cand.get("authors") or []):
        return "soft"  # the identifier's own record under a later title: renamed across versions
    if t == "none" or a == "none":
        return "no"
    if t == "exact":
        return "exact" if a == "ok" else "soft"
    if a != "ok" and not linked:
        return "no"
    ey, cy = entry_view.get("year"), cand.get("year")
    if linked or ey is None or cy is None or abs(ey - cy) <= 1:
        return "soft"
    return "no"


def entry_view(entry: dict) -> dict:
    """The comparable facts of an entry: plain title, split authors, year, venue."""
    f = entry["fields"]
    y = re.search(r"\b(1[5-9]|20)\d{2}\b", f.get("year", "") or f.get("date", ""))
    return {
        "title": detex(f.get("title", "")),
        "authors": split_authors(f.get("author", "")) if f.get("author") else [],
        "year": int(y.group(0)) if y else None,
        "venue": detex(f.get("journal") or f.get("booktitle") or f.get("howpublished") or ""),
        "type": entry["type"],
        "publisher": detex(f.get("publisher", "")),
    }


# ── Venues ───────────────────────────────────────────────────────────────────

_ORDINAL = re.compile(
    r"\b(?:(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)[\s-]?)?"
    r"(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth)\b"
    r"|\b(?:tenth|eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth"
    r"|nineteenth|twentieth|thirtieth|fortieth|fiftieth|sixtieth|seventieth|eightieth|ninetieth|hundredth)\b"
    r"|\b\d+(?:st|nd|rd|th)\b",
    re.IGNORECASE,
)


def load_venues(path=None) -> list[dict]:
    """The canonical-venue table (references/venues.tsv next to this file)."""
    from pathlib import Path

    p = Path(path) if path else Path(__file__).with_name("references") / "venues.tsv"
    rows = []
    for line in p.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        cols = line.split("\t")
        if cols[0] == "acronym":
            continue
        acronym, kind, canonical, pattern, adapter = (cols + [""] * 5)[:5]
        rows.append({
            "acronym": acronym,
            "type": kind,
            "canonical": canonical,
            "re": re.compile(pattern, re.IGNORECASE),
            "adapter": adapter,
        })
    return rows


def venue_key(text: str | None) -> str:
    """Folded, lower-case, punctuation-free venue text for pattern matching."""
    return " ".join(re.split(r"[^a-z0-9/]+", fold(detex(text or "")).lower())).strip()


def canonical_venue(text: str | None, venues: list[dict]) -> dict | None:
    """The table row a venue string names, or None. Workshops never resolve to
    their host conference: "Workshop at ICLR" is not ICLR."""
    k = venue_key(text or "")
    if not k or "workshop" in k:
        return None
    for row in venues:
        if row["re"].search(k):
            return row
    return None


def clean_venue_name(text: str) -> str:
    """Strip edition, year and "(ACRONYM YEAR)" from a proceedings title the
    table does not know: "Proceedings of the Tenth Italian Conference on
    Computational Linguistics (CLiC-it 2024)" → "Proceedings of the Italian
    Conference on Computational Linguistics". A bare conference name becomes
    "Proceedings of the <conference>": "2023 Systems and Information Engineering
    Design Symposium (SIEDS)" → "Proceedings of the Systems and Information
    Engineering Design Symposium"."""
    s = detex(text)
    s = re.sub(r"\s*\([^()]*\b(?:19|20)\d{2}\b[^()]*\)", "", s)
    s = re.sub(r"\b(?:19|20)\d{2}\b", "", s)
    s = _ORDINAL.sub("", s)
    s = re.sub(r",?\s*(?:Volume|Vol\.)\s*\d+\s*:?[^,]*$", "", s)
    s = re.sub(r"\s*\([A-Z][A-Za-z0-9\-]{1,14}\)\s*$", "", s)
    s = re.sub(r"\s+", " ", s).strip(" ,:;-–")
    s = re.sub(r"^(?:the|The)\s+", "", s)
    named = re.match(r"(?:Proceedings|Advances|Findings|Transactions|Journal|Lecture Notes|Annals|Communications)\b", s)
    if not named and re.search(r"\b(?:Conference|Symposium|Workshop|Meeting|Congress|Colloquium|Forum|Summit)\b", s):
        s = "Proceedings of the " + s  # a conference's name, not a publication's
    return s


# ── Corrections ──────────────────────────────────────────────────────────────


def _richer(a: str, b: str) -> str:
    """Of two spellings of the same name part, the one with more information:
    diacritics, then length, and never an ALL-CAPS rendering."""

    def score(s: str) -> tuple:
        p = detex(s)
        return (not (p.isupper() and len(p) > 1), sum(ord(c) > 127 for c in p), len(p.replace(".", "")))

    return a if score(a) >= score(b) else b


def _initials(given: str) -> str:
    return "".join(w[0] for w in re.findall(r"[A-Za-z]+", fold(detex(given))))


def _is_abbreviated(given: str) -> bool:
    words = re.findall(r"[^\s.\-]+", detex(given))
    return bool(words) and all(len(w) == 1 for w in words)


def _given(entry_given: str, source_given: str) -> str:
    """The entry's given name only where the source's is its abbreviation or an
    accent-poorer spelling ("G." vs "Giovanni", "Gyorgy" vs "György"); otherwise
    the source's, which also drops what a mis-split surname left behind
    ("Javier Del" when the source has "Javier" and "Del Ser")."""
    e, src = detex(entry_given), source_given
    if not e:
        return src
    if not src:
        return e
    if fold(e).lower() == fold(src).lower():
        return _richer(e, src)
    if _is_abbreviated(src) and _initials(e).lower().startswith(_initials(src).lower()):
        return e
    return src


def merge_authors(ea: list[dict], ca: list[dict]) -> list[dict]:
    """Authors after correction: the source's list and order. For each person
    the surname (particles included, as one unit) is the entry's only when it is
    the same name modulo accents and case and the richer spelling, so a source
    that drops accents or abbreviates never degrades the entry, and one that
    files a particle differently never duplicates it."""
    ea = [a for a in ea if not a.get("others")]
    if len(ea) != len(ca) or not all(_same_person(x, y) for x, y in zip(ea, ca, strict=False)):
        return [dict(c) for c in ca]
    out = []
    for x, y in zip(ea, ca, strict=True):
        if "{" in y.get("last", ""):
            out.append(dict(y))
            continue
        xs = detex(" ".join(v for v in (x.get("von", ""), x.get("last", "")) if v))
        ys = " ".join(v for v in (y.get("von", ""), y.get("last", "")) if v)
        same = re.sub(r"[^a-z]", "", fold(xs).lower()) == re.sub(r"[^a-z]", "", fold(ys).lower())
        von, last = (
            (x.get("von", ""), detex(x.get("last", "")))
            if same and _richer(xs, ys) == xs
            else (y.get("von", ""), y.get("last", ""))
        )
        out.append({
            "first": _given(x.get("first", ""), y.get("first", "")),
            "von": von,
            "last": last,
            "jr": x.get("jr", "") or y.get("jr", ""),
        })
    return out


def _given_tokens(given: str) -> list[str]:
    """Given names as tokens, a hyphenated name kept as one token ("Jean-Pierre",
    "J.-P."), and initials written together split apart ("GT" → "G.", "T.")."""
    toks = [t for t in re.split(r"\s+|(?<=\.)(?=[A-Za-zÀ-ÿ])", detex(given).strip()) if t.strip(".")]
    out: list[str] = []
    for t in toks:
        if re.fullmatch(r"[A-Z]{2,3}\.?", t):
            out += [f"{c}." for c in t.rstrip(".")]
        else:
            out.append(t)
    return out


def _theirs(a: dict, b: dict, authors: list[dict]) -> bool:
    """Whether byline name `b` (same surname as `a`) belongs to another author of
    the entry — a co-author sharing the surname whose given names fit `b`."""
    return any(
        o is not a
        and not o.get("others")
        and _same_person(o, b)
        and _merge_given(detex(o.get("first", "")), detex(b.get("first", ""))) is not None
        for o in authors
    )


_NAME_SUFFIX = re.compile(r"(?:jr|sr|jnr|snr)\.?|[ivx]{1,4}|\d+(?:st|nd|rd|th)", re.IGNORECASE)
"""What the middle part of `Last, Jr, First` may hold: Jr., Sr., a Roman numeral, an ordinal."""


def malformed_names(field: str) -> list[str]:
    """Names in an author or editor field that BibTeX misreads, each with the
    reason — as a rule a missing "and": a middle part that is no suffix
    ("Devries, Paul L. Hasburn, Javier E." is one person with the suffix "Paul L.
    Hasburn"), or more than two commas in one name. Which reading was meant is
    written nowhere, so they are listed for review, never repaired."""
    out = []
    for n in _split_top(field or "", r"\s+and\s+"):
        parts = [p.strip() for p in _split_top(n, r",")]
        name = " ".join(n.split())
        if len(parts) > 3:
            out.append(f'{name}: {len(parts) - 1} commas in one name (a missing "and"?)')
        elif len(parts) == 3 and parts[1] and not _NAME_SUFFIX.fullmatch(detex(parts[1])):
            out.append(f'{name}: "{parts[1]}" is not a name suffix (a missing "and"?)')
    return out


def name_conflicts(authors: list[dict], evidence: list[dict]) -> list[str]:
    """Authors whose given names two byline records spell incompatibly (initials
    that disagree): left as they are, and listed for a human — or the agent — to
    judge."""
    out = []
    lists = [r.get("authors") or [] for r in evidence if r.get("source") in BYLINE_SOURCES]
    for a in authors:
        if a.get("others") or "{" in a.get("last", ""):
            continue
        forms = {
            detex(b.get("first", ""))
            for bl in lists
            for b in bl
            if _same_person(a, b) and b.get("first") and not _theirs(a, b, authors)
        }
        forms.add(detex(a.get("first", "")))
        forms.discard("")
        if any(_merge_given(x, y) is None for x in forms for y in forms if x < y):
            out.append(f"{detex(join_name(a))}: bylines give {' / '.join(sorted(forms))}")
    return out


def _token_initials(tok: str) -> str:
    return "".join(p[0] for p in re.findall(r"[A-Za-z]+", fold(tok))).lower()


def _fuller_token(a: str, b: str) -> str | None:
    """The fuller of two spellings of one given name, or None when they are two
    names. An initial or abbreviation expands to the name it starts ("J." / "John"
    → "John"; "J.-P." / "Jean-Pierre" → "Jean-Pierre"); two written names agree
    only when they are one name up to accents and case ("Jose" / "José" → "José").
    "Ben" and "Benedict" are two names: which one the paper prints is not ours to
    choose."""
    if _token_initials(a) != _token_initials(b):
        return None

    def letters(t: str) -> str:
        return re.sub(r"[^A-Za-zÀ-ÿ]", "", t)

    def written(t: str) -> bool:
        return len(letters(t)) > 1 and not t.endswith(".")

    if written(a) and written(b) and fold(letters(a)).lower() != fold(letters(b)).lower():
        return None

    def score(t: str) -> tuple[int, int]:
        return (len(letters(t)), sum(ord(c) > 127 for c in t))

    return b if score(b) > score(a) else a


def _merge_given(a: str, b: str) -> str | None:
    """Token-wise union of two given-name spellings of one person, each position
    taking its fuller attested spelling ("J. L." + "John" → "John L."); None when
    any aligned pair is two names (`_fuller_token`)."""
    ta, tb = _given_tokens(a), _given_tokens(b)
    out = []
    for i in range(max(len(ta), len(tb))):
        if i >= len(ta) or i >= len(tb):
            out.append((ta + tb[len(ta) :])[i] if i >= len(ta) else ta[i])
            continue
        f = _fuller_token(ta[i], tb[i])
        if f is None:
            return None
        out.append(f)
    return " ".join(out)


def _richer_surname(a: str, b: str) -> str:
    """Of two spellings of one surname (equal once folded), the more informative:
    never ALL CAPS, then more diacritics, then inner capitals ("LeCun" over "Lecun")."""

    def score(t: str) -> tuple:
        return (not (t.isupper() and len(t) > 1), sum(ord(c) > 127 for c in t), sum(c.isupper() for c in t[1:]))

    return b if score(b) > score(a) else a


def fullest_names(authors: list[dict], evidence: list[list[dict]]) -> tuple[list[dict], list[str]]:
    """Each author's fullest attested name, from records of the same work (and
    the author registries behind them) that name the same person: given names
    completed token by token when every aligned initial agrees ("G." → "Giovanni",
    "J. L." + "John" → "John L."), an abbreviated particle spelled out ("v." →
    "von"), and the surname in its most informative spelling ("Buzsaki" →
    "Buzsáki", "Lecun" → "LeCun"). Nothing is inferred beyond what a record
    spells. BibTeX reads "J. V. Neumann" as given names "J. V."; a record giving
    "John" with the particle "von" resolves that trailing "V." as the particle.
    Returns the names and one line per changed author, naming the sources."""
    out, notes = [], []
    for a in authors:
        if a.get("others") or "{" in a.get("last", ""):
            out.append(a)
            continue
        cur = {
            **a,
            "first": detex(a.get("first", "")),
            "von": detex(a.get("von", "")),
            "last": detex(a.get("last", "")),
        }
        start, sources = join_name(cur), []
        for records in evidence:
            same = [b for b in records if not b.get("others") and "{" not in b.get("last", "") and _same_person(cur, b)]
            fits = [
                b
                for b in same
                if _merge_given(cur["first"], detex(b.get("first", ""))) is not None and not _theirs(a, b, authors)
            ]
            for b in fits if len(fits) == 1 else []:  # two same-surname names that both fit: ambiguous, skip
                bfirst, bvon, blast = detex(b.get("first", "")), detex(b.get("von", "")), detex(b.get("last", ""))
                if re.sub(r"[^a-z]", "", fold(blast).lower()) != re.sub(r"[^a-z]", "", fold(cur["last"]).lower()):
                    continue
                first, von = cur["first"], cur["von"]
                toks = _given_tokens(first)
                if (
                    bvon
                    and not von
                    and len(toks) > len(_given_tokens(bfirst))
                    and _token_initials(toks[-1]) == bvon[0].lower()
                ):
                    first, von = " ".join(toks[:-1]), toks[-1]  # "J. V." + "John von": V. was the particle
                merged = _merge_given(first, bfirst) if bfirst else first
                if merged is None:
                    continue
                if bvon and (not von or (re.fullmatch(r"[A-Za-z]\.?", von) and bvon[0].lower() == von[0].lower())):
                    von = bvon if len(bvon) >= len(von) else von
                new = {**cur, "first": merged, "von": von, "last": _richer_surname(cur["last"], blast)}
                if new != cur:
                    cur = new
                    sources.append(b.get("_source", "record"))
        if sources:
            notes.append(f"{start} → {join_name(cur)} ({', '.join(dict.fromkeys(sources))})")
        out.append(cur)
    return out, notes


BYLINE_SOURCES = frozenset({"crossref", "arxiv", "arxiv-comment", "neurips", "pmlr", "jmlr", "openalex"})
"""Sources whose author names are the paper's own byline: the publisher's
metadata (Crossref), the authors' submission (arXiv via DataCite), the
proceedings' own listings, and OpenAlex's `raw_author_name`. Registries and
profiles — OpenAlex's disambiguated person names, DBLP, Semantic Scholar,
OpenReview, the conference sites — name the person, not what the paper prints,
so they never complete or rewrite a name."""


def complete_names(entry: dict, evidence: list[dict]) -> tuple[dict, list[dict]]:
    """The entry with `fullest_names` applied to its authors, from the byline
    records in `evidence` (see `BYLINE_SOURCES`), and the change that made."""
    evidence = [r for r in evidence if r.get("source") in BYLINE_SOURCES]
    if not evidence or not entry["fields"].get("author"):
        return entry, []
    lists = [[{**a, "_source": r["source"]} for a in r.get("authors") or []] for r in evidence]
    names, notes = fullest_names(split_authors(entry["fields"]["author"]), lists)
    if not notes:
        return entry, []
    text = authors_field(names)
    change = {"field": "author", "old": entry["fields"]["author"], "new": text, "source": "names: " + "; ".join(notes)}
    return {**entry, "fields": {**entry["fields"], "author": text}}, [change]


def authors_field(names: list[dict]) -> str:
    return " and ".join(join_name(n) for n in names)


def _same_authors_text(a: str, b: str) -> bool:
    na, nb = split_authors(a), split_authors(b)
    return len(na) == len(nb) and all(detex(join_name(x)) == detex(join_name(y)) for x, y in zip(na, nb))


# ── Entry classification and identifiers ────────────────────────────────────

_WEB_TYPES = frozenset({"online", "www", "electronic", "software", "webpage", "dataset"})
_UNINDEXED_TYPES = frozenset({
    "phdthesis",
    "mastersthesis",
    "thesis",
    "techreport",
    "report",
    "manual",
    "unpublished",
    "proceedings",
})
_PLACEHOLDER = re.compile(r"^\s*(?:todo|tbd|tba|xxx+|title|untitled|none|null|n/?a|\?+)\s*$", re.IGNORECASE)
_ML_CATEGORIES = ("cs.", "stat.ML", "math.OC", "eess.")


def identifiers(entry: dict) -> dict:
    """DOI, arXiv id (with any pinned version) and proceedings links found in
    the entry's fields, URLs and notes."""
    f = entry["fields"]
    blob = " ".join(
        f.get(k, "")
        for k in ("doi", "url", "note", "howpublished", "journal", "eprint", "arxiv", "archiveprefix", "pdf")
    )
    out: dict = {}
    m = re.search(r"(10\.\d{4,9}/[^\s{}\"'<>]+)", f.get("doi", "") or blob)
    if m:
        d = m.group(1).rstrip(".,;").lower()
        if d.startswith("10.48550/arxiv."):
            out["arxiv"] = d.split("arxiv.", 1)[1]
        else:
            out["doi"] = d
    ep = f.get("eprint", "").strip()
    arxiv_ctx = "arxiv" in (f.get("archiveprefix", "") + f.get("eprinttype", "")).lower() or re.fullmatch(
        _ARXIV_ID + r"(v\d+)?", ep
    )
    m = re.search(rf"(?:arxiv\.org/(?:abs|pdf)/|arXiv:\s*)({_ARXIV_ID})(v\d+)?", blob, re.IGNORECASE)
    if ep and arxiv_ctx:
        m2 = re.match(rf"(?:arXiv:)?({_ARXIV_ID})(v\d+)?", ep, re.IGNORECASE)
        if m2:
            out["arxiv"], out["arxiv_version"] = m2.group(1), m2.group(2)
    elif m:
        out["arxiv"], out["arxiv_version"] = m.group(1), m.group(2)
    for pat, name in (
        (r"proceedings\.mlr\.press/v(\d+)/", "pmlr"),
        (
            r"(?:papers|proceedings)\.n(?:eur)?ips\.cc/paper(?:_files/paper)?/(\d{4})/(?:hash|file)/([0-9a-f]{20,})",
            "neurips",
        ),
        (r"openreview\.net/(?:forum|pdf)\?id=([A-Za-z0-9_\-]+)", "openreview"),
        (r"jmlr\.org/papers/v(\d+)/", "jmlr"),
    ):
        m = re.search(pat, blob)
        if m:
            out[name] = m.groups()
    return {k: v for k, v in out.items() if v}


def is_web(entry: dict) -> bool:
    """True when the thing cited is itself a website, repository or piece of
    software, so its URL is the citation rather than an optional link."""
    f = entry["fields"]
    if entry["type"] in _WEB_TYPES:
        return True
    if entry["type"] != "misc":
        return False
    if any(k in f for k in ("journal", "booktitle", "school", "institution", "eprint")) or "arxiv" in identifiers(
        entry
    ):
        return False
    return bool(f.get("url") or re.search(r"\\url\{|https?://", f.get("howpublished", "")))


def garbage_reason(entry: dict) -> str | None:
    """Why an entry cannot be a citation (no title and no author/editor, or a
    placeholder title with no author), or None."""
    f = entry["fields"]
    title = detex(f.get("title", ""))
    who = f.get("author") or f.get("editor") or f.get("organization") or f.get("institution")
    if not f:
        return "empty entry"
    if not title and not who and not f.get("url") and not identifiers(entry):
        return "no title, no author and no identifier"
    if (not title or _PLACEHOLDER.match(title)) and not who and not identifiers(entry):
        return f"placeholder title {title!r} with no author"
    return None


def _year_of(s: str) -> int | None:
    m = re.search(r"\b(1[5-9]|20)\d{2}\b", s or "")
    return int(m.group(0)) if m else None


def _hint_venues(text: str | None, venues: list[dict]) -> list[tuple[dict, int]]:
    """(venue row, year) pairs named in an arXiv comment or journal-ref such as
    "Appears in COLT 2019" or "Published at the 3rd ICLR, San Diego, 2015". Only
    affirmative wording counts: "submitted to ICLR 2016" names no publication."""
    if not text:
        return []
    k = venue_key(text)
    if "workshop" in k or re.search(r"\b(?:submitted|under review|in submission|under submission)\b", k):
        return []
    if not re.search(
        r"\b(?:accepted|published|appears?|appearing|to appear|presented|camera ready|proceedings|conference paper|oral|spotlight|poster)\b",
        k,
    ):
        return []
    out = []
    for row in venues:
        m = row["re"].search(k) or (row["acronym"] and re.search(rf"\b{re.escape(row['acronym'].lower())}\b", k))
        if m:
            y = _year_of(k[m.start() :]) or _year_of(k)
            if y:
                out.append((row, y))
    return out


# ── Lookups ──────────────────────────────────────────────────────────────────


def _venue_candidates(net: Net, row: dict, year: int, title: str) -> list[dict]:
    """Records for `title` from the index of one venue-year (NeurIPS, PMLR, JMLR, OpenReview)."""
    return [r for r in venue_pool(net, row, year, title) if title_match(title, r["title"]) != "none"]


def venue_pool(net: Net, row: dict, year: int, title: str | None = None) -> list[dict]:
    """Every paper of one venue-year that an index can list (NeurIPS, PMLR, JMLR,
    the ICLR/NeurIPS/ICML conference sites), else OpenReview's hits for `title`.
    An empty list means no index covers that venue-year."""
    adapter = row.get("adapter") or ""
    if adapter == "neurips":
        pool = neurips_index(net, year)
        return pool if len(pool) > 100 else virtual_index(net, "neurips", year)
    if adapter == "pmlr:ICML":
        vol = pmlr_volumes(net).get(("ICML", year))
        return pmlr_volume(net, vol) if vol else virtual_index(net, "icml", year)
    if adapter.startswith("pmlr:"):
        vol = pmlr_volumes(net).get((adapter.split(":", 1)[1].upper(), year))
        return pmlr_volume(net, vol) if vol else []
    if adapter == "iclr":
        pool = virtual_index(net, "iclr", year)
        if pool or not title:
            return pool
        return [
            r for r in openreview_search(net, title, year) if r["extra"]["status"] == "published" and r["year"] == year
        ]
    if adapter == "jmlr":
        return jmlr_volume(net, year - 1999) + jmlr_volume(net, year - 2000) if year >= 2001 else []
    if adapter.startswith("openreview") and title:
        return [
            r for r in openreview_search(net, title, year) if r["extra"]["status"] == "published" and r["year"] == year
        ]
    return []


def _complete(net: Net, rec: dict) -> dict:
    """Fill in what an index record lacks: pages for NeurIPS, full metadata for a
    DBLP-via-OpenReview record that links a DOI or a proceedings page."""
    if rec["source"] == "neurips" and rec["extra"].get("hash"):
        return neurips_bib(net, rec)
    if rec["source"] in ("dblp", "s2", "openalex") and rec.get("doi") and not is_arxiv_doi(rec["doi"]):
        full = crossref_by_dois(net, [rec["doi"]]).get(rec["doi"])
        if full:
            return full
    if rec["source"] == "openreview" and rec["extra"].get("dblp"):
        if rec.get("doi"):
            full = crossref_by_dois(net, [rec["doi"]]).get(rec["doi"])
            if full:
                return full
        m = re.search(r"proceedings\.mlr\.press/v(\d+)/", rec.get("url") or "")
        if m:
            hits = [r for r in pmlr_volume(net, int(m.group(1))) if title_match(rec["title"], r["title"]) == "exact"]
            if hits:
                return hits[0]
        m = re.search(r"(?:papers|proceedings)\.n(?:eur)?ips\.cc/.*?/(\d{4})/hash/([0-9a-f]+)", rec.get("url") or "")
        if m:
            hits = [r for r in neurips_index(net, int(m.group(1))) if r["extra"]["hash"] == m.group(2)]
            if hits:
                return neurips_bib(net, hits[0])
    return rec


_RANK = {"published": 0, "workshop": 1, "preprint": 2, "other": 3}


def _status(rec: dict) -> str:
    if rec["source"] == "openreview":
        return rec["extra"]["status"]
    if rec["type"] == "preprint" or (rec["type"] in ("article", "inproceedings") and not rec.get("venue")):
        return "preprint"
    return "workshop" if "workshop" in venue_key(rec.get("venue") or "") else "published"


_KINDS = {
    "article": {"article", "inproceedings", "preprint"},
    "inproceedings": {"inproceedings", "article", "incollection", "preprint"},
    "incollection": {"incollection", "inproceedings", "book"},
    "book": {"book"},
}
"""Record kinds an entry of each type may be matched to. A journal article is
never its own reprint in an edited volume, and a book is never a review of it."""

_COMMENTARY = re.compile(
    r"^\s*(?:\[.+\]\s*:"
    r"|(?:comments?|discussion|reply|response|rejoinder)\s+(?:on|to|of)\b"
    r"|(?:erratum|errata|corrigendum|addendum)\b|(?:correction|retraction)(?:\s+(?:to|notice|note))?\s*:"
    r"|(?:book\s+)?review\s+of\b)"
    r"|:\s*(?:comments?|discussion|rejoinder|reply)\s*$",
    re.IGNORECASE,
)
"""Titles of a piece about a work rather than the work: a discussion ("[A Survey
of the Statistical Theory of Shape]: Comment", Crossref's form), reply, erratum,
retraction or review."""


def compatible(view: dict, cand: dict, linked: bool = False) -> bool:
    """Whether a matching record is the entry's own publication rather than a
    reprint, a later edition, or a review or discussion of the same work
    (`_COMMENTARY`): its kind must fit the entry's type, and a year more than
    one away is accepted only when the journal or proceedings agrees — the case
    of an entry with a wrong year — or an identifier in the entry links the two.
    For books it never is."""
    if linked:
        return True
    if _COMMENTARY.search(cand.get("title") or "") and not _COMMENTARY.search(view.get("title") or ""):
        return False
    et, ct = view.get("type"), cand.get("type")
    if et in _KINDS and ct not in _KINDS[et]:
        return False
    ey, cy = view.get("year"), cand.get("year")
    if not (ey and cy) or abs(ey - cy) <= 1:
        return True
    if et == "book" or ct == "book":
        return False  # another edition or a reprint (Springer's 1996 reissue of a 1969 book)
    ev, cv = venue_key(view.get("venue")), venue_key(cand.get("venue"))
    if not ev:
        return True

    def core(v: str) -> str:
        return " ".join(w for w in v.split() if w not in ("the", "proceedings", "of"))

    return bool(cv) and (core(ev) in core(cv) or core(cv) in core(ev))


def _best(view: dict, cands: list[dict], linked: bool = False) -> tuple[dict | None, str]:
    """The best matching candidate and its grade: strict before soft, then
    published before workshop before preprint, then nearest year. Reprints,
    later editions and reviews are filtered out first (`compatible`)."""
    scored = []
    for c in cands:
        if not compatible(view, c, linked=linked):
            continue
        g = same_work(view, c, linked=linked)
        if g != "no":
            dy = abs((view.get("year") or c.get("year") or 0) - (c.get("year") or view.get("year") or 0))
            scored.append((g != "exact", _RANK.get(_status(c), 2), dy, c, g))
    if not scored:
        return None, "no"
    scored.sort(key=lambda t: t[:3])
    return scored[0][3], scored[0][4]


def _extension_notice(view: dict, entry_type: str, cands: list[dict]) -> str | None:
    """A later journal version of a conference paper, reported but never swapped in."""
    if entry_type != "inproceedings":
        return None
    for c in cands:
        if c["type"] == "article" and same_work(view, c) != "no" and (c.get("year") or 0) >= (view.get("year") or 0):
            doi = f", doi:{c['doi']}" if c.get("doi") else ""
            return f"journal version exists: {c['venue']} {c.get('year')}{doi}"
    return None


def _arxiv_reference(net: Net, latest: dict, pinned: str | None) -> tuple[dict, int | None, str | None]:
    """The arXiv record an unpublished entry cites, its year, and a note when the
    version history could not be checked.

    A pinned version is cited exactly (its own metadata and date). Otherwise the
    latest version's metadata is used with the year of first submission — unless
    title or authors changed across versions (`version_year`). v1 is compared
    first; the other versions are fetched only when v1 differs."""
    if pinned:
        return latest, _year_of(latest["extra"]["updated"]) or latest["year"], None
    k, aid = latest["extra"]["version"], latest["arxiv"]
    if k <= 1:
        return latest, latest["year"], None
    v1 = arxiv_by_ids(net, [f"{aid}v1"]).get(f"{aid}v1")
    if v1 is None:
        return latest, latest["year"], "version history not checked (arXiv API unavailable): year of v1 used"
    if _same_version_meta(v1, latest):
        return latest, latest["year"], None
    older = {f"{aid}v1": v1, **arxiv_by_ids(net, [f"{aid}v{i}" for i in range(2, k)])}
    note = None if len(older) == k - 1 else "version history incomplete (arXiv API unavailable)"
    return latest, version_year(latest, older), note


def _same_version_meta(a: dict, b: dict) -> bool:
    """Same title and the same authors in the same order, whichever source
    spelled the names (DataCite "Liu, Ziyin" and arXiv "Liu Ziyin" agree)."""
    return (
        title_tokens(a["title"]) == title_tokens(b["title"])
        and len(a["authors"]) == len(b["authors"])
        and all(_same_person(x, y) for x, y in zip(a["authors"], b["authors"], strict=True))
    )


def version_year(latest: dict, older: dict[str, dict]) -> int | None:
    """The year an unpinned preprint is cited with: that of v1, unless title or
    authors changed across versions — then that of the earliest version from
    which they match the latest. `older` maps `<id>vN` to each earlier record; a
    gap in it stops the search, so the year errs late, never early."""
    k = latest["extra"]["version"]
    since = k
    for i in range(k - 1, 0, -1):
        r = older.get(f"{latest['arxiv']}v{i}")
        if not r or not _same_version_meta(r, latest):
            break
        since = i
    if since == 1:
        return latest["year"]
    stable = older.get(f"{latest['arxiv']}v{since}") or latest
    return _year_of(stable["extra"]["updated"]) or latest["year"]


def _renamed_candidates(net: Net, row: dict, year: int, view: dict) -> list[dict]:
    """Papers at a hinted venue-year whose authors match but whose title does not:
    arXiv comments such as "Appears in COLT 2019 with the title …" announce a
    renaming that no title search can confirm, so these go to review."""
    pool = venue_pool(net, row, year) if not (row.get("adapter") or "").startswith("openreview") else []
    ea = [a for a in view.get("authors") or [] if not a.get("others")]
    if not ea:
        return []
    return [
        r
        for r in pool
        if r["authors"]
        and _same_person(ea[0], r["authors"][0])
        and {surname(a) for a in ea} <= {surname(a) for a in r["authors"]} | {surname(ea[0])}
    ][:5]


def _find_published(
    net: Net, view: dict, arx: dict | None, venues: list[dict], crossref_hits: list[dict], s2: dict | None = None
) -> tuple[dict | None, str, list[dict]]:
    """Search for the version of record of a work known as a preprint: the DOI
    arXiv itself records, venue hints in its comment/journal-ref, Crossref, the
    NeurIPS/ICML/ICLR indices of the submission year and the next, Semantic
    Scholar's record of the preprint, DBLP, then OpenReview (including its DBLP
    mirror). Returns (record, grade, near-misses)."""
    tried: list[dict] = []
    if arx and arx.get("doi"):
        rec = crossref_by_dois(net, [arx["doi"]]).get(arx["doi"])
        if rec:
            tried.append(rec)
            if same_work(view, rec, linked=True) != "no":
                return rec, same_work(view, rec, linked=True), tried
    hints = (
        _hint_venues(arx["extra"].get("comment"), venues) + _hint_venues(arx["extra"].get("journal_ref"), venues)
        if arx
        else []
    )
    for row, year in hints:
        cands = _venue_candidates(net, row, year, view["title"])
        tried += cands
        rec, g = _best(view, cands)
        if rec:
            return _complete(net, rec), g, tried
        renamed = _renamed_candidates(net, row, year, view)
        if renamed:
            return None, "renamed", renamed
        if arx and not venue_pool(net, row, year, view["title"]):
            # No index covers that venue-year (ICLR before 2020, say): the authors'
            # own statement on arXiv is the best evidence there is. Soft, so listed.
            hinted = _rec(
                "arxiv-comment",
                arx["arxiv"],
                type=row["type"],
                title=arx["title"],
                authors=arx["authors"],
                year=year,
                venue=_venue_name(row, year),
                extra={"comment": arx["extra"].get("comment")},
            )
            return hinted, "soft", tried
    pubs = [c for c in crossref_hits if c["type"] != "preprint"]
    rec, g = _best(view, pubs)
    if rec and _status(rec) == "published":
        return rec, g, tried
    year = (arx or {}).get("year") or view.get("year")
    if year and (not arx or str(arx["extra"].get("category") or "").startswith(_ML_CATEGORIES)):
        rows = [r for r in venues if r["acronym"] in ("NeurIPS", "ICML", "ICLR")]
        for row in rows:
            for y in (year, year + 1):
                cands = _venue_candidates(net, row, y, view["title"])
                rec, g = _best(view, cands)
                if rec:
                    return _complete(net, rec), g, tried
    # Semantic Scholar's record of the same preprint names its published version.
    if s2 and s2.get("type") != "preprint":
        tried.append(s2)
        if s2.get("doi") and not is_arxiv_doi(s2["doi"]):
            rec = crossref_by_dois(net, [s2["doi"]]).get(s2["doi"])
            if rec and same_work(view, rec, linked=True) != "no":
                return rec, same_work(view, rec, linked=True), tried
        row = canonical_venue(s2.get("venue"), venues)
        if row and s2.get("year"):
            rec, g = _best(view, _venue_candidates(net, row, s2["year"], view["title"]))
            if rec:
                return _complete(net, rec), g, tried
            if not venue_pool(net, row, s2["year"], view["title"]) and same_work(view, s2) != "no":
                return s2, "soft", tried  # no index for that venue-year: Semantic Scholar's word
    # DBLP (through SPARQL): its record of the published version.
    dblp = [r for r in dblp_search(net, view["title"]) if r["type"] != "preprint"]
    tried += dblp
    rec, g = _best(view, dblp)
    if rec and _status(rec) == "published":
        return _complete(net, rec), g, tried
    # OpenReview last: it is the only source for ICLR and TMLR, and the scarcest.
    ors = [r for r in openreview_search(net, view["title"], year) if r["extra"]["status"] in ("published", "workshop")]
    tried += ors
    rec, g = _best(view, ors)
    if rec and _status(rec) == "published":
        return _complete(net, rec), g, tried
    return (rec, g, tried) if rec else (None, "no", tried)


def _near(view: dict, cands: list[dict], n: int = 3) -> list[dict]:
    """Near misses worth showing a reviewer: candidates whose title is at least
    half-similar to the entry's, most similar first."""
    import difflib

    a = " ".join(title_tokens(view.get("title")))
    scored = [
        (difflib.SequenceMatcher(None, a, " ".join(title_tokens(c.get("title")))).ratio(), i, c)
        for i, c in enumerate(cands)
    ]
    return [c for r, _, c in sorted(scored, key=lambda t: (-t[0], t[1])) if r >= 0.5][:n]


def _published_of(net: Net, view: dict, rec: dict) -> dict | None:
    """The published version a Crossref preprint record links (`is-preprint-of`),
    when it is the same work."""
    rel = [
        r.get("id", "").lower()
        for r in (rec["extra"].get("relation") or {}).get("is-preprint-of", [])
        if r.get("id-type") == "doi"
    ]
    pub = crossref_by_dois(net, rel[:1]).get(rel[0]) if rel else None
    return pub if pub and same_work(view, pub, linked=True) != "no" else None


_PREPRINT_SERVER = re.compile(r"rxiv|preprint|ssrn|research ?square|techrxiv|osf\b|zenodo", re.IGNORECASE)


def _preprint_entry(view: dict, rec: dict) -> bool:
    """The entry itself cites a preprint (it names a preprint server, the record's
    own server, or no venue at all)."""
    v = view.get("venue") or ""
    return not v or bool(_PREPRINT_SERVER.search(v)) or _venues_agree(v, rec.get("venue"))


def _first_page(pages: str | None) -> str:
    return re.split(r"\s*(?:--|–|-)\s*", (pages or "").strip())[0].lower()


def _slot_holder(net: Net, view: dict, entry: dict, venues: list[dict]) -> dict | None:
    """The work that really occupies the slot an entry claims (venue, volume,
    first page or paper number), when that is a different work — the signature
    of fabricated metadata: a real title stitched onto someone else's volume and
    pages. A slot can be checked wherever a source lists what sits at a volume
    and page: JMLR's and PMLR's volume indices, and OpenAlex and Crossref for
    journals. NeurIPS's year indices carry no pages and ICLR/TMLR have none, so
    those venues' slots cannot be checked."""
    f = entry["fields"]
    vol, page, num = (f.get("volume") or "").strip(), _first_page(f.get("pages")), (f.get("number") or "").strip()
    if not (view["venue"] and vol and page):
        return None
    row = canonical_venue(view["venue"], venues)
    adapter = (row or {}).get("adapter") or ""
    if adapter == "jmlr":
        pool = jmlr_volume(net, int(vol)) if vol.isdigit() else []
    elif adapter.startswith("pmlr:"):
        # only a volume that really is this venue-year's PMLR volume (a "40" meant as
        # an edition number would otherwise point into another conference)
        acronym, year = adapter.split(":", 1)[1].upper(), view.get("year") or 0
        own = {pmlr_volumes(net).get((acronym, y)) for y in (year - 1, year, year + 1)}
        pool = pmlr_volume(net, int(vol)) if vol.isdigit() and int(vol) in own else []
    elif adapter:
        return None
    else:
        # OpenAlex answers "what is at volume V, first page P" for any journal it
        # indexes; Crossref's citation search covers the rest of the DOI world.
        year = view.get("year")
        pool = [
            r
            for r in openalex_slot(net, vol, page, year)
            if venue_key(r.get("venue")) and _venues_agree(view["venue"], r["venue"])
        ] or crossref_search(net, f"{view['venue']} {vol} {page} {year or ''}", None, rows=5)
    for r in pool:
        same_slot = (r.get("volume") or "").strip() == vol and (
            _first_page(r.get("pages")) == page or (num and (r.get("number") or "") == num and r["source"] == "jmlr")
        )
        if same_slot and title_match(view["title"], r["title"]) == "none":
            return r
    return None


def _venues_agree(a: str | None, b: str | None) -> bool:
    """Two spellings of one journal: the same words once folded (articles and
    prepositions aside), or one an abbreviation of the other word by word ("Phys.
    Rev. E" / "Physical Review E", "J. Mach. Learn. Res.", contractions such as
    "Natl."), or one the acronym of the other ("PNAS"), comparing the parts
    before a colon too ("Physical Review E: Statistical, Nonlinear, and Soft
    Matter Physics"). "Nature" and "Nature Physics" do not agree, nor does a
    renamed journal with its successor ("… Biophysics" / "… Biology")."""

    def words(v: str | None) -> list[str]:
        return [w for w in venue_key(v).split() if w not in ("the", "of", "and", "for", "in", "on", "a")]

    def abbrev(p: str, q: str) -> bool:
        short, long = sorted((p, q), key=len)
        if long.startswith(short):
            return True
        it = iter(long)
        return len(short) <= 5 and short[:1] == long[:1] and all(c in it for c in short)

    def same(x: list[str], y: list[str]) -> bool:
        if len(x) == 1 < len(y) or len(y) == 1 < len(x):
            one, many = (x, y) if len(x) == 1 else (y, x)
            return len(one[0]) > 1 and one[0] == "".join(w[0] for w in many)
        return bool(x) and len(x) == len(y) and all(abbrev(p, q) for p, q in zip(x, y, strict=True))

    heads = [(v or "").split(":", 1)[0] for v in (a, b)]
    return same(words(a), words(b)) or same(words(heads[0]), words(heads[1]))


def _claims_publication(entry: dict, view: dict) -> bool:
    """The entry names a journal, proceedings or publisher (not arXiv/CoRR)."""
    if entry["type"] not in ("article", "inproceedings", "incollection", "book"):
        return False
    where = view["venue"] or view.get("publisher") or ""
    return bool(where) and not re.search(r"arxiv|corr\b|preprint", where, re.IGNORECASE)


def _mangled_authors(view: dict) -> bool:
    """Four or more "authors" that are each a single braced word: a name list
    split at every comma (`{Garnier} and {Simon} and {Ross} …`)."""
    names = [a for a in view["authors"] if not a.get("others")]
    return len(names) >= 4 and all(
        not a.get("first") and re.fullmatch(r"\{[^{}\s]+\}", a.get("last", "")) for a in names
    )


def _lookup_entry(net: Net, entry: dict, venues: list[dict], pre: dict, seen: list[dict]) -> dict:
    """The body of `lookup_entry`; every record it fetches is appended to `seen`."""
    ids = identifiers(entry)
    view = entry_view(entry)
    res: dict = {
        "status": None,
        "grade": None,
        "record": None,
        "reference_year": None,
        "notices": [],
        "problem": None,
        "candidates": [],
        "ids": ids,
    }
    etype = entry["type"]
    if _mangled_authors(view):
        res["notices"].append("author list looks mangled (one braced word per name)")

    # A DOI must lead to this very paper; otherwise it is a wrong or fabricated link.
    if ids.get("doi"):
        rec = pre["crossref"].get(ids["doi"])
        if rec:
            seen.append(rec)
            g = same_work(view, rec, linked=True)
            if g != "no" and rec["type"] == "preprint":
                pub = _published_of(net, view, rec)
                if pub:
                    res.update(status="upgraded", grade=same_work(view, pub, linked=True), record=pub)
                else:
                    res.update(status="verified", grade=g, record=rec)
            elif g != "no":
                res.update(status="verified", grade=g, record=rec)
            else:
                res["notices"].append(
                    f"DOI {ids['doi']} belongs to another work: “{rec['title']}” ({rec.get('venue')}, {rec.get('year')})"
                )
                res["identity_failed"] = True
        else:
            res["notices"].append(f"DOI {ids['doi']} does not resolve in Crossref")

    arx = None
    if ids.get("arxiv") and not res["record"]:
        arx = pre["arxiv"].get(ids["arxiv"] + (ids.get("arxiv_version") or "")) or pre["arxiv"].get(ids["arxiv"])
        if arx:
            seen.append(arx)
            if same_work(view, arx, linked=True) == "no":
                res["notices"].append(f"arXiv:{ids['arxiv']} is another work: “{arx['title']}”")
                res["identity_failed"] = True
                arx = None
        else:
            res["notices"].append(f"arXiv:{ids['arxiv']} not found")

    # No title: a sparse entry (e.g. "Ising 1925") — recover only a unique candidate.
    if not view["title"]:
        first = next((a for a in view["authors"] if not a.get("others")), None)
        hits = (
            crossref_search(net, None, detex(first.get("last", "")) if first else None, view["year"], rows=5)
            if first and view["year"]
            else []
        )
        hits = [
            h for h in hits if author_match(view["authors"], h["authors"]) == "ok" and h.get("year") == view["year"]
        ]
        if len(hits) == 1:
            res.update(status="recovered", grade="soft", record=hits[0])
        else:
            res.update(
                status="queued",
                problem="no title; " + (f"{len(hits)} candidates" if hits else "no candidate"),
                candidates=hits[:5],
            )
        return res

    # Venue indices for entries that cite NeurIPS / PMLR / JMLR / OpenReview venues.
    if not res["record"]:
        row = canonical_venue(view["venue"], venues)
        if row and view["year"] and row.get("adapter"):
            for y in (view["year"], view["year"] - 1, view["year"] + 1):
                cands = _venue_candidates(net, row, y, view["title"])
                seen.extend(cands)
                rec, g = _best(view, cands)
                if rec:
                    res.update(status="verified", grade=g, record=_complete(net, rec))
                    break

    unindexed = etype in _UNINDEXED_TYPES or is_web(entry)
    hits: list[dict] = []
    if not res["record"] and not arx and not unindexed:
        first = next((a for a in view["authors"] if not a.get("others")), None)
        hits = crossref_search(
            net,
            view["title"],
            detex(first.get("last", "")) if first else None,
            rows=8,
            context=f"{view['venue']} {view['year'] or ''}",
        )
        seen.extend(hits)
        rec, g = _best(view, hits)
        if not rec:  # the citation string can bury the obvious: ask for the title alone
            plain = crossref_search(net, view["title"], None, rows=8)
            seen.extend(plain)
            hits = hits + plain
            rec, g = _best(view, hits)
        if not rec and etype == "article":
            f = entry["fields"]
            vol, page = (f.get("volume") or "").strip(), _first_page(f.get("pages"))
            if view["venue"] and vol and page:  # OpenAlex's occupant of the claimed slot
                slot = [
                    r
                    for r in openalex_slot(net, vol, page, view["year"])
                    if _venues_agree(view["venue"], r.get("venue"))
                ]
                seen.extend(slot)
                rec, g = _best(view, slot)
                rec = _complete(net, rec) if rec else None
        if rec and rec["type"] == "preprint":
            pub = _published_of(net, view, rec)
            if pub:
                res.update(status="upgraded", grade=same_work(view, pub, linked=True), record=pub)
            elif _preprint_entry(view, rec):
                res.update(status="verified", grade=g, record=rec)
        elif rec and (_status(rec) == "published" or etype in ("book", "incollection")):
            res.update(status="verified", grade=g, record=rec)
        if not res["record"] and etype not in ("book", "incollection"):
            more = dblp_search(net, view["title"]) + s2_match(net, view["title"])
            seen.extend(more)
            mrec, mg = _best(view, [r for r in more if r["type"] != "preprint"])
            if mrec and _status(mrec) == "published":
                res.update(status="verified", grade=mg, record=_complete(net, mrec))
        journal_elsewhere = etype == "article" and view["venue"] and canonical_venue(view["venue"], venues) is None
        if not res["record"] and etype not in ("book", "incollection") and not journal_elsewhere:
            # (journals outside the ML venue table are Crossref's domain, not OpenReview's)
            ors = openreview_search(net, view["title"], view["year"])
            seen.extend(ors)
            orec, og = _best(view, [r for r in ors if r["extra"]["status"] in ("published", "workshop")])
            if orec:
                res.update(status="verified", grade=og, record=_complete(net, orec))
            else:
                prep = [r for r in ors if r["extra"]["status"] == "preprint"]
                prec, _ = _best(view, prep)
                if prec and not arx:
                    # OpenReview's DBLP mirror knows it only as CoRR: find the arXiv record.
                    m = re.search(rf"arxiv\.org/abs/({_ARXIV_ID})", prec.get("url") or "")
                    if m:
                        arx = arxiv_by_ids(net, [m.group(1)]).get(m.group(1))
                        ids["arxiv"] = m.group(1)

    # arXiv by title: the fix for an eprint that names another paper, and the
    # last source to try before an entry goes to review.
    if not res["record"] and not arx and not unindexed:
        first = next((a for a in view["authors"] if not a.get("others")), None)
        rec, _ = _best(view, arxiv_search(net, view["title"], detex(first.get("last", "")) if first else None))
        if rec:
            if ids.get("arxiv") and ids["arxiv"] != rec["arxiv"]:
                res["notices"].append(f"arXiv id corrected: {ids['arxiv']} → {rec['arxiv']}")
            ids["arxiv"] = rec["arxiv"]
            ids.pop("arxiv_version", None)
            arx = rec

    # A preprint: look for its published version, else cite the arXiv record per the version rule.
    if arx and not res["record"]:
        if not hits:
            first = next((a for a in view["authors"] if not a.get("others")), None)
            hits = crossref_search(net, arx["title"], detex(first.get("last", "")) if first else None)
            seen.extend(hits)
        renamed = not view["title"] or title_match(view["title"], arx["title"]) == "none"
        pview = {**view, "title": arx["title"] if renamed else view["title"], "year": arx["year"]}
        s2 = pre.get("s2", {}).get(f"ARXIV:{arx['arxiv']}")
        pub, g, tried = _find_published(net, pview, arx, venues, hits, s2)
        seen.extend(tried + ([pub] if pub else []))
        if g == "renamed":
            res.update(
                status="queued",
                problem=f"arXiv says it appeared elsewhere under another title (comment: {arx['extra'].get('comment')!r})",
                candidates=tried,
            )
            return res
        if pub and _status(pub) == "published":
            res.update(status="upgraded", grade=g, record=pub)
        elif _claims_publication(entry, view):
            holder = _slot_holder(net, view, entry, venues)
            if holder:
                res.update(
                    status="queued",
                    problem=f"the claimed slot ({view['venue']} {entry['fields'].get('volume')}:{entry['fields'].get('pages')}) belongs to another work",
                    candidates=[holder, arx],
                )
                return res
            res.update(status="unconfirmed")
            res["notices"].append(
                f"venue not confirmed by any index ({view['venue']}); the work exists as arXiv:{arx['arxiv']}"
            )
            return res
        else:
            ref, year, vnote = _arxiv_reference(net, arx, ids.get("arxiv_version"))
            if vnote:
                res["notices"].append(vnote)
            res.update(status="preprint", grade=same_work(view, ref, linked=True), record=ref, reference_year=year)
            if pub:
                res["notices"].append(f"workshop version: {pub.get('venue')} {pub.get('year')}")

    if res["record"] is None:
        holder = _slot_holder(net, view, entry, venues) if etype in ("article", "inproceedings") else None
        others = [c for c in hits if same_work(view, c) != "no" and not compatible(view, c)]
        if holder:
            res.update(
                status="queued",
                problem=f"the claimed slot ({view['venue']} {entry['fields'].get('volume')}:{entry['fields'].get('pages')}) belongs to another work",
                candidates=[holder],
            )
        elif others:
            o = others[0]
            res.update(status="unconfirmed")
            res["notices"].append(
                f"indexed only as another publication of the same work ({o['type']}, {o.get('venue') or o.get('publisher')}, {o.get('year')}); entry kept"
            )
        elif (unindexed or etype in ("book", "inbook", "incollection")) and not _mangled_authors(view):
            res.update(status="unverifiable")  # most books, theses and web pages are in no index
        else:
            near = _near(view, hits)
            res.update(
                status="queued", problem="; ".join(res["notices"]) or "no source knows this entry", candidates=near
            )
        return res

    if res.get("identity_failed") and res["status"] != "queued":
        res["notices"].insert(0, "identity corrected: the entry's identifier pointed at another work")
    if res["record"]["type"] != "preprint":
        if not hits and etype == "inproceedings":
            first = next((a for a in view["authors"] if not a.get("others")), None)
            hits = crossref_search(
                net,
                view["title"],
                detex(first.get("last", "")) if first else None,
                rows=8,
                context=f"{view['venue']} {view['year'] or ''}",
            )
            seen.extend(hits)
        note = _extension_notice(view, etype if res["status"] == "verified" else res["record"]["type"], hits)
        if note:
            res["notices"].append(note)
    return res


def lookup_entry(net: Net, entry: dict, venues: list[dict], pre: dict) -> dict:
    """Settle one entry against the sources. `pre` carries the batched lookups
    (`crossref`, `arxiv`). Returns a result: {"status", "grade", "record",
    "reference_year", "notices", "problem", "candidates", "ids", "evidence"} —
    `evidence` being every record met that names the same work, whatever its
    source, for `fullest_names`."""
    seen: list[dict] = []
    res = _lookup_entry(net, entry, venues, pre, seen)
    view, rec = entry_view(entry), res.get("record")
    unique = {(r["source"], r["id"]): r for r in [*seen, *([rec] if rec else [])] if r and r.get("authors")}
    res["evidence"] = [r for r in unique.values() if r is rec or (compatible(view, r) and same_work(view, r) != "no")]
    return res


# ── Applying a record ────────────────────────────────────────────────────────

_CONTAINER = (
    "journal",
    "booktitle",
    "volume",
    "number",
    "issue",
    "pages",
    "publisher",
    "series",
    "organization",
    "address",
    "edition",
    "chapter",
    "school",
    "institution",
    "howpublished",
    "eprint",
    "archiveprefix",
    "primaryclass",
    "eprinttype",
    "eprintclass",
    "journaltitle",
)
_CAPS_NAMES = {
    n.lower(): n
    for n in (
        "IEEE",
        "ACM",
        "PMLR",
        "SIAM",
        "APS",
        "AIP",
        "IOP",
        "JSTOR",
        "CEUR-WS",
        "USA",
        "UK",
        "MIT Press",
        "PLOS One",
        "IEEE Access",
        "AAAI Press",
        "OpenReview.net",
    )
}


def _norm_value(v: str) -> str:
    return " ".join(detex(v or "").split())


def _venue_name(row: dict, year: int | None) -> str:
    """A table row's canonical name, honouring year-dependent variants
    (`A|<2018:B` means B before 2018: CVPR became "IEEE/CVF" in 2018)."""
    name, *variants = row["canonical"].split("|")
    for v in variants:
        m = re.match(r"<(\d{4}):(.*)", v)
        if m and year and year < int(m.group(1)):
            return m.group(2)
    return name


def _pages(p: str | None) -> str | None:
    if not p:
        return p
    p = re.sub(r"\s*(?:--|–|—|-)\s*", "--", p.strip())
    return p


def protect_title(title: str) -> str:
    """Brace the words a BibTeX style's lowercasing would damage — acronyms and
    words with capitals after their first letter ("LLMs", "ImageNet", "GPT",
    "3D", "U-Net") — outside math, existing braces and commands. Ordinarily capitalised
    words are left to the style."""
    out, i = [], 0
    for m in re.finditer(r"\{(?:[^{}]|\{[^{}]*\})*\}|\$[^$]*\$|\\[A-Za-z]+", title):
        out.append(_brace_words(title[i : m.start()]))
        out.append(m.group(0))
        i = m.end()
    out.append(_brace_words(title[i:]))
    return "".join(out)


def _brace_words(text: str) -> str:
    def fix(m: re.Match) -> str:
        w = m.group(0)
        return (
            "{" + w + "}"
            if re.search(r"[A-Z]", w[1:]) or (len(w) > 1 and w.isupper()) or re.search(r"\d[A-Z]|[A-Z]\d", w)
            else w
        )

    return re.sub(r"[A-Za-z0-9]*[A-Z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*", fix, text)


def _source_title_wins(entry_title: str | None, rec_title: str | None) -> bool:
    """Whether a matched record's title should replace the entry's: not when they
    already agree, nor when the source dropped the entry's LaTeX math (Crossref
    flattens `$\\ell_p$` to "l p") or renders the title in ALL CAPS."""
    if not rec_title or title_match(entry_title, rec_title) == "exact":
        return False
    if entry_title and "$" in entry_title and "$" not in rec_title:
        return False
    letters = re.sub(r"[^A-Za-z]", "", rec_title)
    return not (len(letters) > 8 and letters.isupper())


def apply_record(entry: dict, res: dict, venues: list[dict]) -> tuple[dict, list[dict]]:
    """The entry corrected from its matched record, and the field-level changes.

    Values the source confirms are left in the entry's own spelling (so brace
    protection and LaTeX survive); values the source contradicts are replaced;
    container fields a changed entry type no longer supports are dropped."""
    rec = res["record"]
    src = f"{rec['source']}:{rec['id']}"
    f = dict(entry["fields"])
    changes: list[dict] = []

    def put(name: str, value: str | None) -> None:
        old = f.get(name)
        if value in (None, ""):
            if old is not None:
                changes.append({"field": name, "old": old, "new": None, "source": src})
                del f[name]
            return
        if old is None or _norm_value(old) != _norm_value(value):
            changes.append({"field": name, "old": old, "new": value, "source": src})
            f[name] = value

    if rec["type"] == "preprint" and not rec.get("arxiv"):
        # a preprint on another server (bioRxiv, SSRN, …): its metadata, the entry's own form
        new_type = entry["type"]
        year = res.get("reference_year") or rec["year"]
        if _source_title_wins(f.get("title"), rec["title"]):
            put("title", protect_title(rec["title"]))
    elif rec["type"] == "preprint":
        new_type = "misc"
        for k in _CONTAINER:
            if k in f and k not in ("eprint", "archiveprefix", "primaryclass"):
                put(k, None)
        for k in ("note", "url"):
            if k in f and re.search(r"arxiv", f[k], re.IGNORECASE):
                put(k, None)
        if _source_title_wins(f.get("title"), rec["title"]):
            put("title", protect_title(rec["title"]))
        put("eprint", rec["arxiv"] + (res["ids"].get("arxiv_version") or ""))
        put("archiveprefix", "arXiv")
        put("primaryclass", rec["extra"].get("category"))
        year = res.get("reference_year") or rec["year"]
    else:
        year = rec["year"]
        ey = _year_of(f.get("year", ""))
        if ey and ey in rec["extra"].get("years", ()):
            year = ey  # the entry's year is one of the work's own dates (online-first, print, event)
        if ey and "book" in (entry["type"], rec["type"]):
            year = ey  # a book's year is its edition's: a record a year away confirms, never re-dates
        if (
            rec["source"] == "crossref"
            and rec["type"] == "inproceedings"
            and not rec["extra"].get("year_from_event")
            and ey
            and year == ey + 1
        ):
            year = ey  # Crossref dated the proceedings volume, not the conference
        names = [rec.get("venue"), *rec["extra"].get("containers", []), rec["extra"].get("event")]
        row = next((r for v in names if v and (r := canonical_venue(v, venues))), None) or (
            canonical_venue(entry_view(entry)["venue"], venues)
            if rec["source"]
            in ("neurips", "pmlr", "jmlr", "openreview", "iclr-site", "neurips-site", "icml-site", "arxiv-comment")
            else None
        )
        new_type = (row or {}).get("type") or (
            rec["type"]
            if rec["type"] in ("article", "inproceedings", "book", "incollection", "phdthesis", "techreport")
            else entry["type"]
        )
        if row:
            venue = _venue_name(row, year)
        elif rec["source"] == "dblp" and new_type == entry["type"] and (f.get("journal") or f.get("booktitle")):
            venue = f.get("journal") or f.get("booktitle")  # DBLP names venues by abbreviation ("Neural Comput.")
        elif new_type == "inproceedings":
            venue = clean_venue_name(rec.get("venue") or f.get("booktitle", ""))
        else:
            venue = rec.get("venue") or f.get("journal") or f.get("booktitle")
        if _source_title_wins(f.get("title"), rec["title"]):
            put("title", protect_title(rec["title"]))
        if new_type != entry["type"] or res["status"] == "upgraded":
            for k in _CONTAINER:
                if k in f and not rec.get(k if k != "issue" else "number"):
                    put(k, None)
            for k in ("note", "url"):
                if k in f and re.search(r"arxiv", f[k], re.IGNORECASE):
                    put(k, None)
        if new_type == "article":
            put("journal", venue)
            put("booktitle", None)
            put("publisher", None)
        elif new_type in ("inproceedings", "incollection"):
            put("booktitle", venue)
            put("journal", None)
            put("organization", None)
        # Proceedings are identified by series name and year (no edition, volume or
        # issue numbers are added); journals and books keep theirs.
        if rec.get("volume") and new_type != "inproceedings":
            put("volume", rec["volume"])
        if rec.get("number") and new_type != "inproceedings":
            put("number", rec["number"])
        rp = _pages(rec.get("pages"))
        own = (f.get("pages") or "").strip()
        if own and "--" not in own and rp and rp.startswith("1--"):
            rp = None  # the entry's article number, not the article's internal page range
        if rp and not ("--" not in rp and (_pages(f.get("pages", "")) or "").startswith(rp + "--")):
            put("pages", rp)
        if rec.get("series") and rec.get("volume") and new_type != "inproceedings":
            put("series", rec["series"])
        if new_type in ("book", "incollection") and rec.get("publisher") and not f.get("publisher"):
            put("publisher", rec["publisher"])
    entry_authors = split_authors(f["author"]) if f.get("author") else []
    broken = (
        not entry_authors
        or any(a.get("others") for a in entry_authors)
        or len(entry_authors) != len(rec.get("authors") or [])
    )
    if (
        rec.get("authors")
        and (rec["source"] in BYLINE_SOURCES or broken)
        and not (rec["source"].endswith("-site") and f.get("author"))
    ):
        # A byline source corrects names; a registry or profile source (DBLP, Semantic
        # Scholar, OpenReview) only repairs a missing or truncated list. Conference-site
        # lists do not keep the paper's author order: they confirm, never rewrite.
        merged = merge_authors(entry_authors, rec["authors"])
        text = authors_field(merged)
        if not f.get("author") or not _same_authors_text(f["author"], text):
            put("author", text)
    if year:
        put("year", str(year))
    if new_type != entry["type"]:
        changes.insert(0, {"field": "@type", "old": entry["type"], "new": new_type, "source": src})
    return {**entry, "type": new_type, "fields": f}, changes


_CODE_HOST = re.compile(
    r"^\s*(?:github|gitlab|bitbucket|zenodo|cran|pypi|software heritage|hugging ?face)(?:\s+(?:repository|repo|hub))?\s*$",
    re.IGNORECASE,
)


def normalise_entry(entry: dict) -> tuple[dict, list[dict]]:
    """Source-independent hygiene: portable entry types, arXiv-as-journal to
    @misc eprint, page ranges, restored all-caps names, web URLs out of \\url{}."""
    t, f = entry["type"], dict(entry["fields"])
    changes: list[dict] = []

    def note(field: str, old, new) -> None:
        changes.append({"field": field, "old": old, "new": new, "source": "normalise"})

    for k in ("journal", "publisher"):
        if (
            (t in ("misc", "article") or t in _WEB_TYPES)
            and _CODE_HOST.search(detex(f.get(k, "")))
            and (f.get("url") or f.get("howpublished"))
        ):
            note(k, f.pop(k), None)  # "GitHub repository" is where software lives, not a venue
    if t in _WEB_TYPES or (t == "article" and not f.get("journal") and (f.get("url") or f.get("howpublished"))):
        note("@type", t, "misc")
        t = "misc"
    elif t == "workshop":
        note("@type", t, "inproceedings")
        t = "inproceedings"
    bare = list(entry.get("bare", ()))
    mo = re.match(r"\s*([A-Za-z]{3})[a-z]*\.?\s*$", detex(f.get("month", "")))
    if mo and mo.group(1).lower() in _MONTHS and (f["month"] != mo.group(1).lower() or "month" not in bare):
        note("month", f["month"], mo.group(1).lower())
        f["month"] = mo.group(1).lower()
        bare = [*bare, "month"]
    m = re.match(
        r"\s*arXiv\s+preprint\s+(?:arXiv:)?\s*(" + _ARXIV_ID + r"(?:v\d+)?)", detex(f.get("journal", "")), re.IGNORECASE
    )
    if m:
        note("journal", f.pop("journal"), None)
        f.setdefault("eprint", m.group(1))
        f.setdefault("archiveprefix", "arXiv")
        if t != "misc":
            note("@type", t, "misc")
            t = "misc"
    if "eprint" in f and re.fullmatch(r"\s*arXiv:\s*\S+\s*", detex(f.get("howpublished", ""))):
        note("howpublished", f.pop("howpublished"), None)
    for k in ("article-number", "articleno", "eid"):
        if k in f and "pages" not in f:
            f["pages"] = f.pop(k)
            note("pages", None, f["pages"])
    if "pages" in f and _pages(f["pages"]) != f["pages"]:
        note("pages", f["pages"], _pages(f["pages"]))
        f["pages"] = _pages(f["pages"])
    for k in ("publisher", "organization", "journal", "address", "institution"):
        v = f.get(k)
        if v and _CAPS_NAMES.get(detex(v).lower()) and detex(v) != _CAPS_NAMES[detex(v).lower()]:
            note(k, v, _CAPS_NAMES[detex(v).lower()])
            f[k] = _CAPS_NAMES[detex(v).lower()]
    hp = f.get("howpublished", "")
    mu = re.fullmatch(r"\s*\\url\{([^}]*)\}\s*", hp)
    # bibtex-tidy escapes _ % # & $ even inside \url{}, breaking the link; only
    # such URLs move to `url` (which it leaves alone) — `plain.bst` prints
    # howpublished but not url, so the rest stay where they render everywhere.
    if mu and "url" not in f and re.search(r"[_%#&$]", mu.group(1)):
        note("howpublished", hp, None)
        f.pop("howpublished")
        f["url"] = mu.group(1)
        note("url", None, f["url"])
    nt = re.fullmatch(r"\s*(?:\\url\{([^}]*)\}|(https?://\S+))\s*", f.get("note", ""))
    publication = any(k in f for k in ("journal", "booktitle", "eprint", "school", "institution", "publisher"))
    if (
        nt
        and t == "misc"
        and "url" not in f
        and not publication
        and not re.search(r"\\url\{", f.get("howpublished", ""))
    ):
        # a web page whose only locator sits in `note`: make it the URL it is
        note("note", f.pop("note"), None)
        f["url"] = nt.group(1) or nt.group(2)
        note("url", None, f["url"])
    return {**entry, "type": t, "fields": f, "bare": sorted(set(bare))}, changes


# ── Stripping ────────────────────────────────────────────────────────────────

_JUNK = frozenset({
    "abstract",
    "keywords",
    "doi",
    "file",
    "timestamp",
    "biburl",
    "bibsource",
    "mendeley-tags",
    "mendeley-groups",
    "annote",
    "annotation",
    "owner",
    "creationdate",
    "modificationdate",
    "groups",
    "issn",
    "copyright",
    "pdf",
    "citeulike-article-id",
    "citeulike-linkout-0",
    "citeulike-linkout-1",
    "added-at",
    "interhash",
    "intrahash",
    "shorttitle",
    "numpages",
    "issue_date",
    "acmid",
    "collection",
    "place",
    "ee",
    "local-url",
    "priority",
    "ranking",
    "readstatus",
    "qualityassured",
})


def strip_entry(entry: dict) -> tuple[dict, list[dict]]:
    """Drop what is not part of a citation: abstracts, keywords, DOIs, tool
    bookkeeping, and URLs — except for a website, repository or piece of
    software, where the URL is the thing cited. A note that only repeats an
    identifier goes too; `publisher` on @article (ignored by standard styles and
    invalid in biblatex's data model) goes as well."""
    web = is_web(entry)
    f = {}
    removed = []
    for k, v in entry["fields"].items():
        drop = k in _JUNK
        drop |= k in ("url", "urldate") and not web
        drop |= k == "note" and bool(
            re.fullmatch(r"\s*(?:\\url\{[^}]*\}|https?://\S+|(?:arXiv|doi):\s*\S+|10\.\d{4,9}/\S+)\s*", detex(v) or v)
        )
        drop |= k == "publisher" and entry["type"] == "article"
        drop |= not (v or "").strip()
        if drop:
            removed.append({"field": k, "old": v, "new": None, "source": "strip"})
        else:
            f[k] = v
    return {**entry, "fields": f}, removed


# ── Citation keys: <Surname><Year><FirstContentWord>, PascalCase, ASCII ─────

_KEY_STOP = _STOP | frozenset([
    "but",
    "nor",
    "so",
    "yet",
    "above",
    "below",
    "among",
    "across",
    "during",
    "before",
    "after",
    "against",
    "was",
    "were",
    "been",
    "being",
    "did",
    "could",
    "will",
    "would",
    "shall",
    "should",
    "may",
    "might",
    "must",
    "has",
    "have",
    "had",
    "we",
    "our",
    "you",
    "your",
    "they",
    "their",
    "he",
    "she",
    "his",
    "her",
    "not",
    "no",
    "all",
    "any",
    "some",
    "each",
    "every",
    "more",
    "most",
    "less",
    "least",
    "much",
    "many",
    "very",
    "than",
    "then",
    "if",
    "when",
    "where",
    "how",
    "what",
    "why",
    "which",
    "who",
    "whom",
    "whose",
    "there",
    "here",
    "proceedings",
    "volume",
    "part",
    "chapter",
    "nach",
    "unter",
    "zwischen",
])
_CORP_NOISE = frozenset({
    "maintainers",
    "contributors",
    "team",
    "group",
    "project",
    "developers",
    "authors",
    "consortium",
    "collaboration",
})


def _pascal(word: str) -> str:
    return "".join(p[:1].upper() + p[1:] for p in word.split("-") if p)


def _key_surname(entry: dict) -> str | None:
    f = entry["fields"]
    names = [n for n in split_authors(f.get("author") or f.get("editor") or "") if not n.get("others")]
    if not names:
        return None
    n = names[0]
    if not n.get("first") and n.get("last", "").startswith("{"):
        corp = re.split(r"\s+and\s+|\s*,\s*", fold(detex(n["last"])))[0]
        words = [w for w in re.findall(r"[A-Za-z0-9]+", corp) if w.lower() not in _CORP_NOISE]
        return "".join(w[:1].upper() + w[1:] for w in words)[:24] or None
    fam = re.sub(r"[^A-Za-z]", "", fold(detex(" ".join(x for x in (n.get("von", ""), n.get("last", "")) if x))))
    return fam[:1].upper() + fam[1:] if fam else None


def _content_words(title: str, n: int) -> list[str]:
    t = re.sub(r"[^\w\s\-]", " ", fold(detex(title or "", keep_math=False)))
    out: list[str] = []
    for w in t.split():
        w = w.strip("-_")
        if not w or w.lower() in _KEY_STOP or re.fullmatch(r"\d+(?:st|nd|rd|th)?", w, re.IGNORECASE):
            continue
        cw = _pascal(w.replace("_", "-"))
        if cw and cw.lower() not in {o.lower() for o in out}:
            out.append(cw)
        if len(out) == n:
            break
    return out


def venue_tag(entry: dict, venues: list[dict]) -> str | None:
    """Short venue used only to break key collisions: the table acronym, else the
    initials of the venue (or publisher/school/institution), else "arXiv"."""
    f = entry["fields"]
    row = canonical_venue(f.get("journal") or f.get("booktitle"), venues)
    if row:
        return row["acronym"]
    for k in ("journal", "booktitle", "publisher", "school", "institution"):
        if f.get(k):
            ini = "".join(
                w[0].upper() for w in re.findall(r"[A-Za-z]+", fold(detex(f[k]))) if w.lower() not in _KEY_STOP
            )
            if ini:
                return ini[:6]
    return "arXiv" if f.get("eprint") else None


def base_key(entry: dict) -> str:
    """`<Surname><Year><FirstContentWord>`; an authorless item keys off its title."""
    f = entry["fields"]
    year = re.sub(r"\D", "", f.get("year", ""))[:4] or "nd"
    fam = _key_surname(entry)
    words = _content_words(f.get("title", ""), 2)
    if fam:
        return f"{fam}{year}{words[0] if words else 'Untitled'}"
    return f"{words[0] if words else 'Anon'}{year}{words[1] if len(words) > 1 else 'Untitled'}"


def assign_keys(entries: list[dict], venues: list[dict]) -> list[str]:
    """Canonical keys, aligned with `entries`: collisions take the venue tag,
    then a trailing letter."""
    import collections

    base = [base_key(e) for e in entries]
    groups = collections.defaultdict(list)
    for i, b in enumerate(base):
        groups[b].append(i)
    out = list(base)
    for b, idx in groups.items():
        if len(idx) == 1:
            continue
        second = collections.defaultdict(list)
        for i in idx:
            tag = venue_tag(entries[i], venues)
            second[f"{b}{tag}" if tag else b].append(i)
        for k2, idx2 in second.items():
            if len(idx2) == 1:
                out[idx2[0]] = k2
            else:
                for n, i in enumerate(sorted(idx2, key=lambda j: entries[j]["key"])):
                    out[i] = f"{k2}{chr(ord('A') + n)}"
    return out


def pin_keys(entries: list[dict], venues: list[dict], pins: list[str | None]) -> list[str]:
    """Keys aligned with `entries`: an entry with a pin keeps it; the others get a
    fresh canonical key (`assign_keys`), disambiguated against every pinned key
    with the venue tag, then a letter. A key once assigned is stable across runs
    even when later corrections change the metadata it was derived from."""
    taken = {p for p in pins if p}
    free = [i for i, p in enumerate(pins) if not p]
    out = [p or "" for p in pins]
    for i, k in zip(free, assign_keys([entries[i] for i in free], venues), strict=True):
        cand = k
        if cand in taken:
            tag = venue_tag(entries[i], venues)
            cand = f"{k}{tag}" if tag else k
            n = 0
            while cand in taken:
                cand, n = f"{k}{chr(ord('A') + n)}", n + 1
        taken.add(cand)
        out[i] = cand
    return out


def harmonise_names(entries: list[dict]) -> tuple[list[dict], list[list[dict]]]:
    """Opt-in: one spelling per person across the bibliography — each author
    takes the fuller form other entries give the same person, when that fuller
    form is unambiguous (two different expansions of "Y. Zhang" leave it alone).
    This goes beyond what each paper prints, hence opt-in. Returns the entries
    and, aligned with them, each entry's changes."""
    people = [
        [
            a
            for a in split_authors(e["fields"].get("author", ""))
            if not a.get("others") and "{" not in a.get("last", "")
        ]
        for e in entries
    ]
    out, changes = [], []
    for i, e in enumerate(entries):
        if not e["fields"].get("author"):
            out.append(e)
            changes.append([])
            continue
        names = split_authors(e["fields"]["author"])
        new = []
        for a in names:
            if a.get("others") or "{" in a.get("last", ""):
                new.append(a)
                continue
            own = detex(a.get("first", ""))
            merged = {
                _merge_given(own, detex(b.get("first", "")))
                for j, ps in enumerate(people)
                if j != i
                for b in ps
                if _same_person(a, b)
            }
            fuller = {f for f in merged if f and f != own}
            maximal = {f for f in fuller if not any(g != f and _merge_given(f, g) == g for g in fuller)}
            new.append({**a, "first": maximal.pop()} if len(maximal) == 1 else a)
        text = authors_field(new)
        if _same_authors_text(e["fields"]["author"], text):
            out.append(e)
            changes.append([])
        else:
            out.append({**e, "fields": {**e["fields"], "author": text}})
            changes.append([
                {
                    "field": "author",
                    "old": e["fields"]["author"],
                    "new": text,
                    "source": "harmonised across the bibliography",
                }
            ])
    return out, changes


# ── Dedupe ───────────────────────────────────────────────────────────────────


def _identity_keys(entry: dict, res: dict | None) -> set[str]:
    ids = identifiers(entry)
    out = {f"doi:{ids['doi']}"} if ids.get("doi") else set()
    if ids.get("arxiv"):
        out.add(f"arxiv:{ids['arxiv']}")
    rec = (res or {}).get("record")
    if rec:
        out.add(f"{rec['source']}:{rec['id']}")
        if rec.get("doi"):
            out.add(f"doi:{rec['doi']}")
        if rec.get("arxiv"):
            out.add(f"arxiv:{rec['arxiv']}")
    for d in (res or {}).get("aliases", ()):
        out.add(d)
    return out


def _is_preprint(entry: dict) -> bool:
    f = entry["fields"]
    return (
        bool(f.get("eprint"))
        or not (f.get("journal") or f.get("booktitle"))
        or bool(_PREPRINT_SERVER.search(f.get("journal", "")))
    )


def _same_publication(a: dict, b: dict) -> bool:
    """Two same-title, same-author, same-year entries are one publication only if
    their venues agree or one of them is a preprint — a conference paper and its
    journal version of the same year are two works."""
    if _is_preprint(a) or _is_preprint(b):
        return True
    va, vb = (detex(e["fields"].get("journal") or e["fields"].get("booktitle") or "") for e in (a, b))
    return _venues_agree(va, vb) or venue_key(va) == venue_key(vb)


def dedupe(entries: list[dict], results: list[dict | None]) -> tuple[list[list[int]], list[str]]:
    """Group entries that are the same work (shared DOI, arXiv id, matched source
    record, or identical normalised title + first author + year). Returns the
    groups (survivor first) and a log line per merge."""
    parent = list(range(len(entries)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    seen: dict[str, int] = {}
    for i, e in enumerate(entries):
        for k in _identity_keys(e, results[i]):
            if k in seen:
                parent[find(i)] = find(seen[k])
            else:
                seen[k] = i
    by_citation: dict[str, list[int]] = {}
    for i, e in enumerate(entries):
        v = entry_view(e)
        fa = next((a for a in v["authors"] if not a.get("others")), None)
        if v["title"] and fa:
            by_citation.setdefault(f"{''.join(title_tokens(v['title']))}|{surname(fa)}|{v['year']}", []).append(i)
    for idx in by_citation.values():
        for x, i in enumerate(idx):
            for j in idx[x + 1 :]:
                if _same_publication(entries[i], entries[j]):
                    parent[find(j)] = find(i)
    groups: dict[int, list[int]] = {}
    for i in range(len(entries)):
        groups.setdefault(find(i), []).append(i)
    rank = {
        "verified": 0,
        "corrected": 0,
        "upgraded": 0,
        "recovered": 1,
        "resolved": 0,
        "cached": 0,
        "preprint": 2,
        "unconfirmed": 2,
        "unverifiable": 3,
        "queued": 4,
    }

    def score(i: int) -> tuple:
        r = results[i] or {}
        return (rank.get(r.get("status") or "", 5), -len(entries[i]["fields"]), i)

    out, log = [], []
    for g in groups.values():
        g = sorted(g, key=score)
        out.append(g)
        if len(g) > 1:
            log.append(f"{entries[g[0]]['key']} ← " + ", ".join(entries[i]["key"] for i in g[1:]))
    out.sort(key=lambda g: g[0])
    return out, log


def merge_group(entries: list[dict], group: list[int]) -> tuple[dict, list[dict]]:
    """Lossless merge: the survivor's fields, plus any field only a duplicate has.
    Conflicting values keep the survivor's (it is the better-verified one) and
    are logged."""
    base = entries[group[0]]
    f = dict(base["fields"])
    log = []
    for i in group[1:]:
        for k, v in entries[i]["fields"].items():
            if k not in f and k not in _JUNK and k not in ("url", "urldate", "doi"):
                f[k] = v
                log.append({"field": k, "old": None, "new": v, "source": f"merged from {entries[i]['key']}"})
            elif k in f and _norm_value(f[k]) != _norm_value(v) and k not in _JUNK:
                log.append({
                    "field": k,
                    "old": v,
                    "new": f[k],
                    "source": f"conflict with {entries[i]['key']}; kept survivor's",
                })
    return {**base, "fields": f}, log


# ── bibtex-tidy, all-caps repair, validation ────────────────────────────────

TIDY_ARGS = (
    "--modify",
    "--omit=abstract,keywords,doi",
    "--curly",
    "--numeric",
    "--space=4",
    "--align=50",
    "--blank-lines",
    "--sort=year,author,type,publisher",
    "--duplicates=key,doi,citation",
    "--drop-all-caps",
    "--sort-fields",
    "--strip-comments",
    "--trailing-commas",
    "--remove-empty-fields",
)
"""The house bibtex-tidy invocation. The input path goes before the options:
bibtex-tidy 1.14 rejects `--modify` when the file comes last."""


def _run(cmd: list[str], cwd=None, timeout: float = 300) -> tuple[int, str]:
    import subprocess

    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, str(e)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def tidy(path) -> dict:
    """Run the house bibtex-tidy command in place, then restore every value it
    wrongly title-cased (`--drop-all-caps` turns PLOS ONE into Plos One and
    braces do not protect it). Returns {"ran", "duplicates", "restored", "note"}."""
    import shutil
    from pathlib import Path

    exe = shutil.which("bibtex-tidy")
    if not exe:
        return {
            "ran": False,
            "duplicates": [],
            "restored": [],
            "note": "bibtex-tidy not on PATH (npm i -g bibtex-tidy); output left untidied",
        }
    path = Path(path)
    before = parse_bib(path.read_text())["entries"]
    code, out = _run([exe, str(path), *TIDY_ARGS])
    if code != 0:
        return {"ran": False, "duplicates": [], "restored": [], "note": f"bibtex-tidy failed: {out.strip()[:300]}"}
    dups = re.findall(r"Entry (\S+) has (?:similar content|an identical DOI) to entry (\S+?)\.?$", out, re.MULTILINE)
    restored = repair_caps(path, before)
    return {"ran": True, "duplicates": [(a, b) for a, b in dups if a != b], "restored": restored, "note": None}


def repair_caps(path, before: list[dict]) -> list[str]:
    """`restore_caps` applied to a file in place; returns what it restored."""
    from pathlib import Path

    path = Path(path)
    text, restored = restore_caps(path.read_text(), before)
    path.write_text(text)
    return restored


def restore_caps(text: str, before: list[dict]) -> tuple[str, list[str]]:
    """Restore values that were entirely upper case before tidying and differ
    after it only by letter case. Edits are confined to the entry's own span, so
    an identical value elsewhere in the file is never touched."""
    old = {e["key"]: e["fields"] for e in before}
    restored = []
    for e in parse_bib(text)["entries"]:
        prev = old.get(e["key"])
        if not prev:
            continue
        for k, v in e["fields"].items():
            pv = prev.get(k)
            if pv is None or pv == v or detex(pv).lower() != detex(v).lower():
                continue
            letters = re.sub(r"[^A-Za-z]", "", detex(pv))
            if not letters or letters != letters.upper():
                continue
            span_start = text.find(e["raw"][:60])
            span = text[span_start : span_start + len(e["raw"])] if span_start >= 0 else ""
            fixed = re.sub(
                r"(\b" + re.escape(k) + r"\s*=\s*\{)" + re.escape(v) + r"(\})",
                lambda m, pv=pv: m.group(1) + pv + m.group(2),
                span,
                count=1,
            )
            if span and fixed != span:
                text = text[:span_start] + fixed + text[span_start + len(span) :]
                restored.append(f"{e['key']}.{k}: {v} → {pv}")
    return text, restored


def field_drift(before: list[dict], after_text: str) -> list[str]:
    """Values the formatter changed beyond layout (pre-mortem: a tool that
    rewrites the file makes edits nobody reviewed). Omitted and emptied fields
    and numeric months are expected; anything else is reported."""
    months = {m: str(i + 1) for i, m in enumerate(_MONTHS)}
    post = {e["key"]: e["fields"] for e in parse_bib(after_text)["entries"]}
    out = []
    for e in before:
        now = post.get(e["key"])
        if now is None:
            out.append(f"{e['key']}: missing after tidy")
            continue
        for k, v in e["fields"].items():
            if k in ("abstract", "keywords", "doi") or not v.strip():
                continue
            w = now.get(k)
            a, b = _norm_value(v).translate(_QUOTES), _norm_value(w or "").translate(_QUOTES)
            if k == "month":
                a, b = months.get(a.lower()[:3], a), months.get(b.lower()[:3], b)
            if a != b:
                out.append(f"{e['key']}.{k}: {v!r} → {w!r}")
    return out


_BIBSTYLE = re.compile(r"^[^%\n]*?\\bibliographystyle\s*\{([^}]+)\}", re.MULTILINE)


def find_bst(style: str, dirs=()) -> str | None:
    """A BibTeX style as a .bst file: `style` itself when it is one, else
    `<style>.bst` in one of `dirs` (a document's own style sits beside it), else
    on TeX's search path (`kpsewhich`). None when it is found nowhere."""
    import shutil
    from pathlib import Path

    if style.endswith(".bst") and Path(style).is_file():
        return str(Path(style).resolve())
    stem = style.removesuffix(".bst")
    for d in dirs:
        if (Path(d) / f"{stem}.bst").is_file():
            return str((Path(d) / f"{stem}.bst").resolve())
    if shutil.which("kpsewhich"):
        code, out = _run(["kpsewhich", f"{stem}.bst"], timeout=60)
        found = out.strip().splitlines()[0] if code == 0 and out.strip() else ""
        if found and Path(found).is_file():
            return found
    return None


def validation_style(style: str | None, tex=()) -> tuple[str, str]:
    """The BibTeX style to validate with and where it came from: `style` as given
    (a name, or a path to a .bst), else the first `\\bibliographystyle` the .tex
    files name that can be found, else plain. A given style that TeX cannot find
    is an error; one named in a .tex that cannot be found falls back to plain,
    noted."""
    import shutil
    from pathlib import Path

    dirs = list(dict.fromkeys(str(Path(t).resolve().parent) for t in tex))
    if style:
        found = find_bst(style, [str(Path.cwd()), *dirs])
        if not found and shutil.which("kpsewhich"):
            raise FileNotFoundError(f"no such BibTeX style: {style} (nothing was written)")
        return found or style, "given"
    named = list(
        dict.fromkeys(m.group(1).strip() for t in tex for m in _BIBSTYLE.finditer(Path(t).read_text(errors="replace")))
    )
    for name in named:
        found = find_bst(name, dirs)
        if found:
            also = [n for n in named if n != name]
            return found, "\\bibliographystyle in the .tex" + (f" (also named: {', '.join(also)})" if also else "")
    missing = f" ({', '.join(named)} not found)" if named else ""
    return find_bst("plain") or "plain", "default" + missing


def validate(path, style: str = "plain") -> dict:
    """Compile every entry with bibtex (via a hand-written .aux: no LaTeX run
    needed) in `style` — a style name or a .bst path, plain by default — and
    check biblatex's data model with `biber --tool`. Returns {"bibtex":
    [warnings] | None, "biber": [warnings] | None}; None means the tool is not
    installed."""
    import shutil
    import tempfile
    from pathlib import Path

    out: dict = {"bibtex": None, "biber": None}
    with tempfile.TemporaryDirectory() as d:
        dd = Path(d)
        (dd / "refs.bib").write_text(Path(path).read_text())
        if shutil.which("bibtex"):
            bst = find_bst(style)
            if bst:
                (dd / Path(bst).name).write_bytes(Path(bst).read_bytes())
            stem = Path(bst).stem if bst else style.removesuffix(".bst")
            (dd / "t.aux").write_text(f"\\relax\n\\citation{{*}}\n\\bibstyle{{{stem}}}\n\\bibdata{{refs}}\n")
            _run(["bibtex", "t"], cwd=d)
            blg = (dd / "t.blg").read_text(errors="replace") if (dd / "t.blg").exists() else ""
            out["bibtex"] = [
                ln.strip()
                for ln in blg.splitlines()
                if ln.startswith(("Warning--", "I was expecting", "Repeated entry")) or "error message" in ln
            ]
        if shutil.which("biber"):
            _, txt = _run(
                ["biber", "--tool", "--validate-datamodel", "--output-file=" + str(dd / "o.bib"), str(dd / "refs.bib")],
                cwd=d,
            )
            out["biber"] = [ln.split(" - ", 1)[-1] for ln in txt.splitlines() if ln.startswith(("WARN", "ERROR"))]
    return out


# ── .tex citations ───────────────────────────────────────────────────────────

_CITE_CMD = re.compile(r"\\([A-Za-z]*cite[A-Za-z]*\*?|nocite)(?![A-Za-z])")


def _map_cites(text: str, keymap: dict[str, str]) -> tuple[str, set[str], set[str]]:
    """Rewrite every key inside \\cite-family commands (natbib and biblatex
    variants, optional arguments, multi-key and \\cites-style multi-group forms).
    Each key is looked up once, so renames can never cascade. Returns the new
    text, the keys cited before and the keys cited after."""
    out, before, after = [], set(), set()
    i = 0
    for m in _CITE_CMD.finditer(text):
        if m.start() < i:
            continue
        out.append(text[i : m.end()])
        j = m.end()
        while True:
            k = _skip_ws(text, j)
            if k < len(text) and text[k] == "[":
                depth, e = 0, k
                while e < len(text):
                    depth += text[e] == "["
                    depth -= text[e] == "]"
                    e += 1
                    if depth == 0:
                        break
                out.append(text[j:e])
                j = e
                continue
            if k < len(text) and text[k] == "{":
                try:
                    inner, e = _read_braced(text, k)
                except BibSyntaxError:
                    break
                parts = []
                for tok in inner.split(","):
                    key = tok.strip()
                    if key and key != "*":
                        before.add(key)
                        new = keymap.get(key, key)
                        after.add(new)
                        tok = tok.replace(key, new, 1)
                    parts.append(tok)
                out.append(text[j:k] + "{" + ",".join(parts) + "}")
                j = e
                continue
            break
        i = j
    out.append(text[i:])
    return "".join(out), before, after


def rotate_backup(current: str, orig, prev) -> None:
    """Before a file is rewritten: the first version ever seen is kept at `orig`
    and never overwritten; the version just before this rewrite goes to `prev`
    (rolling) unless it is the original. At most two backups, one of them the
    original."""
    from pathlib import Path

    orig, prev = Path(orig), Path(prev)
    if not orig.exists():
        orig.write_text(current)
    elif current != orig.read_text():
        prev.write_text(current)


def rewrite_tex(tex_paths, keymap, bib_keys=None) -> dict:
    """Migrate `\\cite{}` keys in .tex files through `keymap` (a dict, or the path
    of a `.keymap.tsv` written by `audit`). Each file keeps its original as `.orig.bak` and the version
    before this rewrite as `.prev.bak`. A file is
    left untouched if the rewrite would leave a key undefined that was defined
    before (`bib_keys`: the keys of the new .bib, for that check)."""
    from pathlib import Path

    if not isinstance(keymap, dict):
        keymap = dict(
            ln.split("\t")[:2] for ln in Path(keymap).read_text().splitlines() if "\t" in ln and not ln.startswith("#")
        )
    report = {"rewritten": [], "skipped": [], "undefined_before": set(), "undefined_after": set()}
    old_keys = set(keymap)
    for p in map(Path, tex_paths):
        text = p.read_text()
        new, before, after = _map_cites(text, keymap)
        if bib_keys is not None:
            und_after = after - set(bib_keys)
            und_before = {k for k in before if k not in old_keys}
            broken = {keymap.get(k, k) for k in before if k in old_keys} & und_after
            report["undefined_before"] |= und_before
            report["undefined_after"] |= und_after
            if broken:
                report["skipped"].append((str(p), sorted(broken)))
                continue
        if new != text:
            rotate_backup(text, p.with_name(p.name + ".orig.bak"), p.with_name(p.name + ".prev.bak"))
            p.write_text(new)
            report["rewritten"].append(str(p))
    report["undefined_before"] = sorted(report["undefined_before"])
    report["undefined_after"] = sorted(report["undefined_after"])
    return report


# ── State, cache, report ─────────────────────────────────────────────────────

RULES_VERSION = "0.9.0-10"
"""Version of the audit rules. Cached verdicts are trusted only under the rules
that produced them: bump this whenever a change would alter the outcome for an
entry, and the next run re-audits everything once (keys stay pinned)."""


def usable_cache(cache: dict) -> dict:
    """The cache as loaded, if it was written under the current `RULES_VERSION`;
    otherwise an empty one, so every entry is audited again under the new rules."""
    if cache.get("rules") == RULES_VERSION and isinstance(cache.get("entries"), dict):
        return cache
    return {"version": 1, "rules": RULES_VERSION, "entries": {}}


_FINAL = frozenset({
    "verified",
    "corrected",
    "upgraded",
    "recovered",
    "preprint",
    "unverifiable",
    "unconfirmed",
    "resolved",
    "cached",
})


def state_dir(bib):
    """`<repo root>/.ccsci/bibaudit/<bib path relative to the root>/` — the root is
    the git work tree holding the .bib, or its directory outside git."""
    from pathlib import Path

    bib = Path(bib).resolve()
    code, out = _run(["git", "-C", str(bib.parent), "rev-parse", "--show-toplevel"], timeout=20)
    root = Path(out.strip()) if code == 0 and out.strip() else bib.parent
    try:
        rel = bib.relative_to(root)
    except ValueError:
        rel = Path(bib.name)
    slug = "__".join(rel.with_suffix("").parts)
    return root / ".ccsci" / "bibaudit" / slug


_QUOTES = str.maketrans("’‘“”", "''\"\"")
"""Typographic quotes as ASCII: bibtex-tidy writes "O’Gara" as "O'Gara"."""


def content_hash(entry: dict) -> str:
    """Fingerprint of an entry's citation content, independent of its key, field
    order, LaTeX escaping, bracing, quote style and month spelling — so an audited
    entry re-read after bibtex-tidy hashes the same, and any real edit does not."""
    import hashlib

    months = {m: str(i + 1) for i, m in enumerate(_MONTHS)}
    items = []
    for k, v in sorted(entry["fields"].items()):
        if k in _JUNK or k in ("url", "urldate") and not is_web(entry):
            continue
        nv = _norm_value(v).translate(_QUOTES)
        if k == "month":
            nv = months.get(nv.lower()[:3], nv)
        if nv:
            items.append((k, nv))
    return hashlib.sha1(json.dumps([entry["type"], items], ensure_ascii=False).encode()).hexdigest()[:16]


def _load_json(path, default):
    try:
        return json.loads(path.read_text())
    except _JSON_FILE_ERRORS:
        return default


def _summarise(rec: dict | None) -> str:
    if not rec:
        return ""
    au = ", ".join(detex(join_name(a)) for a in rec.get("authors", [])[:3]) + (
        " et al." if len(rec.get("authors", [])) > 3 else ""
    )
    ref = (
        rec.get("doi")
        and f"doi:{rec['doi']}"
        or rec.get("arxiv")
        and f"arXiv:{rec['arxiv']}"
        or f"{rec['source']}:{rec['id']}"
    )
    return f"{au} ({rec.get('year')}). {rec.get('title')}. {rec.get('venue') or ''} [{ref}]"


def _prepare(entry: dict) -> tuple[dict, list[dict]]:
    """normalise + strip: the form whose hash keys the cache and the overrides."""
    e, ch = normalise_entry(entry)
    e, ch2 = strip_entry(e)
    return e, ch + ch2


def _forced(entry: dict, rec: dict) -> dict:
    """An entry carrying `rec`'s own title and authors: how an identifier supplied
    through `resolve` overrides what the entry claimed."""
    f = dict(entry["fields"])
    f["title"] = rec["title"]
    if rec.get("authors"):
        f["author"] = authors_field(rec["authors"])
    if rec.get("year"):
        f["year"] = str(rec["year"])
    return {**entry, "fields": f}


def audit(
    bib,
    tex=(),
    *,
    offline: bool = False,
    recheck: bool = False,
    preprint_ttl_days: int = 30,
    run_tidy: bool = True,
    run_validate: bool = True,
    workers: int = 8,
    rekey: bool = False,
    harmonise: bool = False,
    style: str | None = None,
) -> dict:
    """Audit a .bib end to end and write the results.

    Every entry is verified against one routed source (Crossref by DOI in
    batches, arXiv in batches, the NeurIPS/PMLR/JMLR indices, OpenReview and its
    DBLP mirror, Crossref search), corrected from the record it matches,
    upgraded from preprint to published version where one exists, deduplicated,
    stripped to citation fields, rekeyed to `<Surname><Year><FirstContentWord>`,
    tidied with the house bibtex-tidy command and validated with bibtex and
    biber. Entries unchanged since a previous audit are not looked up again.

    Outputs: with `tex` files, the .bib is rewritten in place with the new keys
    and the \\cite{} keys in those files are migrated (each keeps `.orig.bak` and `.prev.bak`).
    Without, the .bib is rewritten in place keeping its old keys (a drop-in: a
    merged duplicate stays as a copy under its old key), next to
    `<stem>.rekeyed.bib` with the new keys and `<stem>.keymap.tsv`. State —
    cache, overrides, the findings queue, the original file and `changes.md` —
    lives under `state_dir(bib)`. Lookups for different entries run on
    `workers` threads; each host still sees paced requests. Returns a summary
    dict."""
    import datetime
    from pathlib import Path

    bib = Path(bib).resolve()
    tex = (tex,) if isinstance(tex, (str, Path)) else tuple(tex)
    missing = [str(t) for t in tex if not Path(t).is_file()]
    if missing:
        raise FileNotFoundError(f"no such .tex file: {', '.join(missing)} (nothing was written)")
    bst, bst_from = validation_style(style, tex) if run_validate else ("", "")
    text = bib.read_text()
    sd = state_dir(bib)
    sd.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now().astimezone()
    stamp = now.strftime("%Y%m%d-%H%M%S")
    today = now.date()
    rotate_backup(text, sd / "orig.bib", sd / "prev.bib")
    cache = usable_cache(_load_json(sd / "cache.json", {}))
    overrides = _load_json(sd / "overrides.json", {})
    venues = load_venues()
    pruned = prune_cache()
    net = Net(offline=offline, auth=credentials())
    if not offline:
        openreview_login(net)
    parsed = parse_bib(text)

    deleted = [{"key": None, "reason": f"unparseable: {g['reason']}", "raw": g["raw"]} for g in parsed["garbage"]]
    work = []
    for e in parsed["entries"]:
        e2, ch = _prepare(e)
        h = content_hash(e2)
        ov = overrides.get(h) or {}
        if ov.get("delete"):
            deleted.append({"key": e["key"], "reason": f"deleted on review: {ov.get('note', '')}", "raw": e["raw"]})
            continue
        why = garbage_reason(e2)
        if why and not ov.get("accept"):
            deleted.append({"key": e["key"], "reason": why, "raw": e["raw"]})
            continue
        work.append({"orig": e, "entry": e2, "hash": h, "changes": ch, "override": ov, "res": None})

    # Cached entries skip the lookups; stale preprints are re-checked for publication.
    pending = []
    for w in work:
        c = cache["entries"].get(w["hash"])
        stale = (
            c
            and c.get("preprint")
            and (today - datetime.date.fromisoformat(c.get("checked", "1970-01-01"))).days > preprint_ttl_days
        )
        if c and c.get("status") in _FINAL and not recheck and not stale and not w["override"]:
            w["res"] = {
                "status": "cached",
                "grade": c.get("grade"),
                "record": None,
                "notices": [],
                "problem": None,
                "candidates": [],
                "ids": c.get("ids", {}),
                "aliases": c.get("aliases", []),
                "cached": c,
            }
        else:
            pending.append(w)

    dois = [identifiers(w["entry"]).get("doi") for w in pending] + [w["override"].get("doi") for w in pending]
    axs = []
    for w in pending:
        ids = identifiers(w["entry"])
        if ids.get("arxiv"):
            axs.append(ids["arxiv"] + (ids.get("arxiv_version") or ""))
        if w["override"].get("arxiv"):
            axs.append(w["override"]["arxiv"])
    pre = {"crossref": crossref_by_dois(net, [d for d in dois if d]), "arxiv": arxiv_by_ids(net, axs)}
    s2_ids = [f"ARXIV:{re.sub(r'v[0-9]+$', '', a)}" for a in axs] + [f"DOI:{d}" for d in dois if d]
    pre["s2"] = s2_batch(net, s2_ids) if s2_ids and not offline else {}

    def settle(w: dict) -> dict:
        """Settle one pending entry: an answer from review, else the lookups.
        Returns the entry, its changes and its result; touches nothing shared
        but `net`."""
        ov, e = w["override"], w["entry"]
        empty = {"grade": None, "record": None, "problem": None, "candidates": []}
        if ov.get("accept"):
            note = f"accepted as is on review: {ov.get('note', '')}"
            return {"res": {**empty, "status": "resolved", "notices": [note], "ids": identifiers(e)}}
        if ov.get("fields"):
            f = dict(e["fields"])
            for k, v in ov["fields"].items():
                if v is None:
                    f.pop(k, None)
                else:
                    f[k] = v
            changes = [
                {"field": k, "old": e["fields"].get(k), "new": v, "source": f"review: {ov.get('note', '')}"}
                for k, v in ov["fields"].items()
            ]
            fixed = {**e, "fields": f}
            res = {**empty, "status": "resolved", "notices": [], "ids": identifiers(fixed)}
            return {"entry": fixed, "changes": w["changes"] + changes, "res": res}
        forced = None
        if ov.get("doi"):
            forced = pre["crossref"].get(ov["doi"].lower())
            if forced:
                fe = _forced(e, forced)
                e = {**fe, "fields": {**fe["fields"], "doi": ov["doi"]}}
        elif ov.get("arxiv"):
            forced = pre["arxiv"].get(ov["arxiv"])
            if forced:
                fe = _forced(e, forced)
                e = {**fe, "fields": {**fe["fields"], "eprint": ov["arxiv"], "archiveprefix": "arXiv"}}
        net.begin()
        res = lookup_entry(net, e, venues, pre)
        if res["status"] == "queued" and net.missed():
            res["status"] = "unchecked"
            res["notices"].append(
                f"a source was unavailable during this lookup ({', '.join(sorted(net.down))}) — re-run to retry"
            )
        if forced:
            res["notices"].insert(0, f"identifier supplied on review: {ov.get('note', '')}")
        if res["status"] == "queued" and offline:
            res["status"] = "unchecked"
        return {"res": res}

    import concurrent.futures

    def guarded(w: dict) -> dict:
        """`settle`, with an unexpected error confined to its entry: the entry
        comes back `unchecked` (retried next run) and the error is reported."""
        try:
            return settle(w)
        except Exception as e:  # noqa: BLE001 — reported in `errors`, never swallowed
            import traceback

            where = traceback.extract_tb(e.__traceback__)[-1]
            msg = f"{w['orig']['key']}: {type(e).__name__}: {e} (kernel.py:{where.lineno} in {where.name})"
            errors.append(msg)
            res = {"status": "unchecked", "grade": None, "record": None, "problem": None, "candidates": [], "ids": {}}
            return {"res": res | {"notices": [f"internal error: {msg}"]}}

    errors: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for w, out in zip(pending, pool.map(guarded, pending), strict=True):
            w.update(out)

    # Name evidence from OpenAlex (byline and registry names) and Semantic Scholar, by DOI.
    by_doi: dict[str, list[dict]] = {}
    for w in pending:
        rec = w["res"].get("record") or {}
        d = (
            rec.get("doi")
            if rec.get("doi") and not is_arxiv_doi(rec.get("doi"))
            else w["res"].get("ids", {}).get("doi")
        )
        if d and w["res"]["status"] not in ("queued", "unchecked"):
            by_doi.setdefault(d, []).append(w)
    oa = openalex_by_dois(net, list(by_doi)) if by_doi and not offline else {}
    for d, ws in by_doi.items():
        for w in ws:
            extra = oa.get(d, []) + [r for r in (pre["s2"].get(f"DOI:{d}"),) if r]
            w["res"]["evidence"] = (w["res"].get("evidence") or []) + extra

    # Apply records.
    for w in work:
        res = w["res"]
        if res.get("record") and res["status"] in ("verified", "upgraded", "recovered", "preprint", "resolved"):
            e3, ch = apply_record(w["entry"], res, venues)
            if res["status"] == "verified" and ch:
                res["status"] = "corrected"
            w["entry"], w["changes"] = e3, w["changes"] + ch
        w["entry"], ch = complete_names(w["entry"], res.get("evidence") or [])
        clash = []
        if res["status"] == "cached":
            # No lookup, so no bylines to compare: the verdict of the run that settled it.
            clash = (res.get("cached") or {}).get("name_conflicts", [])
        elif w["entry"]["fields"].get("author"):
            clash = name_conflicts(split_authors(w["entry"]["fields"]["author"]), res.get("evidence") or [])
        res["notices"] += [f"name left as is — {c}" for c in clash]
        res["byline_conflicts"] = clash
        # Read from the entry itself, so a cached entry is flagged again on every run until fixed.
        misread = [f"{f}: {m}" for f in ("author", "editor") for m in malformed_names(w["entry"]["fields"].get(f, ""))]
        res["notices"] = (res.get("notices") or []) + [f"misread by BibTeX — {m}" for m in misread]
        res["name_conflicts"] = clash + misread
        if ch:
            w["changes"] = w["changes"] + ch
            if res["status"] == "verified":
                res["status"] = "corrected"

    # Journal names from one authority (Crossref), for every article settled this run.
    todo = [w for w in pending if w["entry"]["type"] == "article" and w["entry"]["fields"].get("journal")]
    if todo and not offline:
        items = []
        for w in todo:
            rec = w["res"].get("record") or {}
            evid = [r for r in w["res"].get("evidence") or [] if r.get("source") in ("crossref", "openalex", "s2")]
            iss = [i for r in [rec, *evid] for i in (r.get("extra") or {}).get("issn", [])]
            items.append((detex(w["entry"]["fields"]["journal"]), iss))
        for w, (name, src) in zip(todo, canonical_journals_with_source(net, items, venues), strict=True):
            if src == "unreachable":
                w["res"]["retry"] = True  # not cached, so the next run completes the name
                w["res"]["notices"] = [
                    *(w["res"].get("notices") or []),
                    "journal name not checked (source unreachable); retried next run",
                ]
                continue
            old = w["entry"]["fields"]["journal"]
            if name and _norm_value(name) != _norm_value(old):
                w["entry"] = {**w["entry"], "fields": {**w["entry"]["fields"], "journal": name}}
                w["changes"] = w["changes"] + [{"field": "journal", "old": old, "new": name, "source": src}]
                if w["res"]["status"] == "verified":
                    w["res"]["status"] = "corrected"

    # Dedupe, merge, strip once more (merges can bring fields back).
    ents = [w["entry"] for w in work]
    groups, merge_log = dedupe(ents, [w["res"] for w in work])
    finals = []
    for g in groups:
        merged, mlog = merge_group(ents, g)
        merged, slog = strip_entry(merged)
        finals.append({"entry": merged, "members": g, "log": mlog + slog})

    if harmonise:
        harmonised, hch = harmonise_names([x["entry"] for x in finals])
        for x, e, ch in zip(finals, harmonised, hch, strict=True):
            x["entry"], x["log"] = e, x["log"] + ch
    # Keys: a key assigned by an earlier run stays (unless `rekey`); the rest are fresh.
    keys_state = _load_json(sd / "keys.json", {"assigned": [], "from_old": {}})
    assigned, from_old = set(keys_state.get("assigned", [])), keys_state.get("from_old", {})
    pins: list[str | None] = []
    claimed: set[str] = set()
    for x in finals:
        olds = [work[i]["orig"]["key"] for i in x["members"]]
        pin = (
            None
            if rekey
            else next((k for k in olds if k in assigned), None)
            or next((from_old[k] for k in olds if k in from_old), None)
        )
        pin = pin if pin and pin not in claimed else None
        claimed |= {pin} if pin else set()
        pins.append(pin)
    new_keys = pin_keys([x["entry"] for x in finals], venues, pins)
    keymap: dict[str, str] = {}
    ambiguous = set()
    for x, nk in zip(finals, new_keys):
        x["new_key"] = nk
        for i in x["members"]:
            ok = work[i]["orig"]["key"]
            if ok in keymap and keymap[ok] != nk:
                ambiguous.add(ok)
            keymap.setdefault(ok, nk)

    (sd / "keys.json").write_text(
        json.dumps(
            {"assigned": sorted(set(new_keys)), "from_old": {**from_old, **keymap}}, indent=1, ensure_ascii=False
        )
    )

    def with_key(e: dict, k: str) -> dict:
        return {**e, "key": k}

    outputs, tex_report = {}, None
    if tex:
        body = [with_key(x["entry"], x["new_key"]) for x in finals]
        bib.write_text(dump_bib(body, parsed["preamble"]))
        outputs["bib"] = str(bib)
    else:
        old_body, used = [], set()
        for x in finals:
            for n, i in enumerate(x["members"]):
                ok = work[i]["orig"]["key"]
                if ok.lower() in used:  # BibTeX keys are case-insensitive
                    continue
                used.add(ok.lower())
                old_body.append(with_key(x["entry"], ok))
        bib.write_text(dump_bib(old_body, parsed["preamble"]))
        rek = bib.with_name(bib.stem + ".rekeyed.bib")
        rek.write_text(dump_bib([with_key(x["entry"], x["new_key"]) for x in finals], parsed["preamble"]))
        km = bib.with_name(bib.stem + ".keymap.tsv")
        km.write_text(
            "# old key\tnew key\n"
            + "".join(f"{o}\t{n}\n" for o, n in sorted(keymap.items(), key=lambda t: t[0].lower()))
        )
        outputs.update(bib=str(bib), rekeyed=str(rek), keymap=str(km))

    tidy_report, drift, valid = {}, {}, {}
    for name in ("bib", "rekeyed"):
        if name not in outputs:
            continue
        p = Path(outputs[name])
        before = parse_bib(p.read_text())["entries"]
        if run_tidy:
            tidy_report[name] = tidy(p)
            drift[name] = field_drift(before, p.read_text()) if tidy_report[name]["ran"] else []
        if run_validate:
            valid[name] = validate(p, bst)

    if tex:
        tex_report = rewrite_tex(tex, keymap, bib_keys=[x["new_key"] for x in finals])

    # Cache every settled entry under the hash of its final form.
    for x in finals:
        rep = work[x["members"][0]]
        res = rep["res"]
        if res["status"] not in _FINAL or any(work[i]["res"].get("retry") for i in x["members"]):
            continue
        rec = res.get("record") or {}
        prior = res.get("cached") or {}
        aliases = sorted(
            set(prior.get("aliases", []))
            | {
                a
                for i in x["members"]
                for a in _identity_keys(work[i]["entry"], work[i]["res"])
                if not a.startswith("cite:")
            }
        )
        cache["entries"][content_hash(x["entry"])] = {
            "status": "cached" if res["status"] == "cached" else res["status"],
            "grade": res.get("grade"),
            "ids": {
                k: v
                for k, v in {
                    **res.get("ids", {}),
                    "doi": rec.get("doi") or res.get("ids", {}).get("doi"),
                    "arxiv": rec.get("arxiv") or res.get("ids", {}).get("arxiv"),
                }.items()
                if v and not isinstance(v, tuple)
            },
            "aliases": aliases,
            "preprint": (rec.get("type") == "preprint") or prior.get("preprint", False),
            "checked": today.isoformat() if res["status"] != "cached" else prior.get("checked", today.isoformat()),
            "record": _summarise(rec) or prior.get("record", ""),
            "name_conflicts": sorted({c for i in x["members"] for c in work[i]["res"].get("byline_conflicts") or []}),
        }
    (sd / "cache.json").write_text(json.dumps(cache, indent=1, ensure_ascii=False))

    key_of = {id(work[i]): x["new_key"] if tex else work[i]["orig"]["key"] for x in finals for i in x["members"]}
    queue = [
        {
            "key": key_of[id(w)],
            "hash": w["hash"],
            "problem": w["res"]["problem"],
            "entry": dump_entry(w["entry"]),
            "notices": w["res"]["notices"],
            "candidates": [_summarise(c) for c in w["res"].get("candidates", [])],
        }
        for w in work
        if w["res"]["status"] == "queued"
    ]
    soft = [
        {
            "key": key_of[id(w)],
            "status": w["res"]["status"],
            "record": _summarise(w["res"].get("record")),
            "title_in_entry": detex(w["orig"]["fields"].get("title", "")),
        }
        for w in work
        if w["res"].get("grade") == "soft"
    ]
    name_review = [
        {"key": key_of[id(w)], "conflicts": w["res"]["name_conflicts"]} for w in work if w["res"].get("name_conflicts")
    ]
    unconfirmed = [
        {"key": key_of[id(w)], "notices": w["res"]["notices"], "entry": dump_entry(w["entry"])}
        for w in work
        if w["res"]["status"] == "unconfirmed"
    ]
    notices = [
        {"key": key_of[id(w)], "notices": w["res"]["notices"]}
        for w in work
        if w["res"]["notices"] and w["res"]["status"] != "queued"
    ]
    known_pairs = {
        frozenset((work[i]["orig"]["key"], work[j]["orig"]["key"]))
        for x in finals
        for i in x["members"]
        for j in x["members"]
    }
    tidy_dups = sorted({
        tuple(sorted(p))
        for r in tidy_report.values()
        for p in r.get("duplicates", [])
        if frozenset(p) not in known_pairs and len(set(p)) == 2
    })
    (sd / "findings.json").write_text(
        json.dumps(
            {
                "bib": str(bib),
                "stamp": stamp,
                "queue": queue,
                "soft": soft,
                "notices": notices,
                "possible_duplicates": tidy_dups,
                "unconfirmed": unconfirmed,
                "name_conflicts": name_review,
            },
            indent=1,
            ensure_ascii=False,
        )
    )

    counts: dict[str, int] = {}
    for w in work:
        counts[w["res"]["status"]] = counts.get(w["res"]["status"], 0) + 1
    summary = {
        "bib": str(bib),
        "state": str(sd),
        "outputs": outputs,
        "entries_in": len(parsed["entries"]) + len(parsed["garbage"]),
        "entries_out": len(finals),
        "status": counts,
        "merged": merge_log,
        "deleted": [{k: d[k] for k in ("key", "reason")} for d in deleted],
        "queue": queue,
        "soft": soft,
        "notices": notices,
        "possible_duplicates": tidy_dups,
        "unconfirmed": unconfirmed,
        "name_conflicts": name_review,
        "keys_changed": sum(1 for o, n in keymap.items() if o != n),
        "ambiguous_keys": sorted(ambiguous),
        "tidy": {k: {kk: v[kk] for kk in ("ran", "restored", "note")} for k, v in tidy_report.items()},
        "drift": drift,
        "validation": valid,
        "validation_style": f"{Path(bst).name.removesuffix('.bst')} ({bst_from})" if valid else None,
        "tex": tex_report,
        "requests": net.stats,
        "request_failures": net.failures,
        "hosts_down": sorted(net.down),
        "cache_pruned": pruned,
        "credentials": [f"{h}: authenticated" for h in sorted(net.auth)],
        "credential_notes": net.notes,
        "errors": errors,
    }
    with (sd / "changes.md").open("a") as fh:
        fh.write(_report(summary, work, finals, deleted, stamp))
    return summary


def _report(s: dict, work: list[dict], finals: list[dict], deleted: list[dict], stamp: str) -> str:
    """One dated section of changes.md: headline table, then everything a reviewer acts on first."""

    def cell(v) -> str:
        return (str(v) if v is not None else "∅").replace("|", "\\|").replace("\n", " ")[:160]

    st = s["status"]
    reqs = (
        ", ".join(
            f"{h} {v['calls']}"
            + (f" (+{v['cached']} cached)" if v["cached"] else "")
            + (f", {v['failed']} failed" if v["failed"] else "")
            + (f", {v['blocked']} blocked" if v["blocked"] else "")
            + (f", {v['skipped']} skipped" if v.get("skipped") else "")
            for h, v in s["requests"].items()
        )
        or "none"
    )
    lines = [
        f"\n## Audit {stamp[:4]}-{stamp[4:6]}-{stamp[6:8]} {stamp[9:11]}:{stamp[11:13]} — `{s['bib']}`\n",
        "| | |",
        "|---|---|",
        f"| entries in → out | {s['entries_in']} → {s['entries_out']} |",
        *[f"| {k} | {v} |" for k, v in sorted(st.items())],
        f"| duplicates merged | {sum(len(x['members']) - 1 for x in finals)} |",
        f"| deleted | {len(deleted)} |",
        f"| keys changed | {s['keys_changed']} |",
        f"| requests | {reqs} |",
        "",
    ]
    if s["queue"]:
        lines += (
            ["### Needs review", ""]
            + [
                f"- `{q['key']}` — {q['problem']}" + "".join(f"\n  - candidate: {c}" for c in q["candidates"])
                for q in s["queue"]
            ]
            + [""]
        )
    idc = [
        n
        for n in s["notices"]
        if any(
            "identity corrected" in x or "belongs to another work" in x or "is another work" in x for x in n["notices"]
        )
    ]
    if idc:
        lines += (
            ["### Identity corrections — the entry described another work", ""]
            + [f"- `{n['key']}`: " + "; ".join(n["notices"]) for n in idc]
            + [""]
        )
    ext = [n for n in s["notices"] if n not in idc]
    if ext:
        lines += ["### Notices (not applied)", ""] + [f"- `{n['key']}`: " + "; ".join(n["notices"]) for n in ext] + [""]
    if s["soft"]:
        lines += ["### Soft matches — glance at these", "", "| key | entry said | matched |", "|---|---|---|"]
        lines += [f"| `{x['key']}` | {cell(x['title_in_entry'])} | {cell(x['record'])} |" for x in s["soft"]] + [""]
    if s["merged"]:
        lines += ["### Merged duplicates (survivor ← merged)", ""] + [f"- {m}" for m in s["merged"]] + [""]
    if deleted:
        lines += (
            ["### Deleted", ""]
            + [
                f"- `{d['key']}` — {d['reason']}\n\n  ```bibtex\n  " + d["raw"].replace("\n", "\n  ") + "\n  ```"
                for d in deleted
            ]
            + [""]
        )
    rows = []
    for w in work:
        for c in w["changes"]:
            if c["source"] in ("strip",) and c["field"] in _JUNK:
                continue
            rows.append(
                f"| `{w['orig']['key']}` | {c['field']} | {cell(c['old'])} | {cell(c['new'])} | {cell(c['source'])} |"
            )
    if rows:
        lines += (
            ["### Field changes", "", "| entry | field | was | now | source |", "|---|---|---|---|---|"] + rows + [""]
        )
    for name, d in s["drift"].items():
        if d:
            lines += [f"### bibtex-tidy changed values in `{name}` (review)", ""] + [f"- {x}" for x in d] + [""]
    for name, t in s["tidy"].items():
        if t.get("restored"):
            lines += (
                [f"### All-caps values restored after bibtex-tidy (`{name}`)", ""]
                + [f"- {x}" for x in t["restored"]]
                + [""]
            )
        if t.get("note"):
            lines += [f"- tidy: {t['note']}", ""]
    if s.get("validation_style"):
        lines.append(f"- validation style (bibtex): {s['validation_style']}")
    for name, v in s["validation"].items():
        for tool, msgs in v.items():
            lines.append(
                f"- validation `{name}` / {tool}: "
                + (
                    "not installed"
                    if msgs is None
                    else (f"{len(msgs)} warning(s)" + "".join(f"\n  - {m}" for m in msgs[:40]))
                )
            )
    if s["possible_duplicates"]:
        lines += ["", "### bibtex-tidy also flags as similar (not merged)", ""] + [
            f"- `{a}` / `{b}`" for a, b in s["possible_duplicates"]
        ]
    if s["credential_notes"] or s["credentials"]:
        lines += ["", "- credentials: " + "; ".join(s["credentials"] + s["credential_notes"])]
    if s["errors"]:
        lines += ["", "### Internal errors (these entries are `unchecked`; please report)", ""] + [
            f"- {x}" for x in s["errors"]
        ]
    if s["hosts_down"]:
        lines += [
            "",
            f"- **unavailable during this run** (entries they would have settled are `unchecked`, retried next run): {', '.join(s['hosts_down'])}",
        ]
    if s["request_failures"]:
        lines += ["", "### Requests that failed after retries", ""] + [f"- {x}" for x in s["request_failures"][:20]]
    if s["ambiguous_keys"]:
        lines += ["", f"- old keys shared by different works (keymap ambiguous): {', '.join(s['ambiguous_keys'])}"]
    return "\n".join(lines) + "\n"


def resolve(
    bib,
    key: str,
    *,
    doi: str | None = None,
    arxiv: str | None = None,
    fields: dict | None = None,
    accept: bool = False,
    delete: bool = False,
    note: str = "",
) -> dict:
    """Record the answer for one entry of the findings queue; the next `audit`
    applies it. Exactly one of: `doi` / `arxiv` (the work the entry really is —
    its metadata then replaces the entry's), `fields` (verbatim values for works
    no source indexes; None removes a field), `accept` (keep as is), `delete`.
    `note` should say where the answer came from; it lands in changes.md."""
    from pathlib import Path

    given = [x for x in (doi, arxiv, fields, accept or None, delete or None) if x]
    if len(given) != 1:
        raise ValueError("resolve takes exactly one of doi, arxiv, fields, accept, delete")
    bib = Path(bib).resolve()
    hits = [e for e in parse_bib(bib.read_text())["entries"] if e["key"] == key]
    if not hits:
        raise KeyError(f"no entry {key!r} in {bib}")
    e2, _ = _prepare(hits[0])
    sd = state_dir(bib)
    sd.mkdir(parents=True, exist_ok=True)
    overrides = _load_json(sd / "overrides.json", {})
    rec: dict = {"key": key, "note": note}
    if doi:
        rec["doi"] = doi.lower().removeprefix("https://doi.org/")
    elif arxiv:
        rec["arxiv"] = re.sub(r"^(?:arXiv:|https?://arxiv\.org/abs/)", "", arxiv)
    elif fields:
        rec["fields"] = fields
    elif accept:
        rec["accept"] = True
    else:
        rec["delete"] = True
    overrides[content_hash(e2)] = rec
    (sd / "overrides.json").write_text(json.dumps(overrides, indent=1, ensure_ascii=False))
    return {"recorded": rec, "hash": content_hash(e2), "state": str(sd)}
