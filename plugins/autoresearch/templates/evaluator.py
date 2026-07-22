#!/usr/bin/env python
"""LOCKED HARNESS — optional scorer for the ``{"pass", "score"}`` contract."""

import json
import sys


def evaluate() -> tuple[bool, float]:
    """Score the current run's artefacts; return ``(passed, score)``."""
    # --- fill in -------------------------------------------------------------
    # Read whatever the run left behind (metrics.json, safetensors checkpoints,
    # predictions, …) and reduce it to one number plus a correctness verdict.
    raise NotImplementedError("evaluator.py is a stub — populate it before starting the loop.")
    # -------------------------------------------------------------------------


def main() -> None:
    """Print one JSON object ``{"pass": bool, "score": number}`` on stdout."""
    passed, score = evaluate()
    print(json.dumps({"pass": passed, "score": score}))
    sys.exit(0)


if __name__ == "__main__":
    main()
