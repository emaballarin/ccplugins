#!/usr/bin/env bash
# unpark.sh SNAPSHOT TARGET [--keep] [--beside]
#
# Restores a snapshot written by park.sh into the scratchpad TARGET. The snapshot is checked first:
# its files against its records. Then each entry is copied under a temporary name, renamed into
# place and compared with the snapshot, so an interrupted restore never leaves a partial file under
# a real name. An entry already at TARGET is never overwritten: identical, it passes; different, or
# reached through a symlinked directory, it is listed as FAILED. --beside restores the parked
# version of each such entry under a fresh TARGET/PARKED-<id>/ instead, beside the target's own. On a
# full pass the snapshot is popped: its MANIFEST.md (if any) is copied into TARGET as PARKED-<id>.md
# (a free name) and SNAPSHOT is deleted. --keep retains it.
#
# Exit status: 0 restored (and popped, unless --keep); 1 entries differ, listed, snapshot kept;
# 2 usage or a refused path; 3 restored and verified, but the pop failed; 4 no snapshot, or one that
# no longer matches its own records (inspect it by hand); 5 failed otherwise, nothing overwritten,
# snapshot kept.
set -euo pipefail
export LC_ALL=C
umask 077
trap 'exit 5' ERR

usage() { echo "usage: unpark.sh SNAPSHOT TARGET [--keep] [--beside]" >&2; exit 2; }
[ $# -ge 2 ] && [ $# -le 4 ] || usage
KEEP= BESIDE=
for opt in "${@:3}"; do
    case "$opt" in
        --keep) KEEP=1 ;;
        --beside) BESIDE=1 ;;
        *) echo "unpark.sh: unknown option $opt (only --keep, --beside)" >&2; exit 2 ;;
    esac
done
command -v sha256sum >/dev/null && command -v realpath >/dev/null || { echo "unpark.sh: needs GNU coreutils" >&2; exit 2; }
SNAP=$(realpath -m -- "$1")
TARGET=$(realpath -m -- "$2")
id=${SNAP##*/}
case "$SNAP" in */.mf/park/?*) ;; *) echo "unpark.sh: SNAPSHOT must be <root>/.mf/park/<id>, got $SNAP" >&2; exit 2 ;; esac
case "$id" in *.partial) echo "unpark.sh: $SNAP is a park killed midway, not a snapshot" >&2; exit 2 ;; esac
case "$TARGET/" in "$SNAP"/*) echo "unpark.sh: TARGET lies inside SNAPSHOT" >&2; exit 2 ;; esac
case "$SNAP/" in "$TARGET"/*) echo "unpark.sh: SNAPSHOT lies inside TARGET" >&2; exit 2 ;; esac
for f in SHA256SUMS SYMLINKS; do
    [ -f "$SNAP/$f" ] && [ -r "$SNAP/$f" ] || { echo "unpark.sh: no snapshot at $SNAP (no readable $f)" >&2; exit 4; }
done
[ -d "$SNAP/files" ] || { echo "unpark.sh: no snapshot at $SNAP (no files/)" >&2; exit 4; }

# Sets LINK to a symlink's target exactly: a $(...) around it would strip trailing newlines.
linkof() { LINK=$(readlink -n -- "$1"; printf x); LINK=${LINK%x}; }

# 1. The snapshot matches its records: nothing added, missing or changed since the park.
records=$(($(wc -l < "$SNAP/SHA256SUMS") + $(tr -cd '\0' < "$SNAP/SYMLINKS" | wc -c) / 2))
present=$(find "$SNAP/files" \( -type f -o -type l \) | wc -l)
[ "$present" -eq "$records" ] || { echo "unpark.sh: $SNAP holds $present entries but records $records; inspect it by hand" >&2; exit 4; }
if [ -s "$SNAP/SHA256SUMS" ] && ! (cd "$SNAP/files" && sha256sum --quiet --strict -c "$SNAP/SHA256SUMS"); then
    echo "unpark.sh: $SNAP no longer matches its records; inspect it by hand" >&2
    exit 4
fi
while IFS= read -r -d '' l && IFS= read -r -d '' t; do
    [ -L "$SNAP/files/$l" ] && linkof "$SNAP/files/$l" && [ "$LINK" = "$t" ] || {
        echo "unpark.sh: $SNAP/files/$l no longer matches its record; inspect it by hand" >&2
        exit 4
    }
done < "$SNAP/SYMLINKS"

# 2. Each entry into place and compared, or compared with what is already there.
mkdir -p -- "$TARGET"
# A path whose directories include a symlink would be written or read elsewhere.
direct() { [ "$(realpath -m -- "$1")" = "$1" ]; }
same() { # $1 path, $2 entry, $3 kind (f or l), $4 link target: the snapshot's entry is at $1
    if [ "$3" = f ]; then
        [ ! -L "$1" ] && [ -f "$1" ] && cmp -s -- "$SNAP/files/$2" "$1"
    else
        [ -L "$1" ] && linkof "$1" && [ "$LINK" = "$4" ]
    fi
}
put() { # $1 base directory, then as same: 0 when the entry is in place under $1, else 1 with WHY set
    local dest=$1/${2#./} dir tmp
    dir=${dest%/*}
    direct "$dir" || { WHY="a directory on its path is a symlink"; return 1; }
    if [ -e "$dest" ] || [ -L "$dest" ]; then
        same "$dest" "$2" "$3" "$4" && return 0
        WHY="differs"
        return 1
    fi
    mkdir -p -- "$dir" 2>/dev/null || { WHY="cannot create its directory"; return 1; }
    tmp=$(mktemp -u -p "$dir" .mf-unpark.XXXXXXXX) || { WHY="no temporary name"; return 1; }
    if ! { cp -a -- "$SNAP/files/$2" "$tmp" 2>/dev/null && mv -T -- "$tmp" "$dest"; }; then
        rm -f -- "$tmp"
        WHY="copy failed"
        return 1
    fi
    same "$dest" "$2" "$3" "$4" || { WHY="differs after the copy"; return 1; }
}
ASIDE=
aside() { # creates the fresh TARGET/PARKED-<id>[.n]/ that --beside restores into
    [ -n "$ASIDE" ] && return 0
    local n=2
    ASIDE=$TARGET/PARKED-$id
    while [ -e "$ASIDE" ] || [ -L "$ASIDE" ]; do ASIDE=$TARGET/PARKED-$id.$n; n=$((n + 1)); done
    mkdir -- "$ASIDE"
}
failed=0 besides=0
entry() { # $1 entry, $2 kind, $3 link target
    local why
    put "$TARGET" "$1" "$2" "${3-}" && return 0
    why=$WHY
    if [ -n "$BESIDE" ] && aside && put "$ASIDE" "$1" "$2" "${3-}"; then
        echo "$1: $why; the parked version is at ${ASIDE#"$TARGET"/}/${1#./}"
        besides=$((besides + 1))
        return 0
    fi
    echo "$1: FAILED ($why)"
    return 1
}
while IFS= read -r -d '' p; do
    entry "$p" f || failed=$((failed + 1))
done < <(cd "$SNAP/files" && find . -type f -print0 | LC_ALL=C sort -z)
while IFS= read -r -d '' l && IFS= read -r -d '' t; do
    entry "$l" l "$t" || failed=$((failed + 1))
done < "$SNAP/SYMLINKS"
if [ "$failed" -ne 0 ]; then
    echo "unpark.sh: the $failed entries above were left as they are; snapshot kept at $SNAP" >&2
    exit 1
fi
if [ -n "$ASIDE" ]; then
    echo "restored: $records entries into $TARGET, verified; $besides of them beside the entries already there, under ${ASIDE#"$TARGET"/}/"
else
    echo "restored: $records entries into $TARGET, verified"
fi

[ -z "$KEEP" ] || { echo "kept: $SNAP"; exit 0; }
pop() {
    if [ -f "$SNAP/MANIFEST.md" ]; then
        local record=$TARGET/PARKED-$id.md n=2
        while [ -e "$record" ] || [ -L "$record" ]; do record=$TARGET/PARKED-$id.$n.md; n=$((n + 1)); done
        cp -- "$SNAP/MANIFEST.md" "$record" || return 1
    fi
    # Renamed away first: a failure there leaves the snapshot whole, never half deleted.
    local gone=${SNAP%/*}/.$id.popped
    mv -T -- "$SNAP" "$gone" || return 1
    rm -rf -- "$gone" || { echo "unpark.sh: popped, but $gone is left over; delete it by hand" >&2; return 1; }
    # Tidy the now-empty parents; a non-empty one (another snapshot) stays.
    rmdir -- "${SNAP%/*}" 2>/dev/null && rmdir -- "${SNAP%/park/*}" 2>/dev/null
    return 0
}
pop || { echo "unpark.sh: restored and verified, but popping $SNAP failed; delete it by hand once satisfied" >&2; exit 3; }
echo "popped: $SNAP"
