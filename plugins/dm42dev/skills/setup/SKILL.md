---
name: setup
description: Build dm42sim, the headless DM42 emulator — download SwissMicros' Free42 core at a pinned commit, compile it as for the device, and smoke-test it.
disable-model-invocation: true
allowed-tools: [Bash, Read]
---

# /dm42:setup — build the DM42 emulator

Builds `dm42sim` into `$DM42SIM_HOME`, else `$XDG_CACHE_HOME/dm42`, else `~/.cache/dm42`, one directory per pinned core. The first build downloads the core and compiles the Intel decimal library; later runs reuse both and finish quickly.

## Steps

1. **Check the tools**: `bash curl tar gzip patch make gcc g++ awk sed od which python3 sha256sum`, each with `command -v`, and Python 3.14 or later (the marketplace's floor): `python3 -c 'import sys; sys.exit(sys.version_info < (3, 14))'`. Done when all are present; otherwise name the missing ones with the package that provides them on this system, and stop — installing is the person's call.

2. **Build**: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/build.sh"`, in the background when the harness supports it. The script stops at the first failure; its last line on success is the binary's path, preceded by `smoke: OK`. Add `--rebuild` only when the person asks for a clean build. Done when the exit status is 0 and `bash "${CLAUDE_PLUGIN_ROOT}/scripts/build.sh" --path` prints the same path.

3. **On failure**, show the failing command's error and, for the decimal library, the tail of `intel.log` in the build directory. A smoke-test failure means this build does not behave like the device: report the failing checks, and keep the build unused.

4. **Report** the binary's path, the pinned core (`swissmicros/free42` 3.3.10, commit `a7c705e`), and the smoke result. `/dm42:rpn` finds the binary by itself.
