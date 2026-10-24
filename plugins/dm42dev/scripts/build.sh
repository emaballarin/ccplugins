#!/usr/bin/env bash
# Build dm42sim against SwissMicros' Free42 core, pinned, into a cache directory,
# then run the smoke test. A build counts as ready only once the smoke test passes.
#
#   build.sh            build if needed, smoke-test, print the binary's path
#   build.sh --rebuild  delete this pin's build directory first
#   build.sh --path     print the path of a ready binary, or fail; never builds
#
# Needs: bash, curl, tar, gzip, patch, make, gcc, g++, awk, od, which, python3 (3.14+),
# sha256sum; flock, when present, keeps two builds from colliding.
# Network on the first build. Location: $DM42SIM_HOME, else $XDG_CACHE_HOME/dm42,
# else ~/.cache/dm42.
set -euo pipefail

FORK_SHA=a7c705e476cfd6d83d7d8b90042999f386367813 # swissmicros/free42 "Version 3.3.10", 14/11/2025
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=${DM42SIM_HOME:-${XDG_CACHE_HOME:-$HOME/.cache}/dm42}
[[ $ROOT == /* ]] || ROOT=$PWD/$ROOT
PREFIX=$ROOT/${FORK_SHA:0:12}
JOBS=$(nproc 2>/dev/null || echo 4)
# This script and the emulator's sources decide whether to recompile; they and the
# smoke test decide readiness.
BUILT=$(cat "$HERE"/build.sh "$HERE"/sim/*.cc "$HERE"/sim/*.h | sha256sum | cut -c1-16)-${FORK_SHA:0:12}
READY=$BUILT-$(cat "$HERE"/smoke.42 "$HERE"/smoke.py | sha256sum | cut -c1-16)

stamp_is() { [[ -x $PREFIX/bin/dm42sim && $(cat "$PREFIX/bin/$1" 2>/dev/null) == "$2" ]]; }
ready() { stamp_is .ready "$READY"; }

case ${1:-} in
--path)
    ready || { echo "dm42sim is not built for this plugin version; run /dm42:setup" >&2; exit 1; }
    echo "$PREFIX/bin/dm42sim"
    exit 0
    ;;
--rebuild) rm -rf -- "$PREFIX" ;;
"") ;;
*) echo "usage: build.sh [--rebuild | --path]" >&2; exit 2 ;;
esac

mkdir -p "$PREFIX"
cd "$PREFIX"
if command -v flock >/dev/null; then
    exec 9>.lock
    flock 9
fi

if [[ ! -d src ]]; then
    echo "fetching swissmicros/free42 @ ${FORK_SHA:0:12}" >&2
    rm -rf src.tmp && mkdir src.tmp
    curl -fsSL "https://codeload.github.com/swissmicros/free42/tar.gz/$FORK_SHA" | tar xz -C src.tmp --strip-components=1
    mv src.tmp src
fi

# Intel decimal library, built with the fork's own script and patches. That script
# exits 0 even when make fails, so the library file is the only trustworthy signal.
if [[ ! -f lib/gcc111libbid.a ]]; then
    echo "building the Intel decimal library (log: $PREFIX/intel.log)" >&2
    (cd src/gtk && MAKEFLAGS=-j$JOBS sh ./build-intel-lib.sh) >intel.log 2>&1 || true
    [[ -f src/gtk/gcc111libbid.a ]] || { echo "Intel library build failed; see $PREFIX/intel.log" >&2; exit 1; }
    mkdir -p lib && cp src/gtk/gcc111libbid.a lib/
fi

if ! stamp_is .built "$BUILT"; then
    # The core as for the device (ARM), with decimal (BCD) arithmetic like the DM42n.
    FLAGS=(-O2 -fno-rtti -w -DARM -DBCD_MATH -DHAVE_SINCOS=1 -D_WCHAR_T_DEFINED
        -DDECIMAL_CALL_BY_REFERENCE=1 -DDECIMAL_GLOBAL_ROUNDING=1 -DDECIMAL_GLOBAL_ROUNDING_ACCESS_FUNCTIONS=1
        -DDECIMAL_GLOBAL_EXCEPTION_FLAGS=1 -DDECIMAL_GLOBAL_EXCEPTION_FLAGS_ACCESS_FUNCTIONS=1
        -Isrc/common -I"$HERE/sim")
    # Host-specific flags, as the fork's own gtk/Makefile sets them.
    [[ $(echo ab | od -x) == *6162* ]] && FLAGS+=(-DF42_BIG_ENDIAN -DBID_BIG_ENDIAN)
    case $(uname -m) in
    arm64 | aarch64) FLAGS+=(-fsigned-char -DBID_SIZE_LONG=8) ;;
    arm*) FLAGS+=(-fsigned-char -DBID_SIZE_LONG=4) ;;
    esac
    rm -rf obj bin && mkdir -p obj bin
    echo "compiling the core and dm42sim" >&2
    printf '%s\0' src/common/core_*.cc src/common/shell_spool.cc "$HERE"/sim/dm42sim.cc "$HERE"/sim/io.cc |
        xargs -0 -P "$JOBS" -I{} sh -c 'g++ "$@" -c "$0" -o "obj/$(basename "$0" .cc).o"' {} "${FLAGS[@]}"
    g++ -o bin/dm42sim obj/*.o lib/gcc111libbid.a
    echo "$BUILT" >bin/.built
fi

echo "smoke test" >&2
rm -f bin/.ready
python3 "$HERE/smoke.py" "$PREFIX/bin/dm42sim" >&2
echo "$READY" >bin/.ready
echo "$PREFIX/bin/dm42sim"
