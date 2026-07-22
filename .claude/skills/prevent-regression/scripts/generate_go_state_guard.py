#!/usr/bin/env python3
"""Stage an exact-field Go bare-state guard from a reviewed targets artifact."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


class GuardError(ValueError):
    """Invalid targets or unavailable detector closure."""


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _load_targets(root: Path, supplied: str) -> dict:
    raw = Path(supplied)
    path = (raw if raw.is_absolute() else root / raw).resolve()
    if not _inside(root / "reports" / "extract-enum", path):
        raise GuardError("targets must stay beneath reports/extract-enum/")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GuardError(f"cannot read targets artifact: {error}") from error
    required = ("package_path", "carrier_type", "field", "proposed_type")
    if (
        payload.get("language") != "go"
        or payload.get("status") != "review_required"
        or any(not isinstance(payload.get(key), str) or not payload[key] for key in required)
    ):
        raise GuardError("targets do not contain reviewed Go state evidence")
    return payload


def _rule_text(package_path: str, carrier: str, field: str) -> str:
    return f'''#!/usr/bin/env python3
"""Reject bare string operations on {package_path}:{carrier}.{field}."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PACKAGE = {package_path!r}
CARRIER = {carrier!r}
FIELD = {field!r}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("targets", nargs="+")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    go = shutil.which("go")
    if not root.is_dir() or root.is_symlink() or not go:
        print("no_stringly_state: valid project root and Go >= 1.22 are required", file=sys.stderr)
        return 2
    version = subprocess.run([go, "version"], capture_output=True, text=True, check=False)
    match = re.search(r"\\bgo(\\d+)\\.(\\d+)", version.stdout or version.stderr)
    if version.returncode or not match or (int(match.group(1)), int(match.group(2))) < (1, 22):
        print("no_stringly_state: Go >= 1.22 is required", file=sys.stderr)
        return 2
    helper = Path(__file__).with_name("detect_go_state.go")
    violations = []
    for index, supplied in enumerate(args.targets):
        raw_target = Path(supplied)
        target = (raw_target if raw_target.is_absolute() else root / raw_target).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            print(f"no_stringly_state: target outside project root: {{supplied}}", file=sys.stderr)
            return 2
        output = root / "reports" / "implicit-state" / f".guard-{{os.getpid()}}-{{index}}.jsonl"
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = subprocess.run(
                [go, "run", str(helper), "--target", str(target), "--project-root", str(root),
                 "--output", str(output), "--go-executable", go,
                 "--guard-package", PACKAGE, "--guard-carrier", CARRIER, "--guard-field", FIELD],
                cwd=root, env={{**os.environ, "GOTOOLCHAIN": "local"}},
                capture_output=True, text=True, check=False,
            )
            if result.returncode:
                print(result.stderr.strip() or "no_stringly_state: analyzer failed", file=sys.stderr)
                return 2
            for line in output.read_text(encoding="utf-8").splitlines():
                record = json.loads(line)
                if record.get("classification") == "guard_violation":
                    violations.append(record)
        except (OSError, json.JSONDecodeError) as error:
            print(f"no_stringly_state: {{error}}", file=sys.stderr)
            return 2
        finally:
            output.unlink(missing_ok=True)
    for item in violations:
        print(f"{{item['file']}}:{{item['line']}}: bare {{item['literal']!r}} on {{CARRIER}}.{{FIELD}}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--detector-helper")
    args = parser.parse_args(argv)
    try:
        root = Path(args.project_root).resolve()
        if not root.is_dir() or root.is_symlink():
            raise GuardError(f"project root is not a directory: {args.project_root}")
        data = _load_targets(root, args.targets)
        raw_output = Path(args.output_root)
        output = (raw_output if raw_output.is_absolute() else root / raw_output).resolve()
        allowed = root / "reports" / "prevent-regression"
        if output == allowed or not _inside(allowed, output):
            raise GuardError("output root must stay beneath reports/prevent-regression/")
        helper = Path(args.detector_helper).resolve() if args.detector_helper else (
            Path(__file__).resolve().parents[1].parent
            / "find-implicit-state" / "scripts" / "detect_go_state.go"
        )
        if not helper.is_file():
            raise GuardError(
                "Go guard generation requires the find-implicit-state closure; "
                "load it beside prevent-regression or pass --detector-helper",
            )
        rule_dir = output / "scripts" / "lint"
        fixture_dir = output / "tests" / "lint"
        rule_dir.mkdir(parents=True, exist_ok=True)
        fixture_dir.mkdir(parents=True, exist_ok=True)
        rule = rule_dir / "no_stringly_state.py"
        rule.write_text(
            _rule_text(data["package_path"], data["carrier_type"], data["field"]),
            encoding="utf-8",
        )
        rule.chmod(0o755)
        shutil.copy2(helper, rule_dir / "detect_go_state.go")
        proposed = data["proposed_type"]
        field = data["field"]
        carrier = data["carrier_type"]
        (fixture_dir / "no_stringly_state_bad.go").write_text(
            f'''package fixture

type {proposed} string
type {carrier} struct {{ {field} {proposed} }}

func bad(value *{carrier}) bool {{
    value.{field} = "running"
    return value.{field} == "queued" || "done" == value.{field}
}}
''',
            encoding="utf-8",
        )
        (fixture_dir / "no_stringly_state_good.go").write_text(
            f'''package fixture

type {proposed} string
const {proposed}Queued {proposed} = "queued"
type {carrier} struct {{ {field} {proposed} }}

func good(value *{carrier}) bool {{ return value.{field} == {proposed}Queued }}
''',
            encoding="utf-8",
        )
        (output / "host-wiring.diff").write_text(
            "# Review and add this command to the host lint/CI path:\n"
            f"python3 scripts/lint/no_stringly_state.py --project-root . <owned {data['package_path']} package paths>\n",
            encoding="utf-8",
        )
    except (GuardError, OSError) as error:
        print(f"[generate_go_state_guard] ERROR: {error}", file=sys.stderr)
        return 2
    print(f"[generate_go_state_guard] staged {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
