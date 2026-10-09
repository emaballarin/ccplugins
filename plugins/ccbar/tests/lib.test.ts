import { describe, expect, test } from "claude-code/testing";

import {
    contextPieces,
    drainLines,
    formatCountdown,
    formatTokens,
    layBar,
    parseGithub,
    parseShortstat,
    prettyModel,
    tallyTranscript,
} from "../hooks/lib";
import type { Counts } from "../hooks/lib";

const COLORS = { fill: "inactive", track: "userMessageBackground", reserve: "subtle" };

describe("formatting", () => {
    test("token counts read compactly", () => {
        expect([940, 9400, 49_212, 242_700, 999_400, 1_000_000, 3_906_339].map(formatTokens)).toEqual([
            "940",
            "9.4k",
            "49k",
            "243k",
            "999k",
            "1M",
            "3.9M",
        ]);
    });

    test("countdowns run down to the minute", () => {
        const min = 60_000;
        expect([0, 12 * min, 294 * min, 18 * 60 * min + 44 * min, 51 * 60 * min].map(formatCountdown)).toEqual([
            "0m",
            "12m",
            "4h 54m",
            "18h 44m",
            "2d 3h 0m",
        ]);
    });

    test("model ids become names, dated or not, other spellings pass through", () => {
        expect(prettyModel("claude-opus-5-5[1m]")).toBe("Opus 5.5");
        expect(prettyModel("claude-haiku-4-5-20251001")).toBe("Haiku 4.5");
        expect(prettyModel("claude-sonnet-4-20250514")).toBe("Sonnet 4");
        expect(prettyModel("Opus 5.5")).toBe("Opus 5.5");
    });
});

describe("parsing", () => {
    test("GitHub remotes in every spelling, other hosts none", () => {
        const expected = { owner: "emaballarin", name: "ccplugins" };
        expect(parseGithub("git@github.com:emaballarin/ccplugins.git")).toEqual(expected);
        expect(parseGithub("https://github.com/emaballarin/ccplugins")).toEqual(expected);
        expect(parseGithub("ssh://git@github.com/emaballarin/ccplugins.git")).toEqual(expected);
        expect(parseGithub("https://gitlab.com/emaballarin/ccplugins.git")).toBeNull();
        expect(parseGithub(null)).toBeNull();
    });

    test("shortstat counts, singular and absent", () => {
        expect(parseShortstat(" 3 files changed, 12 insertions(+), 1 deletion(-)\n")).toEqual({
            added: 12,
            removed: 1,
        });
        expect(parseShortstat(" 1 file changed, 1 insertion(+)\n")).toEqual({ added: 1, removed: 0 });
        expect(parseShortstat("")).toEqual({ added: 0, removed: 0 });
    });

    test("transcript usage counts once per response, at the largest count its lines record", () => {
        const line = (id: string, stop: string | null, output: number) =>
            JSON.stringify({
                type: "assistant",
                message: {
                    id,
                    stop_reason: stop,
                    usage: {
                        input_tokens: 2,
                        output_tokens: output,
                        cache_read_input_tokens: 900,
                        cache_creation_input_tokens: 0,
                    },
                },
            });
        const text = [
            line("a", "tool_use", 98),
            line("a", "tool_use", 98),
            JSON.stringify({ type: "user", message: { role: "user", content: "hi" } }),
            line("b", null, 4),
            line("b", "end_turn", 98),
            'not json with "usage"',
            "",
        ].join("\n");
        const seen = new Map<string, Counts>();
        // a: 100 once, not twice; b: its final 98 output tokens, not its streaming 4 on top; cache reads never.
        expect(tallyTranscript(text, seen)).toBe(200);
        expect(tallyTranscript(line("a", "end_turn", 98), seen)).toBe(0);
    });

    test("a response written only as streaming lines (a subagent's) still counts, at its largest", () => {
        const line = (output: number) =>
            JSON.stringify({
                message: { id: "s", stop_reason: null, usage: { input_tokens: 5, output_tokens: output } },
            });
        expect(tallyTranscript([line(4), line(16), line(9)].join("\n"), new Map())).toBe(21);
    });

    test("lines of one response read in separate passes add only the rise", () => {
        const line = (output: number) =>
            JSON.stringify({
                message: { id: "r", stop_reason: null, usage: { input_tokens: 5, output_tokens: output } },
            });
        const seen = new Map<string, Counts>();
        expect(tallyTranscript(line(4), seen)).toBe(9);
        expect(tallyTranscript(line(30), seen)).toBe(26);
        expect(tallyTranscript(line(12), seen)).toBe(0);
    });

    test("metered adds the cache reads, still once per response at its largest", () => {
        const line = (id: string, read: number) =>
            JSON.stringify({
                message: {
                    id,
                    stop_reason: null,
                    usage: {
                        input_tokens: 2,
                        output_tokens: 98,
                        cache_creation_input_tokens: 5,
                        cache_read_input_tokens: read,
                    },
                },
            });
        const text = [line("a", 900), line("a", 900), line("b", 1000)].join("\n");
        expect(tallyTranscript(text, new Map()), "new").toBe(210);
        const seen = new Map<string, Counts>();
        expect(tallyTranscript(text, seen, true), "metered").toBe(210 + 900 + 1000);
        expect(tallyTranscript(line("b", 1200), seen, true), "a later, larger read adds the rise").toBe(200);
        expect(tallyTranscript(line("b", 0), seen, true), "a later line without the read takes nothing away").toBe(0);
    });
});

describe("context bar", () => {
    const ctx = {
        tokens: 50_000,
        window: 1_000_000,
        threshold: 900_000,
        segments: [
            { color: "promptBorder", tokens: 10_000 },
            { color: "permission", tokens: 30_000 },
        ],
    };

    test("runs fill the bar exactly, categories first and the reserve last", () => {
        const pieces = contextPieces(ctx, 24, COLORS);
        expect(pieces.reduce((sum, p) => sum + p.units, 0)).toBe(24 * 8);
        expect(pieces.map((p) => p.color)).toEqual(["promptBorder", "permission", "userMessageBackground", "subtle"]);
        expect(pieces[0]!.units + pieces[1]!.units).toBe(Math.round(0.05 * 192));
        expect(pieces.at(-1)!.units).toBe(192 - Math.round(0.9 * 192));
    });

    test("a fresh window is all track, no reserve when compaction is off", () => {
        const pieces = contextPieces({ ...ctx, tokens: null, threshold: null, segments: [] }, 10, COLORS);
        expect(pieces).toEqual([{ color: "userMessageBackground", units: 80 }]);
    });

    test("boundaries draw an eighths block over the next colour", () => {
        const cells = layBar(
            [
                { color: "a", units: 11 },
                { color: "b", units: 13 },
            ],
            3
        );
        expect(cells).toEqual([
            { ch: " ", fg: undefined, bg: "a" },
            { ch: "▍", fg: "a", bg: "b" },
            { ch: " ", fg: undefined, bg: "b" },
        ]);
    });
});

describe("transcript reading", () => {
    const encoder = new TextEncoder();
    const decoder = new TextDecoder();
    const usageLine = (id: string): string =>
        JSON.stringify({
            message: {
                id,
                stop_reason: "end_turn",
                usage: {
                    input_tokens: 1,
                    output_tokens: 10,
                    cache_read_input_tokens: 100,
                    cache_creation_input_tokens: 1000,
                },
            },
        });

    /** `sh`'s ranges over bytes in memory: text decoded as `$.process.run` decodes it, the probe counted in bytes. */
    const ranges = (bytes: Uint8Array) => ({
        read: async (offset: number, length: number) => decoder.decode(bytes.subarray(offset, offset + length)),
        probe: async (offset: number, length: number) => {
            const slice = bytes.subarray(offset, offset + length);
            const nl = slice.indexOf(10);
            return { first: nl < 0 ? slice.length : nl + 1, newlines: slice.filter((b) => b === 10).length };
        },
    });

    const tallyAll = async (text: string, chunk: number): Promise<number> => {
        const bytes = encoder.encode(text);
        const { read, probe } = ranges(bytes);
        const seen = new Map<string, Counts>();
        let total = 0;
        await drainLines({ offset: 0, skipping: false }, bytes.length, chunk, read, probe, (lines) => {
            total += tallyTranscript(lines, seen);
        });
        return total;
    };

    test("a non-ASCII line longer than a chunk is stepped over exactly, at every chunk size", async () => {
        const text = "x".repeat(3) + "é".repeat(400) + "\n" + ["a", "b", "c"].map(usageLine).join("\n") + "\n";
        for (let chunk = 200; chunk <= 300; chunk++) {
            expect(await tallyAll(text, chunk), `chunk ${chunk}`).toBe(3033);
        }
    });

    test("many chunks of whole lines (each shorter than a chunk) lose and double nothing", async () => {
        const text = Array.from({ length: 50 }, (_, i) => usageLine(`m${i}`)).join("\n") + "\n";
        for (const chunk of [200, 333, 1000, 1 << 20])
            expect(await tallyAll(text, chunk), `chunk ${chunk}`).toBe(50_550);
    });

    test("a partial last line waits for its end; an empty read is an error, not a skip", async () => {
        const whole = usageLine("a") + "\n";
        const bytes = encoder.encode(whole + usageLine("b").slice(0, 20));
        const { read, probe } = ranges(bytes);
        const cursor = { offset: 0, skipping: false };
        await drainLines(cursor, bytes.length, 4096, read, probe, () => {});
        expect(cursor.offset).toBe(encoder.encode(whole).length);
        await expect(
            drainLines(
                { offset: 0, skipping: false },
                100,
                64,
                async () => "",
                probe,
                () => {}
            )
        ).rejects.toThrow("no bytes");
    });
});
