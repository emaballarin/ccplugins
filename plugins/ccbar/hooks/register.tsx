/** ccbar: a quiet status band above the prompt, fed by background refreshers and drawn from one snapshot. */
import { atom, read, update } from "claude-code";
import type { Register } from "claude-code";

import type { CcbarContext, CcbarSnapshot } from "../types";
import { layout } from "./band";
import type { Counts, Cursor } from "./lib";
import { drainLines, parseGithub, parseShortstat, prettyModel, tallyTranscript } from "./lib";

const EMPTY: CcbarSnapshot = {
    model: null,
    thinking: null,
    repo: null,
    context: null,
    total: null,
    limits: [],
    now: 0,
};
const snap = atom({ plugin: "ccbar", key: "snap" } as const, EMPTY, { shape: "v3" });

/** Idle cadence; turn ends refresh on their own, and each refresher keeps its own minimum gap. */
const TICK_MS = 60_000;
const GAP_MS = { cheap: 5_000, tokens: 10_000, git: 15_000, breakdown: 30_000 };
/** How often a session whose transcript is not where its root says may rescan every project folder for it. */
const RESCAN_MS = 5 * 60_000;
const CHUNK_BYTES = 2 * 1024 * 1024;
/**
 * Columns taken off `bodyColumns` before packing: the 2 of left padding, plus 4 for the `[-]` mark. Claude Code 2.1.288
 * hands the full width; 2.1.289 already takes the mark's five off, where the 4 only make the band wrap a little early.
 */
const EDGE_COLUMNS = 6;
/** Reads a byte range of a file (`$1` from 1, `$2` the path, `$3` the length). */
const READ_RANGE = 'tail -c "+$1" -- "$2" | head -c "$3"';
/** Measures the same range: the bytes through its first newline, then how many newlines it holds. */
const PROBE_RANGE =
    'r() { tail -c "+$1" -- "$2" | head -c "$3"; }; ' +
    'printf "%s %s\\n" "$(r "$1" "$2" "$3" | head -n 1 | wc -c)" "$(r "$1" "$2" "$3" | tr -dc "\\n" | wc -c)"';

/** Runs `task` one at a time; a call that lands mid-run schedules one more run instead of overlapping. */
function singleFlight(task: () => Promise<void>): () => Promise<void> {
    let running: Promise<void> | null = null;
    let again = false;
    return () => {
        if (running) {
            again = true;
            return running;
        }
        running = (async () => {
            do {
                again = false;
                await task();
            } while (again);
        })().finally(() => {
            running = null;
        });
        return running;
    };
}

type Jobs = { all: (withBreakdown: boolean) => void; tokens: () => void; mode: () => void };

export const register: Register = (on) => {
    // Set by session.start: the refreshers close over that hook's `$`, which is never stored or passed.
    let jobs: Jobs | null = null;
    // The effort the last main-loop turn ran at, after any downgrade for the model (classic.Stop):
    // undefined before any turn ends, null after one ran on a model that takes no effort.
    let observedEffort: string | null | undefined = undefined;

    on("session.start", async ($, e, next) => {
        const started = await next(e);
        const reported = new Set<string>();

        // Transcript cursors live in the module: a reload rescans from the start, rebuilding `seen`.
        const cursors = new Map<string, Cursor>();
        const seen = new Map<string, Counts>();
        let total = 0;
        let located: { dir: string; id: string } | null = null;
        let scanned: { id: string; at: number } | null = null;

        const report = (where: string, err: unknown): void => {
            const text = `ccbar: ${where}: ${err instanceof Error ? err.message : String(err)}`;
            $.ui.log(text, { to: "debug" });
            if (!reported.has(text)) {
                reported.add(text);
                $.ui.log(text);
            }
        };

        /** Applies `change` to the snapshot at write time, writing (and so redrawing) only when it changes something. */
        const patchWith = async (change: (s: CcbarSnapshot) => CcbarSnapshot): Promise<void> => {
            const current = await read($, snap);
            if (JSON.stringify(change(current)) === JSON.stringify(current)) return;
            await update($, snap, change);
        };
        const patch = (fields: Partial<CcbarSnapshot>): Promise<void> => patchWith((s) => ({ ...s, ...fields }));

        /** One at a time and at most once per `gapMs`; calls inside the gap fold into one trailing run. */
        const paced = (where: string, gapMs: number, task: () => Promise<void>): (() => Promise<void>) => {
            const run = singleFlight(() => task().catch((err: unknown) => report(where, err)));
            let last = Number.NEGATIVE_INFINITY;
            let waiting = false;
            const call = async (): Promise<void> => {
                if (waiting) return;
                waiting = true;
                let now: number;
                try {
                    now = await $.clock.now();
                    const wait = last + gapMs - now;
                    if (wait > 0) {
                        $.clock.after(wait, () => {
                            waiting = false;
                            void call();
                        });
                        return;
                    }
                } catch (err: unknown) {
                    // A refresher whose pacing fails stays callable rather than going quiet for the session.
                    waiting = false;
                    report(where, err);
                    return;
                }
                waiting = false;
                last = now;
                await run();
            };
            return call;
        };

        const refreshModel = async (): Promise<void> => {
            await patch({ model: prettyModel(await $.session.model()) });
        };

        const refreshMode = async (): Promise<void> => {
            const row = (await $.config.list()).find((r) => r.key === "thinking");
            if (row?.value !== true) {
                await patch({ thinking: null });
                return;
            }
            const configured = (await $.settings.read()).effortLevel;
            await patch({
                thinking: {
                    effort:
                        observedEffort !== undefined ? observedEffort
                        : typeof configured === "string" ? configured
                        : null,
                },
            });
        };

        // Plumbing only: `git diff` may refresh the index and take its lock, colliding with a commit in flight.
        const refreshGit = async (): Promise<void> => {
            const repo = await $.session.repo();
            if (!repo) {
                await patch({ repo: null });
                return;
            }
            const [branch, head] = await Promise.all([
                $.process.run(["git", "branch", "--show-current"]),
                $.process.run(["git", "rev-parse", "--verify", "-q", "HEAD"]),
            ]);
            // A repository with no commit yet diffs the index against the empty tree.
            const base =
                head.exitCode === 0 ?
                    "HEAD"
                :   (await $.process.run(["git", "hash-object", "-t", "tree", "/dev/null"])).stdout.trim();
            const [unstaged, staged] = await Promise.all([
                $.process.run(["git", "diff-files", "--shortstat"]),
                $.process.run(["git", "diff-index", "--cached", "--shortstat", base]),
            ]);
            let name = branch.exitCode === 0 ? branch.stdout.trim() : "";
            if (!name && head.exitCode === 0) name = `@${head.stdout.trim().slice(0, 7)}`;
            // A failed read is no clean tree: without both counts the counter is left out.
            const counted = base !== "" && unstaged.exitCode === 0 && staged.exitCode === 0;
            const a = parseShortstat(unstaged.stdout);
            const b = parseShortstat(staged.stdout);
            const github = parseGithub(repo.remote);
            await patch({
                repo: {
                    owner: github?.owner ?? null,
                    name: github?.name ?? null,
                    branch: name,
                    changes: counted ? { added: a.added + b.added, removed: a.removed + b.removed } : null,
                },
            });
        };

        /** The live figures and the limits; the category split and the compaction point are left as they are. */
        const refreshUsage = async (): Promise<void> => {
            const usage = await $.session.usage();
            const figures = {
                tokens: usage.context.tokens ?? null,
                window: usage.context.window,
                percent: usage.context.percent ?? null,
            };
            const limits = usage.rateLimits.map((r) => ({
                kind: r.kind,
                percent: r.percentUsed,
                resetsAt: r.resetsAt ?? null,
            }));
            await patchWith((s) => ({
                ...s,
                context: { segments: [], threshold: null, ...s.context, ...figures },
                limits,
            }));
        };

        /** The /context category split and the compaction point; the live figures are left to `refreshUsage`. */
        const refreshBreakdown = async (): Promise<void> => {
            const usage = await $.session.usage({ breakdown: "summary" });
            const b = usage.context.breakdown;
            if (!b) return;
            const split = {
                threshold: b.autoCompactThreshold ?? null,
                segments: b.categories
                    .filter((c) => c.kind === "used")
                    .map((c) => ({ color: c.color, tokens: c.tokens })),
            };
            const fresh: CcbarContext = {
                tokens: usage.context.tokens ?? null,
                window: usage.context.window,
                percent: usage.context.percent ?? null,
                ...split,
            };
            await patchWith((s) => ({ ...s, context: s.context ? { ...s.context, ...split } : fresh }));
        };

        /** Finds `<config>/projects/<slug>` holding `<session id>.jsonl`; resets the tally when the id changes (/clear). */
        const locate = async (): Promise<{ dir: string; id: string } | null> => {
            const id = await $.session.id();
            if (located?.id === id) return located;
            if (located !== null || (scanned !== null && scanned.id !== id)) {
                cursors.clear();
                seen.clear();
                total = 0;
                located = null;
            }
            const home = await $.env.get("HOME");
            const config = (await $.env.get("CLAUDE_CONFIG_DIR")) ?? (home ? `${home}/.claude` : null);
            if (!config) return null;
            const projects = `${config}/projects`;
            const guess = `${projects}/${(await $.session.root()).replace(/[^a-zA-Z0-9]/g, "-")}`;
            if (await $.fs.exists(`${guess}/${id}.jsonl`)) {
                located = { dir: guess, id };
                return located;
            }
            // Before the first response there is no transcript yet: scan every project folder only now and then.
            const now = await $.clock.now();
            if (scanned?.id === id && now - scanned.at < RESCAN_MS) return null;
            scanned = { id, at: now };
            for (const entry of await $.fs.list(projects)) {
                if (entry.kind === "dir" && (await $.fs.exists(`${projects}/${entry.name}/${id}.jsonl`))) {
                    located = { dir: `${projects}/${entry.name}`, id };
                    return located;
                }
            }
            return null;
        };

        const runRange = async (script: string, path: string, offset: number, length: number): Promise<string> => {
            const run = await $.process.run(["sh", "-c", script, "ccbar", String(offset + 1), path, String(length)]);
            // The pipe reports `head`'s status alone, so `tail`'s stderr carries its failures; "Broken pipe" is no
            // failure but `tail` cut off by `head`, which it says aloud where SIGPIPE is ignored.
            const errors = run.stderr
                .split("\n")
                .filter((l) => l.trim() !== "" && !/broken pipe/i.test(l))
                .join("; ");
            if (run.exitCode !== 0 || errors !== "") {
                throw new Error(`reading ${path}: ${errors || `exit ${run.exitCode}`}`);
            }
            return run.stdout;
        };

        /** Tallies a JSONL file's new whole lines from its cursor, in ranges under the 4 MiB read limits. */
        const drain = async (path: string): Promise<void> => {
            const { size } = await $.fs.stat(path);
            const cursor = cursors.get(path) ?? { offset: 0, skipping: false };
            cursors.set(path, cursor);
            await drainLines(
                cursor,
                size,
                CHUNK_BYTES,
                (offset, length) => runRange(READ_RANGE, path, offset, length),
                async (offset, length) => {
                    const [first = NaN, newlines = NaN] = (await runRange(PROBE_RANGE, path, offset, length))
                        .trim()
                        .split(/\s+/)
                        .map(Number);
                    if (!Number.isInteger(first) || !Number.isInteger(newlines)) throw new Error(`probing ${path}`);
                    return { first, newlines };
                },
                (lines) => {
                    total += tallyTranscript(lines, seen);
                }
            );
        };

        const refreshTotal = async (): Promise<void> => {
            const where = await locate();
            if (!where) {
                await patch({ total: null });
                return;
            }
            const paths = [`${where.dir}/${where.id}.jsonl`];
            const subagents = `${where.dir}/${where.id}/subagents`;
            if (await $.fs.exists(subagents)) {
                for (const entry of await $.fs.list(subagents)) {
                    if (entry.kind === "file" && /^agent-.+\.jsonl$/.test(entry.name)) {
                        paths.push(`${subagents}/${entry.name}`);
                    }
                }
            }
            for (const path of paths) await drain(path);
            await patch({ total });
        };

        const tick = async (): Promise<void> => {
            await patch({ now: await $.clock.now() });
        };

        const clock = paced("clock", 0, tick);
        const model = paced("model", GAP_MS.cheap, refreshModel);
        const mode = paced("thinking", GAP_MS.cheap, refreshMode);
        const usage = paced("usage", GAP_MS.cheap, refreshUsage);
        const breakdown = paced("context", GAP_MS.breakdown, refreshBreakdown);
        const git = paced("git", GAP_MS.git, refreshGit);
        const tokens = paced("tokens", GAP_MS.tokens, refreshTotal);

        jobs = {
            all: (withBreakdown) => {
                void clock();
                void model();
                void mode();
                void usage();
                if (withBreakdown) void breakdown();
                void git();
                void tokens();
            },
            tokens: () => void tokens(),
            mode: () => void mode(),
        };

        $.clock.after(0, () => jobs?.all(true));
        $.clock.every(TICK_MS, () => jobs?.all(false));
        return started;
    });

    on("turn.complete", async ($, e, next) => {
        const done = await next(e);
        // A main-loop turn may have moved everything; a subagent's only the token tally.
        $.clock.after(0, () => (e.agentId === undefined ? jobs?.all(true) : jobs?.tokens()));
        return done;
    });

    on("classic.Stop", async ($, e, next) => {
        const result = await next(e);
        const effort = e.effort?.level || null;
        if (effort !== observedEffort) {
            observedEffort = effort;
            $.clock.after(0, () => jobs?.mode());
        }
        return result;
    });

    on("ui.render", { component: "AbovePrompt" }, async ($, e, next) => {
        if (e.props.hasSurvey) return next(e);
        const s = await read($, snap);
        if (!s.model && !s.context) return next(e);
        const { Box, Text } = $.ui.resolve(e);
        const rows = layout(s, Math.max(20, e.props.bodyColumns - EDGE_COLUMNS));
        return (
            <Box flexDirection="column" paddingLeft={2} marginTop={2}>
                {rows.map((row) => (
                    <Text wrap="truncate-end">
                        {row.map((r) => (
                            <Text color={r.color} backgroundColor={r.bg} bold={r.bold}>
                                {r.text}
                            </Text>
                        ))}
                    </Text>
                ))}
            </Box>
        );
    });
};
