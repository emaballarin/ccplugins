/** hup: forwards "You should know" heads-ups to the main agent mid-turn and serves them through a lookup tool. */
import type { EngineInterface, Register } from "claude-code";

import {
    deliveryResult,
    isTruthy,
    listText,
    noteText,
    offerKey,
    parsePush,
    parseSwallow,
    parseRecords,
    planCapture,
    readOffer,
    recordOf,
    TOOL_NAME,
    withItem,
    withoutView,
    withRecord,
    YSK_KEY,
    YSK_PLUGIN,
} from "./core";
import type { Item, Offer, Push, SessionRecord } from "./core";

const isPushed = (record: SessionRecord, offer: Offer): boolean =>
    record.items.some((i) => i.isPushed && i.shownAt === offer.shownAt && i.line === offer.line);

/** What one loaded copy of the module remembers; it starts over at each reload. */
type Memory = {
    push: Push;
    isSwallowOn: boolean;
    queue: Promise<unknown>;
    lastOffer?: string;
    // Pushed offers whose note has not yet ridden a main-loop request: still shown.
    pending: Set<string>;
    // Offers the main agent has received; with swallowing on, the other plugin no longer sees them.
    swallowed: Set<string>;
    hasWarnedShape: boolean;
    hasWarnedError: boolean;
    // Per session, the highest heads-up number this copy has given.
    lastNumber: Map<string, number>;
    // The number each offer was given by this copy.
    numbers: Map<string, number>;
};

/** Appends the heads-up note to the main conversation; records a refusal or failure instead of throwing. */
async function deliver($: EngineInterface, item: Item, isSwallowed: boolean): Promise<Item> {
    try {
        const autoSend = await $.env.get("CLAUDE_CODE_YOU_SHOULD_KNOW_AUTO_SEND").catch((err: unknown) => {
            $.ui.log(`could not read the auto-send switch, taken as off: ${String(err)}`, { to: "debug" });
            return undefined;
        });
        // A plugin above may refuse the row: the call then resolves `{ deny }` and nothing reaches Claude.
        const sent = await $.session.append({
            message: {
                type: "user",
                content: [{ type: "text", text: noteText(item, isTruthy(autoSend), isSwallowed) }],
            },
        });
        return deliveryResult(item, sent);
    } catch (error) {
        $.ui.log(`could not send heads-up #${item.n}: ${String(error)}`, { to: "debug" });
        return deliveryResult(item, { error });
    }
}

/**
 * Records what the plugin's `sessions` value says and pushes a new heads-up.
 * A write is always recorded; a read only matters when it shows an offer this copy has not handled
 * (one already on screen when the mod loaded, or a write it missed).
 */
async function capture($: EngineInterface, memory: Memory, value: unknown, isWrite: boolean): Promise<void> {
    const sessionId = await $.session.id();
    const read = readOffer(value, sessionId);
    const key = read.kind === "offer" ? offerKey(sessionId, read.offer) : undefined;
    if (!isWrite && (key === undefined || key === memory.lastOffer)) return;
    const records = parseRecords(await $.store.get("sessions"));
    const sentHere = new Map([...memory.numbers].filter(([k]) => memory.pending.has(k) || memory.swallowed.has(k)));
    const plan = planCapture(
        records,
        sessionId,
        value,
        memory.push,
        isWrite,
        sentHere,
        memory.lastNumber.get(sessionId) ?? 0
    );
    if (plan.kind === "new") {
        memory.lastNumber.set(sessionId, Math.max(plan.item.n, memory.lastNumber.get(sessionId) ?? 0));
        if (key !== undefined) memory.numbers.set(key, plan.item.n);
    }
    memory.lastOffer = key ?? memory.lastOffer;
    const record =
        plan.kind === "new" && plan.isToPush ?
            withItem(plan.record, await deliver($, plan.item, memory.isSwallowOn))
        :   plan.record;
    if (read.kind === "offer" && key !== undefined && isPushed(record, read.offer) && !memory.swallowed.has(key))
        memory.pending.add(key);
    if (!isWrite && plan.kind !== "new") return;
    await $.store.set("sessions", withRecord(records, record));
    if (plan.kind === "malformed" && !memory.hasWarnedShape) {
        memory.hasWarnedShape = true;
        $.ui.toast(
            `hup: skipped a "You should know" record it cannot read (${plan.why}); if heads-ups stop arriving, hup needs an update.`
        );
    }
}

/** Runs `capture` after any in flight, so read-modify-writes of our store never overlap; never throws, says once. */
async function serially($: EngineInterface, memory: Memory, value: unknown, isWrite: boolean): Promise<void> {
    const work = () => capture($, memory, value, isWrite);
    const run = memory.queue.then(work, work);
    memory.queue = run.catch(() => undefined);
    try {
        await run;
    } catch (err) {
        warn($, memory, "could not handle a heads-up", err);
    }
}

/** Every error goes to the debug log; the first one of this copy also gets a toast. */
function warn($: EngineInterface, memory: Memory, what: string, err: unknown): void {
    $.ui.log(`${what}: ${String(err)}`, { to: "debug" });
    if (memory.hasWarnedError) return;
    memory.hasWarnedError = true;
    $.ui.toast(`hup: ${what} (${String(err).slice(0, 120)}); details in the debug log (claude --debug).`);
}

export const register: Register = (on, options) => {
    const memory: Memory = {
        push: parsePush(options.push),
        isSwallowOn: parseSwallow(options.swallow),
        queue: Promise.resolve(),
        pending: new Set(),
        swallowed: new Set(),
        hasWarnedShape: false,
        hasWarnedError: false,
        lastNumber: new Map(),
        numbers: new Map(),
    };

    on("session.start", async ($, e, next) => {
        const started = await next(e);
        try {
            await $.tool.register({
                name: TOOL_NAME,
                description:
                    'Heads-ups the built-in "You should know" side agent showed the person in this session, ' +
                    "newest first: number, tag, line, explainer, and whether it was sent to the main agent. " +
                    "Pass `number` for one heads-up. The notes are written for the person and are sometimes wrong.",
                inputSchema: {
                    type: "object",
                    properties: {
                        number: {
                            type: "integer",
                            minimum: 1,
                            description: "The heads-up number, as the pushed note gave it. Omit for all.",
                        },
                    },
                    additionalProperties: false,
                },
            });
        } catch (err) {
            warn($, memory, "could not register its lookup tool", err);
        }
        return started;
    });

    // Our bookkeeping runs after the other plugin's call has settled; only a read of a delivered offer is rewritten.
    on("store.set", async ($, e, next) => {
        const done = await next(e);
        if (done.deny !== undefined || next.origin.plugin !== YSK_PLUGIN || e.key !== YSK_KEY) return done;
        await serially($, memory, e.value, true);
        return done;
    }).catch(($, e, next) => {
        $.ui.log(`${next.event} hook failed, the call passed through untouched: ${String(next.error)}`, {
            to: "debug",
        });
        return next(e);
    });

    on("store.get", async ($, e, next) => {
        const got = await next(e);
        if (next.origin.plugin !== YSK_PLUGIN || e.key !== YSK_KEY || got.deny !== undefined) return got;
        await serially($, memory, got.value, false);
        if (!memory.isSwallowOn) return got;
        try {
            // A delivered heads-up reads as gone: off the screen, and never counted as typed past unanswered.
            const sessionId = await $.session.id();
            const read = readOffer(got.value, sessionId);
            return read.kind === "offer" && memory.swallowed.has(offerKey(sessionId, read.offer)) ?
                    { value: withoutView(got.value, sessionId) }
                :   got;
        } catch (err) {
            // Shown rather than hidden: the person still sees it.
            warn($, memory, "could not hide a delivered heads-up", err);
            return got;
        }
    }).catch(($, e, next) => {
        $.ui.log(`${next.event} hook failed, the call passed through untouched: ${String(next.error)}`, {
            to: "debug",
        });
        return next(e);
    });

    // A pushed note rides the main loop's next request: only from then does Claude have it, so only then is it hidden.
    on("turn.step", async function* ($, e, next) {
        if (e.agentId === undefined) {
            for (const key of memory.pending) memory.swallowed.add(key);
            memory.pending.clear();
        }
        return yield* next(e);
    });

    on("tool.run", { tool: "mcp__hup__heads_up" }, async ($, e) => {
        const sessionId = await $.session.id();
        const record = recordOf(parseRecords(await $.store.get("sessions")), sessionId);
        const raw = (e as { number?: unknown }).number;
        const n = typeof raw === "number" && Number.isInteger(raw) ? raw : undefined;
        return { result: listText(record, await $.clock.now(), n) };
    });
};
