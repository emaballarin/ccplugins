#!/usr/bin/env bash
# Optional overnight driver. NOT a Claude Code hook — an ordinary process run by
# hand, in tmux or under nohup. Ctrl-C stops it.
#
#   tmux new -s ar './.ar/ar-loop.sh'
#
# Each pass is a fresh Claude Code session. Continuity comes from ./.ar/ar.jsonl
# being re-read as the first action of every invocation, not from context.
set -euo pipefail

STATE="./.ar/ar.jsonl"
MAX_PASSES="${AR_MAX_PASSES:-200}"

[[ -f "${STATE}" ]] || {
    echo "No ${STATE}. Run /ar:start first." >&2
    exit 1
}

for ((pass = 1; pass <= MAX_PASSES; pass++)); do
    echo "── ar pass ${pass} ── $(date '+%d/%m/%Y %H:%M') ──"
    claude -p "/ar:resume" || {
        echo "Session exited non-zero; stopping." >&2
        break
    }
    if tail -n 40 "${STATE}" | grep -q '"status":"stopped"'; then
        echo "Loop reported status:stopped — done."
        break
    fi
    sleep 2
done
