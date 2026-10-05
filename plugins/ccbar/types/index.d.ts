/** The figures the band draws, gathered by background refreshers. */
export type CcbarSnapshot = {
    /** The main loop's model, prettified (`Opus 5.5`). */
    model: string | null;
    /** Extended thinking: null when off; on, the effort level when one is known. */
    thinking: { effort: string | null } | null;
    /** The working copy's repository; null outside one. */
    repo: CcbarRepo | null;
    /** The live context window; null before the first refresh. */
    context: CcbarContext | null;
    /** Tokens over every API response of the session, subagents included. */
    total: number | null;
    /** The account's rate-limit windows, as the last API response reported them. */
    limits: CcbarLimit[];
    /** The clock at the last tick, that reset countdowns are drawn against. */
    now: number;
};

/** Repository identity and working-tree change counts. */
export type CcbarRepo = {
    /** GitHub owner and name; null for a remote elsewhere or none. */
    owner: string | null;
    name: string | null;
    /** The branch, or `@<short sha>` when detached; empty when unknown. */
    branch: string;
    /** Inserted and deleted lines, staged and unstaged together; null when git could not read them. */
    changes: { added: number; removed: number } | null;
};

/** Context-window occupancy: exact totals, with the category split estimated. */
export type CcbarContext = {
    tokens: number | null;
    window: number;
    percent: number | null;
    /** Where auto-compaction runs, in tokens; null when it is off. */
    threshold: number | null;
    /** The `used` rows of the /context breakdown, in its order, by theme colour. */
    segments: { color: string; tokens: number }[];
};

/** One rate-limit window. */
export type CcbarLimit = {
    kind: string;
    percent: number;
    resetsAt: string | null;
};

declare module "claude-code" {
    interface PluginState {
        ccbar: { snap: Shaped<CcbarSnapshot> };
    }
}
