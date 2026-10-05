import type {
    ConfigRow,
    ContextCategory,
    On,
    ProcessRunResult,
    SessionContextBreakdown,
    SessionUsage,
} from "claude-code";
import type { Engine } from "claude-code/testing";
import { expect, mock, test } from "claude-code/testing";

const HOME = "/home/u";
const ROOT = "/work/ccplugins";
const SID = "sid-1";
const PROJECT = `${HOME}/.claude/projects/-work-ccplugins`;
const TRANSCRIPT = `${PROJECT}/${SID}.jsonl`;
const NOW = Date.parse("2026-10-04T00:00:00Z");

const usage = { input_tokens: 2, output_tokens: 98, cache_read_input_tokens: 900, cache_creation_input_tokens: 0 };
const JSONL =
    [
        JSON.stringify({ message: { id: "m1", stop_reason: "tool_use", usage } }),
        JSON.stringify({ message: { id: "m1", stop_reason: "tool_use", usage } }),
        JSON.stringify({ message: { id: "m2", stop_reason: "end_turn", usage } }),
    ].join("\n") + "\n";

const category = (name: string, tokens: number, color: string, kind: ContextCategory["kind"]): ContextCategory => ({
    name,
    tokens,
    color,
    isDeferred: false,
    kind,
});

const BREAKDOWN: SessionContextBreakdown = {
    categories: [
        category("System prompt", 9_000, "promptBorder", "used"),
        category("Messages", 40_000, "purple_FOR_SUBAGENTS_ONLY", "used"),
        category("Free space", 900_000, "inactive", "free"),
    ],
    totalTokens: 49_000,
    maxTokens: 1_000_000,
    rawMaxTokens: 1_000_000,
    autocompactSource: "model-default",
    percentage: 5,
    gridRows: [],
    model: "claude-opus-5-5",
    memoryFiles: [],
    mcpTools: [],
    agents: [],
    autoCompactThreshold: 967_000,
    isAutoCompactEnabled: true,
    apiUsage: null,
};

const usageFor = (withBreakdown: boolean): SessionUsage => ({
    startedAt: NOW,
    context: {
        tokens: 49_000,
        window: 1_000_000,
        percent: 5,
        ...(withBreakdown ? { breakdown: BREAKDOWN } : {}),
    },
    rateLimits: [
        { kind: "five_hour", percentUsed: 2, resetsAt: new Date(NOW + 294 * 60_000).toISOString() },
        { kind: "seven_day", percentUsed: 26, resetsAt: new Date(NOW + 1124 * 60_000).toISOString() },
    ],
});

const ran = (stdout: string, exitCode = 0): ProcessRunResult => ({
    exitCode,
    stdout,
    stderr: "",
    isStdoutTruncated: false,
    isStderrTruncated: false,
});

const BAND = {
    component: "AbovePrompt",
    props: {
        hasSurvey: false,
        isWorking: false,
        maxRows: 10,
        bodyColumns: 200,
        scroll: { offset: 0, bodyRows: 9 },
        view: {},
    },
} as const;

/** The /config panel's thinking row, on or off. */
const THINKING = (value: boolean): ConfigRow => ({
    key: "thinking",
    label: "Thinking mode",
    kind: "boolean",
    value,
    provider: { plugin: "engine", tier: "core" },
    isLocked: false,
});

/** The engine's own ends of the chains the plugin passes on: a session that starts, a band it leaves empty. */
const engineBottom = (on: On): void => {
    on("session.start", async (_$, e) => ({ cwd: e.cwd }));
    on("ui.render", async ($, e) => {
        const { Box } = $.ui.resolve(e);
        return <Box />;
    });
};

test("the band draws model, repo, context, tokens and limits on terminal and desktop", async ($, on) => {
    engineBottom(on);
    const clock = mock.clock(on, { now: NOW });
    mock.env(on, { HOME });
    on("session.model", async () => ({ value: "claude-opus-5-5[1m]" }));
    on("config.list", async () => ({ value: [THINKING(true)] }));
    on("settings.read", async () => ({ value: { effortLevel: "high" } }));
    on("session.id", async () => ({ value: SID }));
    on("session.root", async () => ({ value: ROOT }));
    on("session.repo", async () => ({
        value: { root: ROOT, remote: "git@github.com:emaballarin/ccplugins.git", internal: false, name: null },
    }));
    on("session.usage", async (_$, e) => ({ value: usageFor(e.breakdown !== undefined) }));
    on("fs.exists", async (_$, e) => ({ value: e.path === TRANSCRIPT }));
    on("fs.stat", async (_$, e) => ({
        value: {
            kind: "file" as const,
            size: e.path === TRANSCRIPT ? new TextEncoder().encode(JSONL).length : 0,
            mtimeMs: NOW,
            isLink: false,
        },
    }));
    on("fs.list", async () => ({ value: [] }));
    on("process.run", async (_$, e) => {
        const argv = e.argv.join(" ");
        if (argv === "git branch --show-current") return { value: ran("main\n") };
        if (argv === "git rev-parse --verify -q HEAD") return { value: ran("0123456789abcdef\n") };
        if (argv === "git diff-files --shortstat")
            return { value: ran(" 2 files changed, 12 insertions(+), 1 deletion(-)\n") };
        if (argv === "git diff-index --cached --shortstat HEAD")
            return { value: ran(" 1 file changed, 2 deletions(-)\n") };
        if (e.argv[0] === "sh" && e.argv[4] === "1" && e.argv[5] === TRANSCRIPT) return { value: ran(JSONL) };
        return { value: ran("", 1) };
    });

    await $.session.start({ cwd: ROOT, surface: "terminal", isInteractive: true });
    await clock.settle();

    for (const surface of ["terminal", "desktop"] as const) {
        const ui = await $.ui.mount({ plugin: "ccbar", surface, ...BAND });
        for (const text of [
            "Opus 5.5",
            " high",
            "emaballarin/",
            "ccplugins",
            "main",
            "+12",
            "−3",
            " 49k",
            "/1M",
            "5%",
            "Tok Σ ",
            "2k",
        ]) {
            expect(await ui.find({ type: "Text", text }), `${surface}: ${text}`).toBeDefined();
        }
        expect(await ui.find({ type: "Text", text: /3k/ }), `${surface}: m1 counted twice`).toBeUndefined();
        expect(await ui.find({ type: "Text", text: /thinking/ }), `${surface}: effort alone`).toBeUndefined();
        expect(await ui.find({ type: "Text", text: "  ·  " }), `${surface}: group separator`).toBeDefined();
        expect(await ui.find({ type: "Text", text: /resets in|│/ }), `${surface}: old limit form`).toBeUndefined();
        expect(await ui.find({ type: "Text", text: /^Session $/ }), `${surface}: session label`).toBeDefined();
        expect(await ui.find({ type: "Text", text: /^Weekly $/ }), `${surface}: weekly label`).toBeDefined();
        expect(await ui.find({ type: "Text", text: /^ \(4h 54m\)$/ }), `${surface}: session reset`).toBeDefined();
        expect(await ui.find({ type: "Text", text: /^ \(18h 44m\)$/ }), `${surface}: weekly reset`).toBeDefined();
        await ui.unmount();
    }
});

test("the band yields to a survey", async ($, on) => {
    engineBottom(on);
    const clock = mock.clock(on, { now: NOW });
    on("ui.log", async () => ({ value: undefined }));
    on("session.model", async () => ({ value: "claude-opus-5-5" }));
    on("config.list", async () => ({ value: [THINKING(false)] }));
    await $.session.start({ cwd: ROOT, surface: "terminal", isInteractive: true });
    await clock.settle();
    const drawn = await $.ui.mount({ plugin: "ccbar", surface: "terminal", ...BAND });
    expect(await drawn.find({ type: "Text", text: /Opus/ }), "a band to yield").toBeDefined();
    await drawn.unmount();
    const ui = await $.ui.mount({
        plugin: "ccbar",
        surface: "terminal",
        ...BAND,
        props: { ...BAND.props, hasSurvey: true },
    });
    expect(await ui.find({ type: "Text", text: /Opus/ }), "yielded").toBeUndefined();
    await ui.unmount();
});

test("thinking off leaves its slot blank, and failing refreshers leave the rest drawn", async ($, on) => {
    engineBottom(on);
    const clock = mock.clock(on, { now: NOW });
    on("ui.log", async () => ({ value: undefined }));
    on("session.model", async () => ({ value: "claude-opus-5-5" }));
    on("config.list", async () => ({ value: [THINKING(false)] }));
    // An effort to show, so that thinking being off is the one thing that can hide it.
    on("settings.read", async () => ({ value: { effortLevel: "high" } }));
    await $.session.start({ cwd: ROOT, surface: "terminal", isInteractive: true });
    await clock.settle();
    const ui = await $.ui.mount({ plugin: "ccbar", surface: "terminal", ...BAND });
    expect(await ui.find({ type: "Text", text: "Opus 5.5" })).toBeDefined();
    expect(await ui.find({ type: "Text", text: /high|xhigh|medium|low|max/ })).toBeUndefined();
    await ui.unmount();
});

/** A session in a repository whose git answers `git`; every source not stubbed fails quietly. */
const repoSession = async ($: Engine, on: On, git: (argv: string) => ProcessRunResult): Promise<void> => {
    engineBottom(on);
    const clock = mock.clock(on, { now: NOW });
    on("ui.log", async () => ({ value: undefined }));
    on("session.model", async () => ({ value: "claude-opus-5-5" }));
    on("config.list", async () => ({ value: [THINKING(false)] }));
    on("session.repo", async () => ({ value: { root: ROOT, remote: null, internal: false, name: null } }));
    on("process.run", async (_$, e) => ({ value: git(e.argv.join(" ")) }));
    await $.session.start({ cwd: ROOT, surface: "terminal", isInteractive: true });
    await clock.settle();
};

test("a detached HEAD shows its short hash", async ($, on) => {
    await repoSession($, on, (argv) => {
        if (argv === "git branch --show-current") return ran("");
        if (argv === "git rev-parse --verify -q HEAD") return ran("abcdef0123456789\n");
        if (argv.startsWith("git diff-")) return ran("");
        return ran("", 1);
    });
    const ui = await $.ui.mount({ plugin: "ccbar", surface: "terminal", ...BAND });
    expect(await ui.find({ type: "Text", text: "@abcdef0" }), "short hash").toBeDefined();
    expect(await ui.find({ type: "Text", text: "+0" }), "clean counter").toBeDefined();
    await ui.unmount();
});

test("a failed git read leaves the counter out rather than claiming a clean tree", async ($, on) => {
    await repoSession($, on, (argv) => {
        if (argv === "git branch --show-current") return ran("main\n");
        if (argv === "git rev-parse --verify -q HEAD") return ran("abcdef0123456789\n");
        if (argv === "git diff-files --shortstat")
            return { ...ran(""), exitCode: 128, stderr: "fatal: dubious ownership" };
        if (argv.startsWith("git diff-index")) return ran("");
        return ran("", 1);
    });
    const ui = await $.ui.mount({ plugin: "ccbar", surface: "terminal", ...BAND });
    expect(await ui.find({ type: "Text", text: "main" }), "branch").toBeDefined();
    expect(await ui.find({ type: "Text", text: /^\+\d/ }), "no counter").toBeUndefined();
    await ui.unmount();
});

test("the effort a turn ran at, from its Stop hook, overrides the setting", async ($, on) => {
    engineBottom(on);
    const clock = mock.clock(on, { now: NOW });
    on("ui.log", async () => ({ value: undefined }));
    on("session.model", async () => ({ value: "claude-opus-5-5" }));
    on("config.list", async () => ({ value: [THINKING(true)] }));
    on("settings.read", async () => ({ value: { effortLevel: "high" } }));
    on("classic.Stop", async () => ({}));
    await $.session.start({ cwd: ROOT, surface: "terminal", isInteractive: true });
    await clock.settle();
    await $.classic.Stop({ stop_hook_active: false, effort: { level: "max" } });
    await clock.advance(10_000);
    const ui = await $.ui.mount({ plugin: "ccbar", surface: "terminal", ...BAND });
    expect(await ui.find({ type: "Text", text: " max" }), "observed effort").toBeDefined();
    expect(await ui.find({ type: "Text", text: " high" }), "setting overridden").toBeUndefined();
    await ui.unmount();
});

test("a turn on a model without effort clears the effort rather than keeping the last one", async ($, on) => {
    engineBottom(on);
    const clock = mock.clock(on, { now: NOW });
    on("ui.log", async () => ({ value: undefined }));
    on("session.model", async () => ({ value: "claude-opus-5-5" }));
    on("config.list", async () => ({ value: [THINKING(true)] }));
    on("settings.read", async () => ({ value: { effortLevel: "high" } }));
    on("classic.Stop", async () => ({}));
    await $.session.start({ cwd: ROOT, surface: "terminal", isInteractive: true });
    await clock.settle();
    await $.classic.Stop({ stop_hook_active: false, effort: { level: "max" } });
    await clock.advance(10_000);
    await $.classic.Stop({ stop_hook_active: false });
    await clock.advance(10_000);
    const ui = await $.ui.mount({ plugin: "ccbar", surface: "terminal", ...BAND });
    expect(await ui.find({ type: "Text", text: "Opus 5.5" }), "model").toBeDefined();
    expect(await ui.find({ type: "Text", text: / (max|high)$/ }), "no stale effort").toBeUndefined();
    await ui.unmount();
});

test("subagent transcripts count too, including responses written only as streaming lines", async ($, on) => {
    engineBottom(on);
    const clock = mock.clock(on, { now: NOW });
    mock.env(on, { HOME });
    const SUBAGENTS = `${PROJECT}/${SID}/subagents`;
    const AGENT = `${SUBAGENTS}/agent-x.jsonl`;
    // Three streaming lines of one response and no closing line: 100 input + at most 30 output.
    const agentLines =
        [4, 30, 12]
            .map((output) =>
                JSON.stringify({
                    message: { id: "s1", stop_reason: null, usage: { input_tokens: 100, output_tokens: output } },
                })
            )
            .join("\n") + "\n";
    const files: Record<string, string> = { [TRANSCRIPT]: JSONL, [AGENT]: agentLines };
    on("ui.log", async () => ({ value: undefined }));
    on("session.model", async () => ({ value: "claude-opus-5-5" }));
    on("config.list", async () => ({ value: [THINKING(false)] }));
    on("session.id", async () => ({ value: SID }));
    on("session.root", async () => ({ value: ROOT }));
    on("fs.exists", async (_$, e) => ({ value: e.path === TRANSCRIPT || e.path === SUBAGENTS }));
    on("fs.list", async (_$, e) => ({
        value:
            e.path === SUBAGENTS
                ? [{ name: "agent-x.jsonl", kind: "file" as const, size: 0, mtimeMs: NOW, isLink: false }]
                : [],
    }));
    on("fs.stat", async (_$, e) => ({
        value: {
            kind: "file" as const,
            size: new TextEncoder().encode(files[e.path] ?? "").length,
            mtimeMs: NOW,
            isLink: false,
        },
    }));
    on("process.run", async (_$, e) => {
        const text = e.argv[0] === "sh" && e.argv[4] === "1" ? files[e.argv[5] ?? ""] : undefined;
        return { value: text === undefined ? ran("", 1) : ran(text) };
    });
    await $.session.start({ cwd: ROOT, surface: "terminal", isInteractive: true });
    await clock.settle();
    const ui = await $.ui.mount({ plugin: "ccbar", surface: "terminal", ...BAND });
    // Main: 2000 (two responses); subagent: 130 → 2130 → "2.1k".
    expect(await ui.find({ type: "Text", text: "2.1k" }), "main + subagent").toBeDefined();
    await ui.unmount();
});

test("a range cut short by head is no read failure, even where tail reports the broken pipe", async ($, on) => {
    engineBottom(on);
    const clock = mock.clock(on, { now: NOW });
    mock.env(on, { HOME });
    on("ui.log", async () => ({ value: undefined }));
    on("session.model", async () => ({ value: "claude-opus-5-5" }));
    on("config.list", async () => ({ value: [THINKING(false)] }));
    on("session.id", async () => ({ value: SID }));
    on("session.root", async () => ({ value: ROOT }));
    on("fs.exists", async (_$, e) => ({ value: e.path === TRANSCRIPT }));
    on("fs.list", async () => ({ value: [] }));
    on("fs.stat", async () => ({
        value: { kind: "file" as const, size: new TextEncoder().encode(JSONL).length, mtimeMs: NOW, isLink: false },
    }));
    on("process.run", async (_$, e) => ({
        value:
            e.argv[0] === "sh" && e.argv[4] === "1"
                ? { ...ran(JSONL), stderr: "tail: error writing 'standard output': Broken pipe\n" }
                : ran("", 1),
    }));
    await $.session.start({ cwd: ROOT, surface: "terminal", isInteractive: true });
    await clock.settle();
    const ui = await $.ui.mount({ plugin: "ccbar", surface: "terminal", ...BAND });
    expect(await ui.find({ type: "Text", text: "2k" }), "tallied despite the broken-pipe notice").toBeDefined();
    await ui.unmount();
});
