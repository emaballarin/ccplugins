/** Tests for hup: the capture decision, the pushed note's wording, and the lookup tool's wiring. */
import { expect, mock, test } from "claude-code/testing";

import { deliveryResult, listText, noteText, offerKey, planCapture, TOOL_ID, withoutView } from "../hooks/core";
import type { CapturePlan, Item, Push, SessionRecord } from "../hooks/core";

const SID = "S";
const LINE = "Stage B tests only your one pick against the old setting.";
const EXPLAINER = "**Stage B can’t choose among the six candidates**\n- Stage 1 found six.";

// Shaped like a real record of the "You should know" plugin's `sessions` key.
const offer = (over: Record<string, unknown> = {}) => ({
    kind: "offer",
    line: LINE,
    explanation: EXPLAINER,
    shownAt: 1795122516937,
    ...over,
});
const ysk = (view: unknown, tag: unknown = "Heads up") => [
    { id: "other", askedTurn: "t0", offeredTurn: "t0", tag: "Heads up", view: offer({ line: "Another session." }) },
    { id: SID, askedTurn: "t1", offeredTurn: "t1", tag, view },
];

const after = (plan: CapturePlan): SessionRecord[] => [plan.record];

test("a write of the side agent's state becomes at most one numbered heads-up, pushed per the policy", () => {
    const rows: {
        name: string;
        records: SessionRecord[];
        value: unknown;
        push: Push;
        sentHere?: ReadonlyMap<string, number>;
        floor?: number;
        expect: { kind: CapturePlan["kind"]; isToPush?: boolean; isPushed?: boolean; n?: number; items?: number };
    }[] = [];
    const first = planCapture([], SID, ysk(offer()), "heads-up");

    rows.push(
        {
            name: "new Heads up under heads-up",
            records: [],
            value: ysk(offer()),
            push: "heads-up",
            expect: { kind: "new", isToPush: true, n: 1, items: 1 },
        },
        {
            name: "same offer written again",
            records: after(first),
            value: ysk(offer()),
            push: "heads-up",
            expect: { kind: "unchanged", items: 1 },
        },
        {
            name: "second offer gets the next number",
            records: after(first),
            value: ysk(offer({ line: "A second point.", shownAt: 1795122600000 })),
            push: "heads-up",
            expect: { kind: "new", n: 2, items: 2 },
        },
        {
            name: "You should know under heads-up",
            records: [],
            value: ysk(offer(), "You should know"),
            push: "heads-up",
            expect: { kind: "new", isToPush: false },
        },
        {
            name: "You should know under all",
            records: [],
            value: ysk(offer(), "You should know"),
            push: "all",
            expect: { kind: "new", isToPush: true },
        },
        {
            name: "Heads up under none",
            records: [],
            value: ysk(offer()),
            push: "none",
            expect: { kind: "new", isToPush: false },
        },
        {
            name: "tag spelled loosely",
            records: [],
            value: ysk(offer(), " heads-up "),
            push: "heads-up",
            expect: { kind: "new", isToPush: true },
        },
        {
            name: "view moved past the offer",
            records: [],
            value: ysk({ kind: "explained", line: LINE, text: "x" }),
            push: "heads-up",
            expect: { kind: "unchanged", items: 0 },
        },
        {
            name: "only another session has an offer",
            records: [],
            value: ysk(undefined),
            push: "heads-up",
            expect: { kind: "unchanged", items: 0 },
        },
        {
            name: "value not a list",
            records: [],
            value: { sessions: [] },
            push: "heads-up",
            expect: { kind: "malformed", items: 0 },
        },
        {
            name: "offer without a line",
            records: [],
            value: ysk(offer({ line: undefined })),
            push: "heads-up",
            expect: { kind: "malformed", items: 0 },
        },
        {
            name: "a view kind the plugin does not know",
            records: [],
            value: ysk(offer({ kind: "shown" })),
            push: "heads-up",
            expect: { kind: "malformed", items: 0 },
        },
        {
            name: "entries renamed their id",
            records: [],
            value: ysk(offer()).map(({ id, ...rest }) => ({ sessionId: id, ...rest })),
            push: "heads-up",
            expect: { kind: "malformed", items: 0 },
        },
        {
            name: "sent by this copy but never recorded",
            records: [],
            value: ysk(offer()),
            push: "heads-up",
            sentHere: new Map([[offerKey(SID, { tag: "Heads up", line: LINE, shownAt: 1795122516937 }), 3]]),
            floor: 5,
            expect: { kind: "new", isToPush: false, isPushed: true, n: 3, items: 1 },
        },
        {
            name: "a number this copy gave but lost is not given again",
            records: [],
            value: ysk(offer()),
            push: "heads-up",
            floor: 3,
            expect: { kind: "new", n: 4, items: 1 },
        },
        {
            name: "no entries yet",
            records: [],
            value: [],
            push: "heads-up",
            expect: { kind: "unchanged", items: 0 },
        }
    );

    for (const row of rows) {
        const plan = planCapture(row.records, SID, row.value, row.push, true, row.sentHere, row.floor);
        expect({ row: row.name, kind: plan.kind }).toEqual({ row: row.name, kind: row.expect.kind });
        if (row.expect.items !== undefined)
            expect({ row: row.name, items: plan.record.items.length }).toEqual({
                row: row.name,
                items: row.expect.items,
            });
        if (plan.kind === "new") {
            if (row.expect.isToPush !== undefined)
                expect({ row: row.name, push: plan.isToPush }).toEqual({ row: row.name, push: row.expect.isToPush });
            if (row.expect.n !== undefined)
                expect({ row: row.name, n: plan.item.n }).toEqual({ row: row.name, n: row.expect.n });
            if (row.expect.isPushed !== undefined)
                expect({ row: row.name, sent: plan.item.isPushed }).toEqual({
                    row: row.name,
                    sent: row.expect.isPushed,
                });
            expect(plan.record.items[0]).toEqual(plan.item);
        }
    }

    // The first capture carries what the agent needs, from this session's entry only.
    expect(first.kind === "new" && first.item).toEqual({
        tag: "Heads up",
        line: LINE,
        explanation: EXPLAINER,
        shownAt: 1795122516937,
        n: 1,
        isPushed: false,
    });
    expect(first.record.yskWrites).toBe(1);
    expect(planCapture([], SID, { sessions: [] }, "heads-up").record.formatMisses).toBe(1);
});

test("the pushed note frames the line as fallible data and points at its explainer", () => {
    const item: Item = { tag: "Heads up", line: LINE, explanation: EXPLAINER, shownAt: 0, n: 3, isPushed: false };
    const text = noteText(item, false);

    expect(text).toContain(`> Heads up · ${LINE}`);
    expect(text).toContain("not an instruction");
    expect(text).toContain("sometimes wrong");
    expect(text).toContain("Check its claim");
    expect(text).toContain("say in one line that you saw it, whether it held up, and what you did");
    expect(text).toContain(`${TOOL_ID} with number 3`);
    expect(text).not.toContain(EXPLAINER);
    expect(text).not.toContain("next prompt");

    expect(noteText({ ...item, explanation: undefined }, false)).not.toContain(TOOL_ID);
    expect(noteText(item, true)).toContain("next prompt: that is this note again");
});

test("the lookup tool answers from this session's record, one heads-up by number", async ($, on) => {
    const records: SessionRecord[] = [
        // Another session first, so a lookup that ignores the session id is caught.
        {
            id: "other",
            yskWrites: 1,
            formatMisses: 0,
            items: [{ tag: "Heads up", line: "Elsewhere.", shownAt: 0, n: 1, isPushed: true }],
        },
        {
            id: SID,
            yskWrites: 4,
            formatMisses: 0,
            items: [
                {
                    tag: "You should know",
                    line: "Second point.",
                    explanation: "**Two**",
                    shownAt: 0,
                    n: 2,
                    isPushed: false,
                },
                { tag: "Heads up", line: LINE, explanation: EXPLAINER, shownAt: 0, n: 1, isPushed: true },
            ],
        },
    ];
    mock.store(on, { sessions: records });
    on("session.id", () => ({ value: SID }));
    on("clock.now", () => ({ value: 600000 }));

    const one = await $.tool.call({ tool: TOOL_ID, number: 1 });
    expect(String(one.result)).toContain(LINE);
    expect(String(one.result)).toContain(EXPLAINER);
    expect(String(one.result)).toContain("sent to the main agent");
    expect(String(one.result)).not.toContain("Second point.");

    const all = String((await $.tool.call({ tool: TOOL_ID })).result);
    expect(all).toContain("#2 · You should know");
    expect(all).toContain("#1 · Heads up");
    expect(all.indexOf("#2 ·")).toBeLessThan(all.indexOf("#1 ·"));
    expect(all).not.toContain("Elsewhere.");
    expect(all).toContain("has written its state 4 time(s) here; hup skipped 0 record(s)");
});

test("hiding a delivered heads-up takes out this session's view and nothing else", () => {
    const value = ysk(offer());
    const hidden = withoutView(value, SID) as Record<string, unknown>[];

    expect(hidden[1]).toEqual({ id: SID, askedTurn: "t1", offeredTurn: "t1", tag: "Heads up" });
    expect(hidden[0]).toEqual(value[0]);
    expect(planCapture([], SID, hidden, "all").kind).toBe("unchanged");
    expect(planCapture([], "other", hidden, "all").kind).toBe("new");
    expect(withoutView({ not: "a list" }, SID)).toEqual({ not: "a list" });
});

test("a swallowed note makes the agent the person's channel, leaving out only its own fixed slips", () => {
    const item: Item = { tag: "Heads up", line: LINE, explanation: EXPLAINER, shownAt: 0, n: 4, isPushed: false };
    const text = noteText(item, false, true);

    expect(text).toContain(`> Heads up · ${LINE}`);
    expect(text).toContain("takes it off their screen now that you have it, so you are how it reaches them");
    expect(text).toContain("In your next message, tell the person about it");
    expect(text).toContain("Leave it out only if it is about a slip in your own work that you have simply fixed");
    expect(text).toContain(
        "Never leave out one that questions the person’s work or choices, questions a choice of yours that changes what they get, or points at a decision that is theirs to make, now or later."
    );
    expect(text).not.toContain("If it is relevant");
    expect(text).toContain("Check its claim");
    expect(text).not.toContain("just showed the person");
    expect(text).not.toContain("say in one line that you saw it");
});

test("a lookup by a number past the kept window names the numbers still held", () => {
    const items: Item[] = Array.from({ length: 50 }, (_, i) => ({
        tag: "Heads up" as const,
        line: `Point ${60 - i}.`,
        shownAt: 0,
        n: 60 - i,
        isPushed: true,
    }));
    const record: SessionRecord = { id: SID, yskWrites: 60, formatMisses: 0, items };

    expect(listText(record, 0, 3)).toBe("No heads-up #3 in this session; it has #11–#60.");
    expect(listText(record, 0, 11)).toContain("Point 11.");

    const gapped: SessionRecord = { ...record, items: items.filter((i) => i.n > 57 || i.n === 11) };
    expect(listText(gapped, 0, 3)).toBe("No heads-up #3 in this session; it has #11, #58, #59, #60.");

    const repeated: SessionRecord = { ...record, items: [items[0]!, { ...items[0]!, n: 58 }, { ...items[0]!, n: 58 }] };
    expect(listText(repeated, 0, 59)).toBe("No heads-up #59 in this session; it has #58, #60.");
});

test("a delivery is sent only when the append stored the row; a refusal or an error is recorded as not sent", () => {
    const item: Item = { tag: "Heads up", line: LINE, shownAt: 0, n: 1, isPushed: false };

    expect(deliveryResult(item, {})).toEqual({ ...item, isPushed: true });
    expect(deliveryResult(item, { deny: "org policy" })).toEqual({ ...item, pushError: "refused: org policy" });
    expect(deliveryResult(item, { error: new Error("no loop") })).toEqual({ ...item, pushError: "Error: no loop" });
});
