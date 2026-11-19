/** The input of hup's lookup tool: one heads-up by `number`, or all of this session's when omitted. */
export type HeadsUpLookupInput = { number?: number };

// hup's own tool: the laid MCP typings list it only if it was registered when they were written.
declare module "claude-code" {
    interface McpToolInputs {
        mcp__hup__heads_up: HeadsUpLookupInput;
    }
}
