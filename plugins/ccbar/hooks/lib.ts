/** Pure helpers for ccbar: formatting, git and transcript parsing, and the context bar's layout. */

/** A run of one colour along the bar, in eighths of a cell. */
export type BarPiece = { color: string; units: number };

/** One terminal cell of the bar: a left-aligned eighths block in `fg` over `bg`, or a blank in `bg`. */
export type BarCell = { ch: string; fg: string | undefined; bg: string };

/** Theme keys the bar draws its non-category runs in. */
export type BarColors = { fill: string; track: string; reserve: string };

const EIGHTHS = ["", "▏", "▎", "▍", "▌", "▋", "▊", "▉"];

const trimZero = (s: string): string => s.replace(/\.0$/, "");

/** Formats a token count compactly: 940, 9.4k, 49k, 1M, 3.9M. */
export function formatTokens(n: number): string {
    if (n < 1000) return String(Math.round(n));
    if (n < 9950) return `${trimZero((n / 1000).toFixed(1))}k`;
    if (n < 999_500) return `${Math.round(n / 1000)}k`;
    return `${trimZero((n / 1e6).toFixed(1))}M`;
}

/** Formats a duration down to the minute: `2d 3h 7m`, `4h 54m`, `12m`. */
export function formatCountdown(ms: number): string {
    const minutes = Math.max(0, Math.floor(ms / 60_000));
    const d = Math.floor(minutes / 1440);
    const h = Math.floor((minutes % 1440) / 60);
    const m = minutes % 60;
    if (d > 0) return `${d}d ${h}h ${m}m`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
}

/** Turns a model id (`claude-opus-5-5[1m]`) into its name (`Opus 5.5`); other spellings pass through. */
export function prettyModel(raw: string): string {
    const id = /claude-([a-z]+)-(\d{1,2})(?:-(\d{1,2}))?(?!\d)/i.exec(raw);
    if (id?.[1] && id[2]) {
        const family = id[1].charAt(0).toUpperCase() + id[1].slice(1).toLowerCase();
        return id[3] ? `${family} ${id[2]}.${id[3]}` : `${family} ${id[2]}`;
    }
    return raw.replace(/\s*\[1m\]\s*$/i, "").trim();
}

/** Reads `owner/name` off a GitHub remote URL (https, ssh or scp-like); null for any other host. */
export function parseGithub(remote: string | null): { owner: string; name: string } | null {
    if (!remote) return null;
    const m =
        /^(?:git@github\.com:|ssh:\/\/git@github\.com(?::\d+)?\/|https?:\/\/(?:[^@/]+@)?github\.com\/|git:\/\/github\.com\/)([^/\s]+)\/([^/\s]+?)(?:\.git)?\/?$/.exec(
            remote.trim()
        );
    return m?.[1] && m[2] ? { owner: m[1], name: m[2] } : null;
}

/** Reads inserted and deleted line counts off `git diff --shortstat` output. */
export function parseShortstat(text: string): { added: number; removed: number } {
    const added = /(\d+) insertions?\(\+\)/.exec(text)?.[1];
    const removed = /(\d+) deletions?\(-\)/.exec(text)?.[1];
    return { added: added ? Number(added) : 0, removed: removed ? Number(removed) : 0 };
}

const count = (v: unknown): number => (typeof v === "number" && Number.isFinite(v) && v > 0 ? v : 0);

type TranscriptLine = {
    message?: { id?: unknown; usage?: Record<string, unknown> };
};

/** A response's new-token counts so far (uncached input, output, cache write): the largest each of its lines has recorded. */
export type Counts = readonly [number, number, number];

/**
 * Adds the new tokens in whole JSONL lines to a per-response tally, and returns by how much the total grew.
 *
 * New tokens are a request's uncached input, its cache writes and its output; cache reads are the
 * conversation re-sent with every request and are left out, so the total grows by what each request
 * added, not by the history it carried again. A response is written as several lines (one per
 * content block), each repeating its usage, so a response counts once, at the largest value any of
 * its lines records for each count. A finished main-loop response repeats the same counts on every
 * line; a subagent's is written only as streaming lines (`stop_reason` null) that are never closed,
 * and the largest they record is the best there is. A later line that raises a response's counts
 * adds only the rise, so lines read in separate passes still count once.
 */
export function tallyTranscript(text: string, seen: Map<string, Counts>): number {
    let added = 0;
    for (const line of text.split("\n")) {
        if (!line.includes('"usage"')) continue;
        let parsed: TranscriptLine;
        try {
            parsed = JSON.parse(line) as TranscriptLine;
        } catch {
            continue;
        }
        const message = parsed.message;
        const usage = message?.usage;
        if (!message || !usage || typeof message.id !== "string") continue;
        const previous = seen.get(message.id) ?? [0, 0, 0];
        const merged: Counts = [
            Math.max(previous[0], count(usage.input_tokens)),
            Math.max(previous[1], count(usage.output_tokens)),
            Math.max(previous[2], count(usage.cache_creation_input_tokens)),
        ];
        added += merged[0] + merged[1] + merged[2] - (previous[0] + previous[1] + previous[2]);
        seen.set(message.id, merged);
    }
    return added;
}

/** Where a read of an append-only JSONL file stands: the byte offset of the next unread byte, and whether it lies inside a line longer than a chunk. */
export type Cursor = { offset: number; skipping: boolean };

/** Reads at most `length` bytes of the file from byte `offset`, as UTF-8 text. */
export type ReadRange = (offset: number, length: number) => Promise<string>;

/** Measures at most `length` bytes from byte `offset`: the bytes through the first newline (all of them without one), and how many newlines there are. */
export type ProbeRange = (offset: number, length: number) => Promise<{ first: number; newlines: number }>;

/**
 * Advances `cursor` over a file of `size` bytes, handing each run of whole new lines to `take`.
 *
 * A range read in text starts on a line boundary and is cut after its last newline, so the text
 * re-encodes to its exact byte length. A line longer than `chunk` is stepped over by byte counts
 * alone (`probe`), never by decoded text, which cannot say how many bytes a split character held.
 * An empty read before the end of the file is an error, not a skip.
 */
export async function drainLines(
    cursor: Cursor,
    size: number,
    chunk: number,
    read: ReadRange,
    probe: ProbeRange,
    take: (lines: string) => void
): Promise<void> {
    if (size < cursor.offset) {
        cursor.offset = 0;
        cursor.skipping = false;
    }
    while (cursor.offset < size) {
        if (cursor.skipping) {
            const { first, newlines } = await probe(cursor.offset, chunk);
            if (newlines === 0) {
                // Still inside the over-long line; at the end of the file it is still being written.
                if (cursor.offset + chunk >= size) return;
                cursor.offset += chunk;
                continue;
            }
            cursor.offset += first;
            cursor.skipping = false;
            continue;
        }
        const text = await read(cursor.offset, chunk);
        if (text === "") throw new Error(`no bytes at offset ${cursor.offset} of ${size}`);
        const cut = text.lastIndexOf("\n");
        if (cut < 0) {
            // A partial last line waits for its end; a full chunk with no newline is an over-long line.
            if (cursor.offset + chunk >= size) return;
            cursor.skipping = true;
            continue;
        }
        const lines = text.slice(0, cut + 1);
        cursor.offset += new TextEncoder().encode(lines).length;
        take(lines);
    }
}

/**
 * Splits a bar of `width` cells into coloured runs: the used window by category, the free window,
 * then the auto-compaction reserve at the end.
 *
 * The used length is exact (`tokens` over `window`); the categories share it in proportion to
 * their estimates, by largest remainder. Without categories the used run takes `colors.fill`.
 */
export function contextPieces(
    ctx: {
        tokens: number | null;
        window: number;
        threshold: number | null;
        segments: { color: string; tokens: number }[];
    },
    width: number,
    colors: BarColors
): BarPiece[] {
    const total = width * 8;
    const toUnits = (tokens: number): number => Math.round(Math.min(1, tokens / ctx.window) * total);
    const used = ctx.tokens && ctx.tokens > 0 ? Math.max(1, toUnits(ctx.tokens)) : 0;
    const reserveStart = ctx.threshold !== null && ctx.threshold < ctx.window ? toUnits(ctx.threshold) : total;

    const pieces: BarPiece[] = [];
    const segments = ctx.segments.filter((s) => s.tokens > 0);
    const estimated = segments.reduce((sum, s) => sum + s.tokens, 0);
    if (used > 0 && estimated > 0) {
        const exact = segments.map((s) => (s.tokens / estimated) * used);
        const units = exact.map(Math.floor);
        let left = used - units.reduce((a, b) => a + b, 0);
        const byRemainder = exact.map((x, i) => ({ i, r: x - Math.floor(x) })).sort((a, b) => b.r - a.r);
        for (const { i } of byRemainder) {
            if (left <= 0) break;
            units[i] = (units[i] ?? 0) + 1;
            left -= 1;
        }
        segments.forEach((s, i) => pieces.push({ color: s.color, units: units[i] ?? 0 }));
    } else if (used > 0) {
        pieces.push({ color: colors.fill, units: used });
    }
    const free = Math.max(0, reserveStart - used);
    pieces.push({ color: colors.track, units: free });
    pieces.push({ color: colors.reserve, units: total - used - free });
    return pieces.filter((p) => p.units > 0);
}

/**
 * Lays runs into cells. A cell inside one run is a blank on that colour; a cell where runs meet
 * draws the first as a left eighths block over the largest of the rest, so a boundary keeps
 * eighth-cell precision with two colours per cell.
 */
export function layBar(pieces: BarPiece[], width: number): BarCell[] {
    const queue = pieces.map((p) => ({ ...p }));
    const fallback = pieces.at(-1)?.color ?? "subtle";
    const cells: BarCell[] = [];
    for (let c = 0; c < width; c++) {
        const parts: BarPiece[] = [];
        let room = 8;
        while (room > 0 && queue.length > 0) {
            const head = queue[0];
            if (!head) break;
            const take = Math.min(head.units, room);
            const last = parts.at(-1);
            if (last && last.color === head.color) last.units += take;
            else if (take > 0) parts.push({ color: head.color, units: take });
            head.units -= take;
            room -= take;
            if (head.units <= 0) queue.shift();
        }
        const first = parts[0];
        if (!first || parts.length === 1) {
            cells.push({ ch: " ", fg: undefined, bg: first?.color ?? fallback });
            continue;
        }
        const rest = parts.slice(1).reduce((a, b) => (b.units > a.units ? b : a));
        cells.push({ ch: EIGHTHS[first.units] ?? " ", fg: first.color, bg: rest.color });
    }
    return cells;
}

/** A rate-limit window's label, as Claude's usage pages name it: `Session`, `Weekly`, `Spend`, else its kind. */
export function limitLabel(kind: string): string {
    if (kind === "five_hour") return "Session";
    if (kind === "seven_day") return "Weekly";
    if (kind === "spend_limit") return "Spend";
    const words = kind.replace(/_/g, " ");
    return words.charAt(0).toUpperCase() + words.slice(1);
}
