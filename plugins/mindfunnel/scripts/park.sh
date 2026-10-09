#!/usr/bin/env bash
# park.sh [--replace] SCRATCHPAD SNAPSHOT [DROP_LIST]
#
# Copies SCRATCHPAD into SNAPSHOT (<project root>/.mf/park/<session-id>) and verifies the copy:
# every regular file by sha256 (SHA256SUMS), every symlink by its target (SYMLINKS). DROP_LIST
# names what to leave behind, one `./`-prefixed path per line: a file exactly, or a directory and
# everything under it when the line ends in `/`. A line that matches nothing is an error. Absent or
# empty, every file is kept. Empty directories and special files (FIFOs, sockets, devices) are not.
#
# An existing SNAPSHOT is a park never unparked: refused, with counts of its entries missing from
# the scratchpad (lost, say, to a reboot: /mf:unpark first), of those edited since and of entries
# new since. --replace takes the scratchpad's state instead. The snapshot is built beside its final place and moved there
# only once verified, so any failure before that leaves nothing behind and replaces nothing. Inside
# git, `.mf/park/` is made ignored through .git/info/exclude (local, never committed).
#
# Exit status: 0 parked; 1 failed, nothing left behind; 2 usage or a refused path; 3 parked, but git
# does not ignore `.mf/park/`; 4 SNAPSHOT already exists (the message counts what it holds that the
# scratchpad no longer does); 5 SNAPSHOT exists but is no readable snapshot (inspect it by hand);
# 6 the input needs fixing (a missing drop list, a drop line that matches nothing, a name with a
# newline, nothing to park). Needs bash, GNU tar and GNU coreutils.
set -euo pipefail
# Byte-order sorting and untranslated messages, whatever the caller's locale.
export LC_ALL=C
umask 077
trap 'exit 1' ERR

usage() { echo "usage: park.sh [--replace] SCRATCHPAD SNAPSHOT [DROP_LIST]" >&2; exit 2; }
REPLACE=
if [ "${1:-}" = "--replace" ]; then REPLACE=1; shift; fi
[ $# -ge 2 ] && [ $# -le 3 ] || usage
command -v sha256sum >/dev/null && command -v realpath >/dev/null || { echo "park.sh: needs GNU coreutils" >&2; exit 2; }
tar --version 2>/dev/null | grep -q 'GNU tar' || { echo "park.sh: needs GNU tar" >&2; exit 2; }
[ -d "$1" ] || { echo "park.sh: no scratchpad at $1" >&2; exit 2; }
SP=$(realpath -e -- "$1")
DEST=$(realpath -m -- "$2")
DROP=/dev/null
if [ $# -eq 3 ]; then
    [ -f "$3" ] || { echo "park.sh: no drop list at $3" >&2; exit 6; }
    DROP=$(realpath -e -- "$3")
fi
case "$DEST" in */.mf/park/?*) ;; *) echo "park.sh: SNAPSHOT must be <root>/.mf/park/<id>, got $DEST" >&2; exit 2 ;; esac
case "$DEST/" in "$SP"/*) echo "park.sh: SNAPSHOT lies inside SCRATCHPAD" >&2; exit 2 ;; esac
case "$SP/" in "$DEST"/*) echo "park.sh: SCRATCHPAD lies inside SNAPSHOT" >&2; exit 2 ;; esac

# Sets LINK to a symlink's target exactly: a $(...) around it would strip trailing newlines.
linkof() { LINK=$(readlink -n -- "$1"; printf x); LINK=${LINK%x}; }

if [ -e "$DEST" ] && [ -z "$REPLACE" ]; then
    for f in all.list keep.list; do
        [ -f "$DEST/$f" ] && [ -r "$DEST/$f" ] || { echo "park.sh: $DEST exists but is no readable snapshot (no $f); inspect it by hand" >&2; exit 5; }
    done
    [ -d "$DEST/files" ] || { echo "park.sh: $DEST exists but is no readable snapshot (no files/); inspect it by hand" >&2; exit 5; }
    # Each kept entry against the snapshot's own copy: never through a symlink, never opening
    # anything but a regular file.
    missing=0 edited=0
    while IFS= read -r p; do
        here=$SP/${p#./}
        if [ ! -e "$here" ] && [ ! -L "$here" ]; then
            missing=$((missing + 1))
        elif [ -L "$DEST/files/$p" ]; then
            linkof "$DEST/files/$p"
            want=$LINK
            [ -L "$here" ] && [ "$(realpath -m -- "${here%/*}")" = "${here%/*}" ] && linkof "$here" && [ "$LINK" = "$want" ] ||
                edited=$((edited + 1))
        else
            [ ! -L "$here" ] && [ -f "$here" ] && [ "$(realpath -m -- "$here")" = "$here" ] && cmp -s -- "$DEST/files/$p" "$here" ||
                edited=$((edited + 1))
        fi
    done < "$DEST/keep.list"
    new=$( (cd "$SP" && find . -mindepth 1 \( -type f -o -type l \) | sort) | comm -13 "$DEST/all.list" - | wc -l)
    echo "park.sh: $DEST already exists: a park never unparked ($missing of its entries missing from the scratchpad, $edited edited since, $new new since). Missing entries call for /mf:unpark first; to take the scratchpad's state instead, re-run with --replace" >&2
    exit 4
fi

if (cd "$SP" && find . -mindepth 1 -name $'*\n*' -print -quit | grep -q .); then
    echo "park.sh: a name under $SP contains a newline; rename it first" >&2
    exit 6
fi

WORK=$DEST.partial
rm -rf -- "$WORK"
trap 'status=$?; [ $status -eq 0 ] || rm -rf -- "$WORK"' EXIT
mkdir -p -- "$WORK/files"

(cd "$SP" && find . -mindepth 1 \( -type f -o -type l \) | LC_ALL=C sort) > "$WORK/all.list"
cp -- "$DROP" "$WORK/drop.list"
if ! awk 'FILENAME == ARGV[1] { if ($0 != "") d[++n] = $0; next }
     { kept = 1
       for (i = 1; i <= n; i++) { p = d[i]
         if ($0 == p || (substr(p, length(p)) == "/" && index($0, p) == 1)) { hit[i] = 1; kept = 0 } }
       if (kept) print }
     END { for (i = 1; i <= n; i++) if (!hit[i]) { print "park.sh: drop line matches nothing: " d[i] | "cat 1>&2"; bad = 1 }
           exit bad }' "$WORK/drop.list" "$WORK/all.list" > "$WORK/keep.list"; then
    exit 6
fi
[ -s "$WORK/all.list" ] || { echo "park.sh: nothing to park: the scratchpad holds no files" >&2; exit 6; }
[ -s "$WORK/keep.list" ] || { echo "park.sh: nothing to park: every entry was dropped" >&2; exit 6; }

tar -C "$SP" --verbatim-files-from --no-unquote -T "$WORK/keep.list" -cf - | tar -C "$WORK/files" -xpf -
(cd "$WORK/files" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 -r sha256sum) > "$WORK/SHA256SUMS"
(cd "$WORK/files" && find . -type l -print0 | LC_ALL=C sort -z |
    while IFS= read -r -d '' l; do linkof "$l"; printf '%s\0%s\0' "$l" "$LINK"; done) > "$WORK/SYMLINKS"

# The copy's records, checked against the source: an entry that differs or is missing fails here.
if [ -s "$WORK/SHA256SUMS" ]; then (cd "$SP" && sha256sum --quiet --strict -c "$WORK/SHA256SUMS"); fi
while IFS= read -r -d '' l && IFS= read -r -d '' t; do
    [ -L "$SP/$l" ] && linkof "$SP/$l" && [ "$LINK" = "$t" ] || { echo "$l: FAILED (symlink)" >&2; exit 1; }
done < "$WORK/SYMLINKS"
copied=$(find "$WORK/files" \( -type f -o -type l \) | wc -l)
listed=$(wc -l < "$WORK/keep.list")
[ "$copied" -eq "$listed" ] || { echo "park.sh: $listed entries kept but $copied copied" >&2; exit 1; }

if [ -e "$DEST" ]; then rm -rf -- "$DEST"; fi
mv -- "$WORK" "$DEST"
# From here the snapshot is in place: a failure leaves it unignored (exit 3), never removed.
trap 'exit 3' ERR
bytes=$(du -sb "$DEST/files" | cut -f1) || bytes="?"
echo "parked: $listed of $(wc -l < "$DEST/all.list") entries, $bytes bytes, verified, at $DEST"

ROOT=${DEST%/.mf/park/*}
exclude_park() {
    local exclude
    # --git-path answers relative to -C's directory, which this shell is not in: anchor it at ROOT.
    exclude=$(git -C "$ROOT" rev-parse --git-path info/exclude) || return 1
    case "$exclude" in /*) ;; *) exclude=$ROOT/$exclude ;; esac
    mkdir -p -- "${exclude%/*}" || return 1
    if ! grep -qxF '/.mf/park/' "$exclude" 2>/dev/null; then
        # A last line without its newline would swallow ours.
        if [ -s "$exclude" ] && [ -n "$(tail -c1 -- "$exclude")" ]; then printf '\n' >> "$exclude" || return 1; fi
        printf '/.mf/park/\n' >> "$exclude" || return 1
        echo "excluded: .mf/park/ added to $exclude"
    fi
    git -C "$ROOT" check-ignore -q .mf/park/x
}
if git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1 && ! git -C "$ROOT" check-ignore -q .mf/park/x; then
    exclude_park || {
        echo "park.sh: the snapshot is in place, but git does not ignore .mf/park/ (a negation rule, or an unwritable .git/info/exclude?); keep it out of commits by hand" >&2
        exit 3
    }
fi
