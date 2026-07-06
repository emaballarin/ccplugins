"""
Literature-review helpers for Claude Code. There is no auto-injection: load
these by importing this file by its path (see SKILL.md). The public helpers are:

    verify_dois, crossref_lookup, search_openalex, expand_citations,
    extract_dois, style_pass, resolve_published, resolve_published_all,
    dedupe_records, to_bibtex, bibtex_tidy

The module has zero import-time side effects: the top level is imports,
function definitions, and literal constants only; everything that touches the
network or a subprocess happens inside a function body. No special runtime is
required — the polite-pool contact email comes from LITREVIEW_CONTACT_EMAIL
(with a default) and the optional OpenAlex key from OPENALEX_API_KEY.
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request


DOI_PATTERN = r"10\.\d{4,9}/[^\s\"'`\]\}—–&|]+"
_UA = "ccsci-literature-review/1.0"


def litrev_contact() -> str:
    """Contact email for polite-pool API headers (Crossref / doi.org ONLY —
    never sent to OpenAlex, which takes no contact email). Reads
    LITREVIEW_CONTACT_EMAIL, falling back to a maintainer default."""
    import os

    return os.environ.get("LITREVIEW_CONTACT_EMAIL") or "emanuele@ballarin.cc"


def litrev_openalex_key() -> str | None:
    """The OpenAlex API key from OPENALEX_API_KEY, or None to fall back to
    unauthenticated calls. OpenAlex's core corpus stays reachable without a key
    (subject to shared rate limits); a key mainly raises the per-request budget.
    OpenAlex takes no `mailto` parameter."""
    import os

    return os.environ.get("OPENALEX_API_KEY") or None


def litrev_openalex_key_ok(key: str, timeout: float = 10) -> bool | None:
    """Cheap key-aliveness probe: GET /rate-limit carrying ONLY api_key.
    With no other query parameters, a 4xx here cannot be a bad-parameter
    refusal, so it cleanly disambiguates a dual-cause request-path 403. Returns
    True when the key authenticates (2xx, or 429 = authenticated but over
    budget), False when the key is refused (other 4xx), None when unknown
    (network trouble) — callers treat None like True (soft-degrade)."""
    url = "https://api.openalex.org/rate-limit?api_key=" + urllib.parse.quote(key, safe="")
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return True
        return False if 400 <= e.code < 500 else None
    except Exception:  # noqa: BLE001 — best-effort network catch, degrade to None
        return None


def litrev_openalex_get(url: str, timeout: float = 15) -> dict | None:
    """GET an api.openalex.org URL. When OPENALEX_API_KEY is set it is appended
    as ``api_key=`` (OpenAlex takes no ``mailto``); when it is absent the request
    goes out unauthenticated (OpenAlex's core corpus stays reachable keyless,
    subject to shared rate limits). With a key present, raises RuntimeError with
    an actionable message on 401/409 (key rejected/required) and on a 429 that
    survives one 2 s retry (usage limit — most commonly the daily budget, which
    resets at 00:00 UTC). A 403 is dual-cause on request paths — key rejected OR
    invalid query parameters — so it is disambiguated with one tiny /rate-limit
    probe: a confirmed-dead key raises; a live or unverifiable key returns None
    (soft-degrade, so callers' fallbacks still run). Without a key, transient
    and limit errors soft-degrade to None. Returns None on all other errors."""
    key = litrev_openalex_key()
    full = url
    if key:
        sep = "&" if "?" in url else "?"
        full = url + sep + "api_key=" + urllib.parse.quote(key, safe="")
    for attempt in (0, 1):
        req = urllib.request.Request(full, headers={"User-Agent": _UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if key and e.code in (401, 409):
                raise RuntimeError(
                    f"OpenAlex rejected the API key (HTTP {e.code}). Re-check "
                    "OPENALEX_API_KEY against https://openalex.org/settings/api, "
                    "or unset it to fall back to keyless access — do not retry "
                    "the same key."
                ) from None
            if key and e.code == 403:
                # Dual-cause status: disambiguate with the probe (see docstring).
                # Only a CONFIRMED-dead key raises; a live/unverifiable key means
                # the 403 was parameter-shaped.
                if litrev_openalex_key_ok(key, timeout) is False:
                    raise RuntimeError(
                        "OpenAlex rejected the API key (HTTP 403, and the key "
                        "also failed a direct /rate-limit check). Re-check "
                        "OPENALEX_API_KEY against https://openalex.org/settings/api, "
                        "or unset it to fall back to keyless access."
                    ) from None
                return None
            if e.code == 429:
                # One short retry: a burst 429 clears in seconds; a budget 429
                # does not.
                if attempt == 0:
                    time.sleep(2)
                    continue
                if key:
                    raise RuntimeError(
                        "The OpenAlex API key is over its usage limit (HTTP 429) "
                        "— most commonly the daily budget is exhausted (resets at "
                        "00:00 UTC). Continue with the non-OpenAlex sources."
                    ) from None
                return None
            return None
        except Exception:  # noqa: BLE001 — best-effort network catch, degrade to None
            return None
    return None


def litrev_get(url: str, timeout: float = 15) -> dict | None:
    """GET `url` and JSON-decode. One 2s retry on HTTP 429; None on any error."""
    c = litrev_contact()
    ua = _UA + (f" (mailto:{c})" if c else "")
    ua = ua.encode("ascii", "ignore").decode("ascii")
    for attempt in (0, 1):
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 0:
                time.sleep(2)
                continue
            return None
        except Exception:  # noqa: BLE001 — best-effort network catch, degrade to None
            return None
    return None


def quote_doi_path(doi: str) -> str:
    """URL-encode a DOI path; unquote each segment first so a pre-encoded
    %28 stays single-encoded (caller may pass either form)."""
    return "/".join(urllib.parse.quote(urllib.parse.unquote(seg), safe="") for seg in doi.split("/"))


def crossref_year(m: dict) -> int | None:
    """Safely extract the publication year from a CrossRef `message` record."""
    dp = (m.get("published") or {}).get("date-parts") or [[None]]
    return (dp[0] or [None])[0]


def short_authors(names: list[str]) -> str | None:
    """Collapse an author list to note form: first three names,
    semicolon-separated (names may carry internal commas), then 'et al.'
    when more authors exist or any entry is nameless. Returns None when the
    record carries no author names at all.

    Authors ride in every helper's default output so that working notes built
    from them keep the name next to the DOI and year — an `(Author Year)`
    citation written from an authorless note gets its names from parametric
    memory, which supplies plausible names, not the paper's."""
    kept = [n.strip() for n in names if n and n.strip()]
    if not kept:
        return None
    more = len(names) > 3 or len(kept) < len(names)
    return "; ".join(kept[:3]) + (" et al." if more else "")


def crossref_authors(m: dict) -> str | None:
    """Note-form author names (family names) from a CrossRef `message` record."""
    return short_authors([a.get("family") or a.get("name") or "" for a in (m.get("author") or [])])


def openalex_authors(w: dict) -> str | None:
    """Note-form author names (full display names) from an OpenAlex work record."""
    return short_authors([((a.get("author") or {}).get("display_name") or "") for a in (w.get("authorships") or [])])


def litrev_head(url: str, timeout: float = 10) -> int | None:
    """HEAD `url` WITHOUT following redirects; return the origin server's own
    status (so doi.org returns 302 for a registered DOI and 404 for an
    unregistered one — not the publisher's status). One 2s retry on 429.
    Returns None only when no status could be obtained (connection/timeout)."""
    c = litrev_contact()
    ua = (_UA + (f" (mailto:{c})" if c else "")).encode("ascii", "ignore").decode("ascii")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    for attempt in (0, 1):
        req = urllib.request.Request(url, headers={"User-Agent": ua}, method="HEAD")
        try:
            with opener.open(req, timeout=timeout) as r:
                return r.status
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 0:
                time.sleep(2)
                continue
            return e.code
        except Exception:  # noqa: BLE001 — best-effort network catch, degrade to None
            return None
    return None


def verify_dois(dois: list[str]) -> dict[str, dict]:
    """Resolve each DOI against CrossRef, with a doi.org HEAD fallback for
    DataCite/mEDRA/arXiv DOIs. Returns {doi: {ok, title?, authors?, year?,
    journal?, retracted?, registry?, error?}} where:
      ok=True  — resolves (CrossRef hit, or doi.org 2xx/3xx);
      ok=False — does NOT resolve (doi.org 404; likely fabricated or typo);
      ok=None  — could not be verified (network/transient/5xx); do not flag as
                 fabricated.
    `retracted` is True/False only on a CrossRef hit; None when the registry
    is non-CrossRef or the lookup was unverified. It flags a *retraction*
    specifically; withdrawals, errata, and expressions of concern still ride in
    CrossRef's `update-to` field and warrant a direct check on surprising
    findings (see SKILL.md)."""
    out: dict[str, dict] = {}
    for d in dois:
        d = d.strip()
        # No registration agency uses `.`/`..`/empty path segments in a DOI
        # suffix; reject up-front so a server/CDN that dot-segment-normalizes
        # can't make a fabricated identifier appear to resolve. Decode the WHOLE
        # string first then split, so encoded `..` (`%2E%2E`) and encoded
        # slashes carrying `..` (`a%2F..%2Fb`) both surface as a `..` segment.
        segs = urllib.parse.unquote(d).split("/")
        if any(seg in ("", ".", "..") for seg in segs[1:]):
            out[d] = {"ok": False, "error": "dot-segment in DOI"}
            continue
        enc = quote_doi_path(d)
        j = litrev_get(f"https://api.crossref.org/works/{enc}")
        time.sleep(0.06)
        if j and "message" in j:
            m = j["message"]
            title = (m.get("title") or [""])[0]
            upd = [u.get("type", "") for u in (m.get("update-to") or [])]
            retracted = (
                any("retract" in t.lower() for t in upd)
                or str(m.get("subtype") or "").lower() == "retraction"
                or title.upper().startswith("RETRACTED")
            )
            out[d] = {
                "ok": True,
                "title": title,
                "authors": crossref_authors(m),
                "year": crossref_year(m),
                "journal": (m.get("container-title") or [""])[0],
                "retracted": retracted,
                "registry": "crossref",
            }
            continue
        # CrossRef miss OR transient — doi.org is the authoritative resolver
        # across all registration agencies, so its verdict decides ok.
        code = litrev_head(f"https://doi.org/{enc}")
        if code is not None and 200 <= code < 400:
            out[d] = {"ok": True, "registry": "non-crossref", "retracted": None}
        elif code == 404:
            out[d] = {"ok": False}
        else:
            out[d] = {"ok": None, "error": "unverified (network)", "retracted": None}
    return out


def crossref_lookup(ref_string: str) -> dict | None:
    """Find a DOI from a free-text citation (author/title/year). Returns the
    top CrossRef match as {doi, title, authors, year, score} or None. Use when you have
    a citation's details but not its DOI — this is the alternative to guessing."""
    q = urllib.parse.quote(ref_string)
    j = litrev_get(f"https://api.crossref.org/works?query.bibliographic={q}&rows=1")
    items = (j or {}).get("message", {}).get("items", [])
    if not items:
        return None
    m = items[0]
    return {
        "doi": m.get("DOI"),
        "title": (m.get("title") or [""])[0],
        "authors": crossref_authors(m),
        "year": crossref_year(m),
        "score": m.get("score"),
    }


def search_openalex(query: str, n: int = 10, filters: str = "") -> list[dict]:
    """Search OpenAlex (open scholarly index, ~250M works across all STEM
    fields — journals, conference proceedings, and preprints). Returns up to n
    hits as [{doi, title, authors, year, cited_by, venue, oa_url}]. `filters` is
    an OpenAlex filter string, e.g. 'from_publication_date:2022-01-01' or
    'type:article'. Raises RuntimeError only when a configured OPENALEX_API_KEY
    is rejected or over its daily budget; with no key set, requests go out
    unauthenticated — do not retry a rejected key anonymously mid-sweep,
    continue with the non-OpenAlex sources."""
    q = urllib.parse.quote(query)
    flt = f"&filter={filters}" if filters else ""
    j = litrev_openalex_get(
        f"https://api.openalex.org/works?search={q}&per-page={min(n, 25)}&sort=cited_by_count:desc{flt}"
    )
    out = []
    for w in (j or {}).get("results", [])[:n]:
        loc = w.get("primary_location") or {}
        venue = ((loc.get("source") or {}) or {}).get("display_name")
        out.append({
            "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
            "title": w.get("title"),
            "authors": openalex_authors(w),
            "year": w.get("publication_year"),
            "cited_by": w.get("cited_by_count"),
            "venue": venue,
            "oa_url": (w.get("open_access") or {}).get("oa_url"),
        })
    return out


def expand_citations(doi: str, n_backward: int = 50, n_forward: int = 15) -> dict:
    """One citation-graph step in both directions via OpenAlex.
    `references` is the backward step — the paper's own bibliography (outgoing
    citations), via `filter=cited_by:<id>`, sorted most-cited first.
    `cited_by` is the forward step — papers that cite this one (incoming
    citations), via `filter=cites:<id>`. Each entry is {doi, title, authors,
    year, cited_by}. Three OpenAlex requests total (up to five when a degraded
    list query retries without `authorships`); returns empty lists when the
    DOI is unknown to OpenAlex or a transient error hit the list endpoint.
    Raises RuntimeError only when a configured OPENALEX_API_KEY is rejected
    (401/409) or over its usage limit (429 after one retry); with no key set,
    requests go out unauthenticated — do not retry a rejected key anonymously."""
    enc = quote_doi_path(doi)
    work = litrev_openalex_get(f"https://api.openalex.org/works/doi:{enc}?select=id")
    work_id = ((work or {}).get("id") or "").rsplit("/", 1)[-1]
    if not work_id:
        return {"references": [], "cited_by": []}

    def _rows(results: list) -> list[dict]:
        out = []
        for w in results or []:
            out.append({
                "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
                "title": w.get("title"),
                "authors": openalex_authors(w),
                "year": w.get("publication_year"),
                "cited_by": w.get("cited_by_count"),
            })
        return out

    def _list(filter_expr: str, n: int) -> list[dict]:
        base = f"https://api.openalex.org/works?filter={filter_expr}&sort=cited_by_count:desc&per-page={min(n, 100)}"
        j = litrev_openalex_get(base + "&select=doi,title,publication_year,cited_by_count,authorships")
        if j is None:
            # litrev_openalex_get maps a select rejection and a transient
            # error to the same None; one retry without `authorships` makes
            # the worst case an authorless expansion, not an empty one.
            j = litrev_openalex_get(base + "&select=doi,title,publication_year,cited_by_count")
        return _rows((j or {}).get("results", []))

    return {
        "references": _list(f"cited_by:{work_id}", n_backward),
        "cited_by": _list(f"cites:{work_id}", n_forward),
    }


def html_decode(s: str) -> str:
    """Minimal HTML entity decode for DOI extraction (lt/gt/amp/nbsp/slash)."""
    for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&amp;", "&"), ("&nbsp;", " "), ("&#x2F;", "/"), ("&#47;", "/")):
        s = s.replace(a, b)
    return s


def extract_dois(text: str) -> list[str]:
    """Pull every DOI-looking string from `text` (for feeding to verify_dois).
    HTML-decoded, balanced-paren SICI, `</`-truncated, markdown/punct-stripped."""
    decoded = html_decode(text)
    out: set[str] = set()
    for m in re.findall(DOI_PATTERN, decoded):
        d = m.split("</")[0]
        if d.count("<") != d.count(">"):
            d = d.split("<")[0]
        d = re.sub(r"(?:\*\*|__|[_\]\*>`,;:])+$", "", d)
        d = d.removesuffix(".")
        while d.endswith(")") and d.count("(") < d.count(")"):
            d = d[:-1]
        if len(d) > 8:
            out.add(d)
    return sorted(out)


def style_pass(draft: str, model: str | None = None) -> dict:
    """Deterministic prose lint. Returns {ok, issues:[{code,note}]} where each
    code is one of EMDASH/HONEST/PROCNOTE/PARENDOI/LONGHEAD/FLATSTRUCT.

    No LLM call by design: drafts routinely quote web/paper-retrieved
    third-party text, and a free-text fix hint the agent is instructed to
    apply would be an indirect-injection channel. The deterministic regex
    codes are the load-bearing checks. `model` is accepted and ignored."""
    del model
    issues: list[dict] = []
    w = len(draft.split()) or 1
    em = draft.count("—")
    if em > 6 and 1000 * em / w > 8:
        issues.append({
            "code": "EMDASH",
            "note": f"{em} em-dashes ({1000 * em / w:.0f}/1kw); replace most with comma/colon/period, keep at most one per paragraph",
        })
    m = re.search(
        r"\b(the\s+|an?\s+)?honest(ly)?\s+(answer|summary|read|reading|look|perspective|assessment|appraisal|take|view)\b",
        draft,
        re.IGNORECASE,
    )
    if m:
        issues.append({
            "code": "HONEST",
            "note": f"{m.group(0)!r}: drop the framing, write the sentence it was guarding",
        })
    if re.search(
        r"(DOIs?\s+(were\s+)?verif|verified against (CrossRef|PubMed)|no retraction|current as of)",
        draft,
        re.IGNORECASE,
    ):
        issues.append({"code": "PROCNOTE", "note": "process-narration line present; delete it"})
    if re.search(r"\]\(https://doi\.org/[^)\s]*\([^)\s]*\)", draft):
        issues.append({
            "code": "PARENDOI",
            "note": "DOI href contains literal ( ); URL-encode as %28 %29 so the markdown link survives simpler renderers",
        })
    h2 = [ln for ln in draft.split("\n") if ln.startswith("## ")]
    long_h2 = [ln for ln in h2 if len(ln.split()) > 8]
    if len(long_h2) >= 2:
        issues.append({
            "code": "LONGHEAD",
            "note": f"{len(long_h2)} headings read as sentences; shorten to <=6-word noun phrases",
        })
    if len(h2) >= 7 and not any(ln.startswith("### ") for ln in draft.split("\n")):
        issues.append({
            "code": "FLATSTRUCT",
            "note": f"{len(h2)} top-level sections, no subsections; group related ## under a parent and demote to ###",
        })
    return {"ok": len(issues) == 0, "issues": issues}


# --- BibTeX pipeline: resolve preprints to version-of-record, dedupe, emit ---


def is_arxiv_doi(doi: str | None) -> bool:
    """True for an arXiv DataCite DOI (10.48550/arXiv.<id>) — i.e. a preprint
    identifier, not a version-of-record DOI."""
    return bool(doi) and doi.strip().lower().startswith("10.48550/arxiv.")


def _clean_doi(doi: str | None) -> str:
    """Bare DOI: strip whitespace and any https/http doi.org (or `doi:`) prefix."""
    d = (doi or "").strip()
    for p in ("https://doi.org/", "http://doi.org/", "doi:"):
        d = d.removeprefix(p)
    return d


def _norm_title(title: str | None) -> str:
    """Lowercased alnum-token form of a title, for fuzzy equality/dedupe."""
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def _title_matches(a: str | None, b: str | None) -> bool:
    """True when two titles are plausibly the same paper: exact normalized
    match, or token Jaccard >= 0.6 (guards against a spurious search top hit)."""
    na, nb = _norm_title(a), _norm_title(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    sa, sb = set(na.split()), set(nb.split())
    return bool(sa) and bool(sb) and len(sa & sb) / len(sa | sb) >= 0.6


def _doi_from_url(url: str | None) -> str | None:
    """Extract a bare DOI from a doi.org landing-page URL, else None."""
    if not url:
        return None
    m = re.search(r"doi\.org/(10\.\d{4,9}/\S+)", url)
    return m.group(1) if m else None


def _arxiv_id_from_doi(doi: str | None) -> str | None:
    """The arXiv id embedded in an arXiv DataCite DOI (10.48550/arXiv.<id>)."""
    if not is_arxiv_doi(doi):
        return None
    parts = re.split(r"arxiv\.", _clean_doi(doi), maxsplit=1, flags=re.IGNORECASE)
    return parts[1] if len(parts) > 1 else None


def _http_text(url: str, timeout: float = 15, accept: str | None = None) -> str | None:
    """GET `url` and return the decoded body as text (no JSON parse). Sends the
    polite-pool User-Agent and an optional Accept header (used for DOI content
    negotiation). Returns None on any network/decoding error."""
    c = litrev_contact()
    ua = (_UA + (f" (mailto:{c})" if c else "")).encode("ascii", "ignore").decode("ascii")
    headers = {"User-Agent": ua}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, ValueError):
        return None


def _published_doi_from_openalex_work(w: dict | None) -> str | None:
    """The version-of-record DOI implied by an OpenAlex work: the work's own DOI
    when it is not an arXiv DOI, else a non-arXiv DOI parsed from any of its
    locations' landing pages. None when only the preprint is known."""
    if not w:
        return None
    own = _clean_doi(w.get("doi"))
    if own and not is_arxiv_doi(own):
        return own
    locs = list(w.get("locations") or [])
    pl = w.get("primary_location")
    if pl:
        locs = [pl, *locs]
    for loc in locs:
        d = _doi_from_url((loc or {}).get("landing_page_url"))
        if d and not is_arxiv_doi(d):
            return d
    return None


def _openalex_published_doi(arxiv_id: str | None, title: str | None) -> str | None:
    """OpenAlex lookup for a preprint's published DOI — by the arXiv DataCite
    DOI first, then a title search. Returns None when OpenAlex has only the
    preprint or no hit is found; a configured-but-rejected key surfaces as
    RuntimeError, which `resolve_published` catches and falls through."""
    select = "select=doi,title,primary_location,locations"
    if arxiv_id:
        w = litrev_openalex_get(
            f"https://api.openalex.org/works/doi:10.48550/arXiv.{urllib.parse.quote(arxiv_id, safe='')}?{select}"
        )
        d = _published_doi_from_openalex_work(w)
        if d:
            return d
    if title:
        q = urllib.parse.quote(title)
        j = litrev_openalex_get(f"https://api.openalex.org/works?search={q}&per-page=5&{select}")
        for w in (j or {}).get("results", []):
            if _title_matches(title, w.get("title")):
                d = _published_doi_from_openalex_work(w)
                if d:
                    return d
    return None


def _arxiv_published_doi(arxiv_id: str | None) -> str | None:
    """The published DOI an arXiv record self-reports via its <arxiv:doi> field
    (authors register it once a paper appears), or a DOI embedded in its
    <arxiv:journal_ref>. None when arXiv knows only the preprint."""
    if not arxiv_id:
        return None
    txt = _http_text(f"http://export.arxiv.org/api/query?id_list={urllib.parse.quote(arxiv_id, safe='')}&max_results=1")
    if not txt:
        return None
    m = re.search(r"<arxiv:doi[^>]*>\s*([^<\s]+)\s*</arxiv:doi>", txt)
    if m:
        d = _clean_doi(html_decode(m.group(1)))
        if d and not is_arxiv_doi(d):
            return d
    jm = re.search(r"<arxiv:journal_ref[^>]*>(.*?)</arxiv:journal_ref>", txt, re.DOTALL)
    if jm:
        dm = re.search(DOI_PATTERN, html_decode(jm.group(1)))
        if dm and not is_arxiv_doi(dm.group(0)):
            return dm.group(0)
    return None


def _crossref_published_doi(title: str | None, authors: str | None) -> str | None:
    """Crossref title(+author) search for a preprint's published DOI, accepted
    only when the top hit's title matches (Jaccard guard) and is not itself an
    arXiv DOI."""
    if not title:
        return None
    hit = crossref_lookup(title + (f" {authors}" if authors else ""))
    if not hit:
        return None
    d = _clean_doi(hit.get("doi"))
    if d and not is_arxiv_doi(d) and _title_matches(title, hit.get("title")):
        return d
    return None


def _s2_published_doi(arxiv_id: str | None) -> str | None:
    """Semantic Scholar externalIds.DOI for an arXiv id (Graph API), or None."""
    if not arxiv_id:
        return None
    obj = litrev_get(
        f"https://api.semanticscholar.org/graph/v1/paper/arXiv:{urllib.parse.quote(arxiv_id, safe='')}?fields=externalIds"
    )
    d = _clean_doi(((obj or {}).get("externalIds") or {}).get("DOI"))
    return d if d and not is_arxiv_doi(d) else None


def resolve_published(record: dict) -> dict:
    """Attach the version-of-record DOI to a single preprint record.

    `record` is a dict that may carry `arxiv_id`, `doi`, `title`, `authors`,
    `year`. When it lacks a published DOI, look one up in order — OpenAlex
    locations, the arXiv <arxiv:doi>/journal-ref, Crossref title+author search,
    Semantic Scholar externalIds — and return a copy whose `doi` is the
    published DOI, with the arXiv id preserved as `arxiv_id` and `resolved_from`
    naming the source. If nothing published is found (record already published,
    or still preprint-only), the record is returned with `arxiv_id` normalized
    and any arXiv DOI kept as the fallback identifier. Best-effort: never raises."""
    r = dict(record)
    doi = _clean_doi(r.get("doi"))
    arxiv_id = r.get("arxiv_id") or _arxiv_id_from_doi(doi)
    if arxiv_id:
        r["arxiv_id"] = arxiv_id
    if doi and not is_arxiv_doi(doi):
        r["doi"] = doi
        return r
    title, authors = r.get("title"), r.get("authors")
    sources = (
        ("openalex", lambda: _openalex_published_doi(arxiv_id, title)),
        ("arxiv", lambda: _arxiv_published_doi(arxiv_id)),
        ("crossref", lambda: _crossref_published_doi(title, authors)),
        ("semanticscholar", lambda: _s2_published_doi(arxiv_id)),
    )
    for name, fn in sources:
        try:
            found = fn()
        except (RuntimeError, urllib.error.URLError, OSError, ValueError):
            found = None
        if found:
            r["doi"] = _clean_doi(found)
            r["resolved_from"] = name
            return r
    if doi:
        r["doi"] = doi  # keep the arXiv DOI as the only identifier we have
    return r


def resolve_published_all(records: list[dict]) -> list[dict]:
    """`resolve_published` mapped over a list of records."""
    return [resolve_published(r) for r in records]


def _record_keys(r: dict) -> set[tuple[str, str]]:
    """Identity keys for dedupe: (kind, value) over DOI, normalized title,
    citation key, and arXiv id."""
    keys: set[tuple[str, str]] = set()
    doi = _clean_doi(r.get("doi")).lower()
    if doi:
        keys.add(("doi", doi))
    nt = _norm_title(r.get("title"))
    if nt:
        keys.add(("title", nt))
    ck = str(r.get("key") or r.get("citation_key") or "").strip().lower()
    if ck:
        keys.add(("key", ck))
    ax = str(r.get("arxiv_id") or "").strip().lower()
    if ax:
        keys.add(("arxiv", ax))
    return keys


def _merge_group(recs: list[dict]) -> dict:
    """Collapse records for the same work into one, preferring the published
    (non-arXiv) DOI and keeping the arXiv id as a secondary field. First-seen
    non-empty value wins per field."""
    merged: dict = {}
    for r in recs:
        for k, v in r.items():
            if v not in (None, "", []):
                merged.setdefault(k, v)
    dois = [_clean_doi(r.get("doi")) for r in recs if r.get("doi")]
    pub = next((d for d in dois if not is_arxiv_doi(d)), None)
    ax_doi = next((d for d in dois if is_arxiv_doi(d)), None)
    if pub:
        merged["doi"] = pub
    elif ax_doi:
        merged["doi"] = ax_doi
    ax_id = next((r.get("arxiv_id") for r in recs if r.get("arxiv_id")), None) or _arxiv_id_from_doi(ax_doi)
    if ax_id:
        merged["arxiv_id"] = ax_id
    return merged


def dedupe_records(records: list[dict]) -> list[dict]:
    """Collapse duplicate records into one entry each. A (preprint, published)
    pair merges under the published DOI when the two share a normalized title;
    records are further deduped by DOI, normalized title, citation key, and
    arXiv id. The survivor keeps the published DOI as its dedupe pin and carries
    the arXiv id as a secondary field. First-seen order is preserved."""
    groups: list[dict] = []
    for r in records:
        ks = _record_keys(r)
        target = next((g for g in groups if g["keys"] & ks), None)
        if target is None:
            groups.append({"keys": set(ks), "recs": [r]})
        else:
            target["keys"] |= ks
            target["recs"].append(r)
    return [_merge_group(g["recs"]) for g in groups]


def to_bibtex(dois: list[str], timeout: float = 20) -> dict[str, str]:
    """Fetch a BibTeX entry per DOI via DOI content negotiation: GET
    https://doi.org/<DOI> with `Accept: application/x-bibtex`. Returns
    {doi: bibtex} for the DOIs that resolved (failures are omitted). Run
    verify_dois first so only real DOIs reach here; the returned entries KEEP
    the DOI field — stripping it is a downstream bibtex_tidy(drop_doi=True)
    choice, never done here."""
    out: dict[str, str] = {}
    for raw in dois:
        d = _clean_doi(raw)
        if not d:
            continue
        txt = _http_text(f"https://doi.org/{quote_doi_path(d)}", timeout=timeout, accept="application/x-bibtex")
        time.sleep(0.06)
        if txt and "@" in txt:
            out[d] = txt.strip()
    return out


def bibtex_tidy(bib_path: str, drop_doi: bool = False) -> dict:
    """Run `bibtex-tidy` (npm CLI) in place on `bib_path`.

    DOI is RETAINED by default (the `--omit` list is abstract,keywords only);
    pass drop_doi=True to also omit the doi field, for a DOI-stripped .bib. All
    other flags are identical. Returns {ok, tidied, note}. When bibtex-tidy is
    not on PATH the file is left untouched and ok=False with an install note
    (`npm i -g bibtex-tidy`)."""
    import shutil
    import subprocess

    exe = shutil.which("bibtex-tidy")
    if not exe:
        return {
            "ok": False,
            "tidied": False,
            "note": "bibtex-tidy not on PATH; left the .bib untidied (install: npm i -g bibtex-tidy)",
        }
    omit = "abstract,keywords,doi" if drop_doi else "abstract,keywords"
    cmd = [
        exe,
        bib_path,  # bibtex-tidy requires input file(s) BEFORE the options
        "--modify",
        f"--omit={omit}",
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
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as e:
        return {"ok": False, "tidied": False, "note": f"bibtex-tidy failed: {e}"}
    if p.returncode != 0:
        return {"ok": False, "tidied": False, "note": f"bibtex-tidy exit {p.returncode}: {p.stderr.strip()[:300]}"}
    return {"ok": True, "tidied": True, "note": None}
