/** The band's layout as plain data: coloured runs, grouped, packed into rows under a width. */
import type { CcbarSnapshot } from "../types";
import { contextPieces, formatCountdown, formatTokens, layBar, limitLabel } from "./lib";

/** A stretch of text in one style; colours are theme keys. */
export type Run = { text: string; color?: string; bg?: string; bold?: boolean };

/** Runs that stay together on one row. */
export type Group = Run[];

/** What sits between two groups on a row. */
export const SEPARATOR: Run = { text: "  ·  ", color: "subtle" };

/** The closer join inside a group of figures of one kind: the rate-limit windows (Session, Weekly, Spend). */
export const TIGHT: Run = { text: " · ", color: "subtle" };

/** Theme keys by meaning: one colour, one sense. */
export const COLOR = {
    identity: "claude",
    mode: "permission",
    label: "inactive",
    added: "diffAddedWord",
    removed: "diffRemovedWord",
} as const;

const BAR = { fill: "inactive", track: "userMessageBackground", reserve: "subtle" };

/** Load against a cap: green below 60%, yellow below 85%, red from there. */
export function loadColor(percent: number): string {
    if (percent >= 85) return "error";
    if (percent >= 60) return "warning";
    return "success";
}

/** Columns a run list takes; every glyph the band draws is one cell wide. */
export function width(runs: Run[]): number {
    return runs.reduce((sum, r) => sum + [...r.text].length, 0);
}

/**
 * Packs groups into rows no wider than `columns`, `SEPARATOR` between neighbours on a row. Rows after
 * the first start `indent` columns in, and have that much less room.
 */
export function pack(groups: Group[], columns: number, indent = 0): Run[][] {
    const rows: Run[][] = [];
    let row: Run[] = [];
    for (const group of groups) {
        const room = rows.length === 0 ? columns : columns - indent;
        const joined = row.length > 0 ? [...row, SEPARATOR, ...group] : group;
        if (row.length > 0 && width(joined) > room) {
            rows.push(row);
            row = [...group];
        } else {
            row = joined;
        }
    }
    if (row.length > 0) rows.push(row);
    return indent > 0 ? rows.map((r, i) => (i === 0 ? r : [{ text: " ".repeat(indent) }, ...r])) : rows;
}

/** The band's groups in reading order: model, repository, context, tokens, then the rate limits together. */
export function groups(s: CcbarSnapshot, barWidth: number): Group[] {
    const out: Group[] = [];
    if (s.model) {
        const effort = s.thinking?.effort;
        out.push([
            { text: s.model, color: COLOR.identity, bold: true },
            ...(effort ? [{ text: ` ${effort}`, color: COLOR.mode }] : []),
        ]);
    }
    if (s.repo) {
        const r = s.repo;
        const group: Run[] = [];
        if (r.owner && r.name) group.push({ text: `${r.owner}/`, color: COLOR.label }, { text: r.name });
        if (r.branch) group.push({ text: group.length > 0 ? " ⎇ " : "⎇ ", color: COLOR.label }, { text: r.branch });
        // Drawn whenever git could read the tree: a quiet (+0 −0) says it is clean.
        if (r.changes) {
            const { added, removed } = r.changes;
            group.push(
                { text: group.length > 0 ? " (" : "(", color: COLOR.label },
                { text: `+${added}`, color: added > 0 ? COLOR.added : COLOR.label },
                { text: " ", color: COLOR.label },
                { text: `−${removed}`, color: removed > 0 ? COLOR.removed : COLOR.label },
                { text: ")", color: COLOR.label }
            );
        }
        if (group.length > 0) out.push(group);
    }
    if (s.context) {
        const c = s.context;
        const used = c.tokens;
        const cells = layBar(contextPieces(c, barWidth, BAR), barWidth);
        const group: Run[] = cells.map((cell) => ({ text: cell.ch, color: cell.fg, bg: cell.bg }));
        group.push(
            { text: ` ${used === null ? "–" : formatTokens(used)}` },
            { text: `/${formatTokens(c.window)}`, color: COLOR.label }
        );
        if (c.percent !== null && used !== null) {
            const load = (used / (c.threshold ?? c.window)) * 100;
            group.push(
                { text: " (", color: COLOR.label },
                { text: `${c.percent}%`, color: loadColor(load) },
                { text: ")", color: COLOR.label }
            );
        }
        out.push(group);
    }
    if (s.total) out.push([{ text: "Tok Σ ", color: COLOR.label }, { text: formatTokens(s.total) }]);
    // The rate-limit windows wrap as one group: a row never splits Session from Weekly.
    const limits: Run[] = [];
    for (const l of s.limits) {
        if (limits.length > 0) limits.push(TIGHT);
        limits.push(
            { text: `${limitLabel(l.kind)} `, color: COLOR.label },
            { text: `${l.percent}%`, color: loadColor(l.percent) }
        );
        if (l.resetsAt && s.now) {
            limits.push({ text: ` (${formatCountdown(Date.parse(l.resetsAt) - s.now)})`, color: COLOR.label });
        }
    }
    if (limits.length > 0) out.push(limits);
    return out;
}

/**
 * Rows for `columns`: one row with a 24-cell bar, else one with 16, else wrapped rows with up to 16 (fewer
 * below 36 columns). Wrapped rows hang under the first row's second segment, unless the indent would cost a
 * row or leave a group too wide for the room beside it: then the whole band wraps flush left.
 */
export function layout(s: CcbarSnapshot, columns: number): Run[][] {
    for (const bar of [24, 16]) {
        const rows = pack(groups(s, bar), columns);
        if (rows.length <= 1) return rows;
    }
    const wrapped = groups(s, Math.max(6, Math.min(16, columns - 20)));
    const first = wrapped[0];
    const flat = pack(wrapped, columns);
    const hanging = first ? pack(wrapped, columns, width(first) + width([SEPARATOR])) : [];
    const fits = hanging.length > 0 && hanging.length <= flat.length && hanging.every((r) => width(r) <= columns);
    return fits ? hanging : flat;
}
