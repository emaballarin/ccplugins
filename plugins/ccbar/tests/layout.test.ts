import { describe, expect, test } from "claude-code/testing";

import { groups, layout, linkSpans, loadColor, pack, SEPARATOR, width } from "../hooks/band";
import type { CcbarSnapshot } from "../types";

const NOW = Date.parse("2026-10-04T00:00:00Z");

const SNAP: CcbarSnapshot = {
    model: "Opus 5.5",
    thinking: { effort: "xhigh" },
    repo: null,
    context: { tokens: 246_000, window: 1_000_000, percent: 25, threshold: 967_000, segments: [] },
    total: 12_700_000,
    limits: [
        { kind: "five_hour", percent: 9, resetsAt: new Date(NOW + 261 * 60_000).toISOString() },
        { kind: "seven_day", percent: 27, resetsAt: new Date(NOW + 1091 * 60_000).toISOString() },
    ],
    now: NOW,
};

const text = (runs: { text: string }[]): string => runs.map((r) => r.text).join("");

describe("layout", () => {
    test("one row reads model, context, tokens and limits, dot-separated", () => {
        const rows = layout(SNAP, 200);
        expect(rows.length).toBe(1);
        const bar = text(groups(SNAP, 24)[1]!.slice(0, 24));
        expect(text(rows[0]!).replace(bar, "[bar]")).toBe(
            "Opus 5.5 xhigh  ·  [bar] 246k/1M (25%)  ·  Tok Σ 12.7M  ·  Session 9% (4h 21m) · Weekly 27% (18h 11m)"
        );
    });

    test("a narrower row first shrinks the bar to 16 cells", () => {
        const wide = width(layout(SNAP, 200)[0]!);
        const rows = layout(SNAP, wide - 4);
        expect(rows.length).toBe(1);
        expect(width(rows[0]!)).toBe(wide - 8);
    });

    test("rows wrap only between groups, and no row starts or ends with a separator", () => {
        const rows = layout(SNAP, 60);
        expect(rows.length).toBeGreaterThan(1);
        for (const row of rows) {
            expect(width(row)).toBeLessThanOrEqual(60);
            expect(row[0]).not.toEqual(SEPARATOR);
            expect(row.at(-1)).not.toEqual(SEPARATOR);
        }
    });

    test("a group wider than the row still gets a row of its own", () => {
        expect(pack([[{ text: "x".repeat(30) }], [{ text: "y" }]], 10).map(text)).toEqual(["x".repeat(30), "y"]);
    });

    test("effort shows only while thinking is on with a known level", () => {
        expect(text(groups({ ...SNAP, thinking: null }, 10)[0]!)).toBe("Opus 5.5");
        expect(text(groups({ ...SNAP, thinking: { effort: null } }, 10)[0]!)).toBe("Opus 5.5");
    });

    test("load colours: green below 60, yellow below 85, red from 85", () => {
        expect([0, 59.9, 60, 84.9, 85, 100].map(loadColor)).toEqual([
            "success",
            "success",
            "warning",
            "warning",
            "error",
            "error",
        ]);
    });
});

describe("repository", () => {
    test("a clean tree still shows a quiet (+0 −0) beside the branch", () => {
        const repo = { owner: null, name: null, branch: "main", changes: { added: 0, removed: 0 } };
        const group = groups({ ...SNAP, repo }, 10)[1]!;
        expect(text(group)).toBe("⎇ main (+0 −0)");
        expect(group.filter((r) => r.text.startsWith("+") || r.text.startsWith("−")).map((r) => r.color)).toEqual([
            "inactive",
            "inactive",
        ]);
    });

    test("without counts (git could not read the tree) there is no counter at all", () => {
        const repo = { owner: null, name: null, branch: "main", changes: null };
        expect(text(groups({ ...SNAP, repo }, 10)[1]!)).toBe("⎇ main");
    });

    const HOME = "https://github.com/emaballarin/ccplugins";

    test("on GitHub, owner/name links to the repository and the branch to its tree, path-encoded", () => {
        const repo = { owner: "emaballarin", name: "ccplugins", branch: "feat/x#1%2", changes: null };
        expect(groups({ ...SNAP, repo }, 10)[1]!.map((r) => [r.text, r.href])).toEqual([
            ["emaballarin/", HOME],
            ["ccplugins", HOME],
            [" ⎇ ", undefined],
            ["feat/x#1%2", `${HOME}/tree/feat/x%231%252`],
        ]);
    });

    test("a detached HEAD has no tree to open, and a repository elsewhere no page at all", () => {
        const detached = { owner: "emaballarin", name: "ccplugins", branch: "@abcdef0", changes: null };
        expect(groups({ ...SNAP, repo: detached }, 10)[1]!.map((r) => r.href)).toEqual([
            HOME,
            HOME,
            undefined,
            undefined,
        ]);
        const at = { owner: "emaballarin", name: "ccplugins", branch: "@release", changes: null };
        expect(groups({ ...SNAP, repo: at }, 10)[1]!.at(-1)!.href, "a branch named @…").toBe(`${HOME}/tree/%40release`);
        const elsewhere = { owner: null, name: null, branch: "main", changes: { added: 1, removed: 0 } };
        expect(
            groups({ ...SNAP, repo: elsewhere }, 10)[1]!
                .map((r) => r.href)
                .filter(Boolean)
        ).toEqual([]);
    });

    test("consecutive runs sharing a link make one span; every other run stands alone", () => {
        const repo = { owner: "o", name: "n", branch: "main", changes: { added: 1, removed: 0 } };
        expect(linkSpans(groups({ ...SNAP, repo }, 10)[1]!).map((s) => [text(s), s[0]!.href])).toEqual([
            ["o/n", "https://github.com/o/n"],
            [" ⎇ ", undefined],
            ["main", "https://github.com/o/n/tree/main"],
            [" (", undefined],
            ["+1", undefined],
            [" ", undefined],
            ["−0", undefined],
            [")", undefined],
        ]);
    });
});

describe("rate limits", () => {
    test("Session and Weekly wrap together, never split across rows", () => {
        // One row even with the bar at 16 cells needs `narrow` columns; 3 fewer clip the end of Weekly.
        const narrow = width(layout(SNAP, 200)[0]!) - 8;
        const rows = layout(SNAP, narrow - 3);
        expect(rows.length).toBe(2);
        expect(text(rows[1]!).trimStart()).toBe("Session 9% (4h 21m) · Weekly 27% (18h 11m)");
        expect(text(rows[0]!)).not.toContain("Session");
    });
});

describe("wrapping", () => {
    const hang = width([{ text: "Opus 5.5 xhigh  ·  " }]);

    test("continuation rows start under the first row's second segment", () => {
        const narrow = width(layout(SNAP, 200)[0]!) - 8;
        const rows = layout(SNAP, narrow - 3);
        expect(rows.length).toBe(2);
        expect(text(rows[1]!)).toBe(" ".repeat(hang) + "Session 9% (4h 21m) · Weekly 27% (18h 11m)");
        for (const row of rows) expect(width(row)).toBeLessThanOrEqual(narrow - 3);
    });

    test("where a group would not fit beside the indent, rows start at the left edge", () => {
        const rows = layout(SNAP, 60);
        expect(rows.length).toBeGreaterThan(1);
        for (const row of rows) {
            expect(width(row)).toBeLessThanOrEqual(60);
            // An indent is a run of bare spaces; a bar cell is a space on a background colour.
            const lead = row[0]!;
            expect(lead.bg === undefined && /^ +$/.test(lead.text), "indented").toBe(false);
        }
    });
});

describe("hanging indent cost", () => {
    // Mirrors layout's choice of bar width, packing flush left: the row count the indent must not exceed.
    const flatRows = (s: CcbarSnapshot, columns: number): number => {
        for (const bar of [24, 16]) if (pack(groups(s, bar), columns).length <= 1) return 1;
        return pack(groups(s, Math.max(6, Math.min(16, columns - 20))), columns).length;
    };
    const cases: [string, CcbarSnapshot][] = [
        [
            "GitHub repo",
            {
                ...SNAP,
                repo: { owner: "emaballarin", name: "ccplugins", branch: "main", changes: { added: 12, removed: 3 } },
            },
        ],
        [
            "other repo",
            { ...SNAP, repo: { owner: null, name: null, branch: "main", changes: { added: 0, removed: 0 } } },
        ],
        ["no repo", SNAP],
        ["thinking off", { ...SNAP, thinking: null }],
    ];

    test("the indent never costs a row, at any width from 40 to 200 columns", () => {
        for (const [name, s] of cases) {
            for (let columns = 40; columns <= 200; columns++) {
                expect(layout(s, columns).length, `${name} at ${columns}`).toBeLessThanOrEqual(flatRows(s, columns));
            }
        }
    });
});
