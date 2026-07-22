#!/usr/bin/env bash
# LOCKED HARNESS — optional correctness gate. Populate once, then never edit.
#
# Exit non-zero to force status=checks_failed, which blocks a keep no matter how
# good the metric looks. This is what stops the loop from trading correctness
# for score.
set -euo pipefail

# --- fill in -----------------------------------------------------------------
ruff check src/
python -O -m pytest -q
# -----------------------------------------------------------------------------
