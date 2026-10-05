import { describe, expect, test } from "claude-code/testing";

import { groups, layout, loadColor, pack, SEPARATOR, width } from "../hooks/band";
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
            "Opus 5.5 xhigh  ·  [bar] 246k/1M (25%)  ·  Tok Σ 12.7M  ·  Session 9% (4h 21m)  ·  Weekly 27% (18h 11m)"
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
});
