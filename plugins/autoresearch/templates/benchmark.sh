#!/usr/bin/env bash
# LOCKED HARNESS — the measuring instrument. Populate once, then never edit.
#
# Contract: emit exactly one primary METRIC line on stdout, as
#   METRIC <name>=<number>
# Secondary metrics may follow on their own METRIC lines; once introduced, a
# secondary metric must appear on every subsequent run.
#
# Honour ${AR_SEED} so borderline candidates can be re-run across seeds.
#
# Execution is deferred: long jobs belong on the cluster, not inside the agent.
# If the run is long, print the command and exit rather than launching it.
set -euo pipefail

SEED="${AR_SEED:-0}"

# --- fill in -----------------------------------------------------------------
# Example shape:
#   python -O -m src.train --seed "${SEED}" --config ./config.yaml >run.log 2>&1
#   VALUE="$(grep -oP 'final val_loss: \K[0-9.]+' run.log | tail -1)"
#   echo "METRIC val_loss=${VALUE}"
# -----------------------------------------------------------------------------

echo "METRIC val_loss=NaN  # TODO: wire to real output (seed=${SEED})" >&2
echo "benchmark.sh is a stub — populate it before starting the loop." >&2
exit 1
