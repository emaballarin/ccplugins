#!/usr/bin/env bash
# Runs the built dm42sim with the given arguments; fails when /dm42:setup has not
# built it for this plugin version. A stable entry point: no state between calls.
set -euo pipefail
sim=$(bash "$(dirname "${BASH_SOURCE[0]}")/build.sh" --path)
exec "$sim" "$@"
