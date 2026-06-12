#!/usr/bin/env python3
"""Run the Path A parity battery against the current route.py and print results."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
ROUTE_PATH = REPO_ROOT / ".claude" / "skills" / "which-shape" / "scripts" / "route.py"

spec = importlib.util.spec_from_file_location("which_shape_route", ROUTE_PATH)
route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(route)

PROMPTS = [
    # fallback / probes
    "help me with the thing we discussed",
    "this is not a typo, the whole subsystem terminology is wrong",
    # one per shape, no re-added tokens
    "fix one-line typo in the status label",
    "this bug keeps coming back",
    "this failure keeps coming back; prevent the regression again",
    "onboard an unknown inherited repo and figure out what loop to run",
    "adapt this codebase",
    "this project feels messy and slow; identify the right cleanup loop",
    "what should we audit for a broad health sweep",
    "choose the durable architecture tradeoff and record an ADR",
    "add a new endpoint for the export workflow",
    "execute the approved refactor proposal",
    "rename the domain concept across the glossary and all surfaces",
    "the work is finished; run a closeout cleanup over the changed files",
    # re-added-token prompts (expected deltas after vocabulary restoration)
    "the app shows a crash on startup",
    "stop this regression from coming back",
    "build a new export page",
    "extract the service and split the module",
]

results = {}
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    for prompt in PROMPTS:
        rec = route.route(prompt, root)["recommendation"]
        results[prompt] = [rec["shape"], rec["score"], rec["confidence"]]

json.dump(results, sys.stdout, indent=2)
print()
