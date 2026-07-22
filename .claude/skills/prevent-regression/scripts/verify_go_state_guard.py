#!/usr/bin/env python3
"""Verify a staged Go state guard against isolated bad and good modules."""
from __future__ import annotations

import argparse
import ast
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _run(rule: Path, root: Path, source: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(rule), "--project-root", str(root), str(source)],
        cwd=root, capture_output=True, text=True, check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rule", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--bad", required=True)
    parser.add_argument("--good", required=True)
    args = parser.parse_args()
    rule = Path(args.rule).resolve()
    try:
        tree = ast.parse(rule.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError) as error:
        print(f"cannot read staged guard: {error}")
        return 1
    package_path = None
    for statement in tree.body:
        if (
            isinstance(statement, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "PACKAGE" for target in statement.targets)
        ):
            package_path = ast.literal_eval(statement.value)
            break
    if not isinstance(package_path, str) or not package_path:
        print("guard does not declare a literal PACKAGE identity")
        return 1
    with tempfile.TemporaryDirectory(dir=Path(args.project_root)) as temporary:
        base = Path(temporary)
        results = []
        for label, supplied in (("bad", args.bad), ("good", args.good)):
            host = base / label
            host.mkdir()
            (host / "go.mod").write_text(f"module {package_path}\n\ngo 1.22\n", encoding="utf-8")
            source = host / "state.go"
            shutil.copy2(supplied, source)
            results.append(_run(rule, host, source))
        bad, good = results
    print(f"BAD_RC={bad.returncode}, GOOD_RC={good.returncode}")
    if bad.returncode == 1 and good.returncode == 0:
        print("PASS: BAD_RC=1, GOOD_RC=0")
        return 0
    if bad.stdout or bad.stderr:
        print(f"BAD_OUTPUT:\n{bad.stdout}{bad.stderr}")
    if good.stdout or good.stderr:
        print(f"GOOD_OUTPUT:\n{good.stdout}{good.stderr}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
