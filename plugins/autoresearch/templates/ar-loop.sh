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
    # Halt when the active segment (lines after the last config header) holds a
    # stopped sentinel, wherever in it: a pass in flight when /ar:stop lands can
    # append its result after the sentinel, and a new segment clears an old one.
    if awk '/"config"[[:space:]]*:/ { s = 0 }
            /"status"[[:space:]]*:[[:space:]]*"stopped"/ { s = 1 }
            END { exit !s }' "${STATE}"; then
        echo "Loop reported status:stopped — done."
        break
    fi
    sleep 2
done
