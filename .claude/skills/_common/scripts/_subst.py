#!/usr/bin/env python3
"""Substitute `{{key}}` placeholders in a scout brief.

Used by `dispatch_scout.sh` — kept separate because shell parameter
substitution is brittle for multi-line values (e.g., a 50-line
`{{declarations}}` block passed from the chunk map).

Usage:
    _subst.py <template> <output> [<key>=<value> ...]

Reads <template>, replaces every literal `{{key}}` with its value (values
come from positional key=value args OR from env vars named SCOUT_<KEY>),
writes the result to <output>. Unknown placeholders left intact — the
orchestrator sees them in the brief and can detect incomplete argument
lists.
"""
from __future__ import annotations

import os
import re
import sys


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: _subst.py <template> <output> [key=value ...]", file=sys.stderr)
        return 2

    template_path = argv[1]
    output_path = argv[2]
    pairs = argv[3:]

    subs: dict[str, str] = {}
    for raw in pairs:
        if "=" not in raw:
            print(f"_subst: malformed arg (need key=value): {raw!r}", file=sys.stderr)
            return 2
        key, _, value = raw.partition("=")
        subs[key] = value

    for env_key, env_val in os.environ.items():
        if env_key.startswith("SCOUT_"):
            subs.setdefault(env_key[len("SCOUT_"):].lower(), env_val)

    with open(template_path, "r", encoding="utf-8") as fh:
        body = fh.read()

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        return subs.get(name, match.group(0))

    body = re.sub(r"\{\{([a-zA-Z0-9_]+)\}\}", repl, body)

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(body)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
