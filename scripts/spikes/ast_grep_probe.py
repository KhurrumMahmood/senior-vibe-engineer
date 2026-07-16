#!/usr/bin/env python3
"""Extract the pinned syntax facts through ast-grep's structured CLI output."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


KINDS = {
    "definitions": ("function_declaration", "enum_declaration", "interface_declaration", "variable_declarator"),
    "imports": ("import_statement",),
    "calls": ("call_expression",),
    "writes": ("assignment_expression",),
}


def normalize(family: str, value: str) -> str | None:
    if family == "definitions":
        patterns = (
            r"(?:function|enum|interface)\s+([A-Za-z_$][\w$]*)",
            r"^([A-Za-z_$][\w$]*)\s*(?::|=)",
        )
        for pattern in patterns:
            match = re.search(pattern, value)
            if match:
                return match.group(1)
    elif family == "imports":
        match = re.search(r"from\s+['\"]([^'\"]+)['\"]", value)
        if match:
            return match.group(1)
    elif family == "calls":
        match = re.match(r"\s*([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*\(", value)
        if match:
            return match.group(1)
    elif family == "writes":
        match = re.match(r"\s*([^=]+?)\s*=", value)
        if match and "==" not in value:
            return match.group(1).strip()
    return None


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: ast_grep_probe.py <ast-grep-bin> <corpus-root>", file=sys.stderr)
        return 2
    binary, root = Path(argv[1]).resolve(), Path(argv[2]).resolve()
    facts = {family: set() for family in KINDS}
    for family, kinds in KINDS.items():
        for kind in kinds:
            result = subprocess.run(
                [str(binary), "run", "--kind", kind, "--lang", "ts", "--json=compact", str(root / "src")],
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode not in (0, 1):
                print(result.stderr, file=sys.stderr)
                return 1
            rows = json.loads(result.stdout or "[]")
            for row in rows:
                value = normalize(family, row.get("text", ""))
                if value:
                    facts[family].add(value)
    print(json.dumps({key: sorted(value) for key, value in facts.items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
