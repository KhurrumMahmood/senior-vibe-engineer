#!/usr/bin/env python3
"""Measure fresh-process TypeScript fact-provider startup and analysis."""
from __future__ import annotations

import hashlib
import json
import platform
import resource
import sys
from pathlib import Path

from _lib.lang_adapter import FACT_CAPABILITIES, TypeScriptAdapter


def _rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if platform.system() == "Darwin" else value * 1024


def main(argv: list[str] | None = None) -> int:
    paths = [Path(value) for value in (argv if argv is not None else sys.argv[1:])]
    if not paths:
        raise SystemExit("at least one source path is required")
    adapter = TypeScriptAdapter()
    results = [
        adapter.analyze(
            path.read_text(encoding="utf-8"),
            path=path.name,
            capabilities=FACT_CAPABILITIES,
        )
        for path in paths
    ]
    encoded = json.dumps(
        [result.to_dict() for result in results],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    print(
        json.dumps(
            {
                "digest": hashlib.sha256(encoded).hexdigest(),
                "peak_rss_bytes": _rss_bytes(),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
