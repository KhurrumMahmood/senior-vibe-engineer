#!/usr/bin/env python3
"""Prove a staged exact PHP enum-property guard on disposable project copies."""
from __future__ import annotations

import argparse
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _library() -> Any:
    local = Path(__file__).with_name("php_proposal_evidence.py")
    canonical = Path(__file__).resolve().parents[2] / "_php-proposal/php_proposal_evidence.py"
    path = local if local.is_file() else canonical
    spec = importlib.util.spec_from_file_location("php_proposal_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("php_proposal_evidence.py is missing from the copied closure")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


E = _library()


def _invoke(php: str, guard: Path, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [php, str(guard), str(root)], cwd=root, capture_output=True, text=True,
        check=False, timeout=60,
    )


def _seed(root: Path, metadata: dict[str, Any]) -> Path:
    selection, authority = metadata["selection"], metadata["authority"]
    source = E.safe_path(root, selection["authority_file"], "regression authority")
    text = source.read_text(encoding="utf-8")
    enum_short = selection["enum_type"].rsplit("\\", 1)[-1]
    field = authority["field"]
    pattern = re.compile(
        rf"(?m)^(?P<indent>\s*(?:public|protected|private)\s+){re.escape(enum_short)}"
        rf"(?P<middle>\s+\${re.escape(field)}\s*=\s*){re.escape(enum_short)}::[A-Za-z_][A-Za-z0-9_]*(?P<tail>\s*;)"
    )
    changed, count = pattern.subn(r"\g<indent>string\g<middle>'queued'\g<tail>", text)
    if count != 1:
        raise E.EvidenceError("regression_unseedable", "could not seed exactly one typed-field regression")
    source.write_text(changed, encoding="utf-8")
    return source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("project-root", "stage", "php", "composer"):
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()
    stage = E.output_dir(root, args.stage, "prevent-regression")
    report = stage / "verification.json"
    try:
        metadata = E.load_json(stage / "authority.json", "guard authority")
        guard = stage / "guard/exact_field_type_guard.php"
        if (
            metadata.get("schema_version") != "php-state-guard-v1"
            or metadata.get("status") != "staged"
            or not guard.is_file()
            or E.sha256(guard) != metadata.get("guard_sha256")
        ):
            raise E.EvidenceError("stage_tampered", "staged PHP guard closure is invalid")
        before = E.source_hashes(root)
        native = E.native_checks(root, metadata, metadata["native"], args.php, args.composer)
        php_path = native["tools"]["php"]["path"]
        clean = _invoke(php_path, guard, root)
        if clean.returncode != 0 or clean.stdout.strip() != "php-state-guard-ok":
            raise E.EvidenceError("guard_clean_failed", clean.stderr or clean.stdout)
        with tempfile.TemporaryDirectory() as temporary:
            regression = Path(temporary) / "host"
            shutil.copytree(
                root, regression, symlinks=True,
                ignore=shutil.ignore_patterns(".git", "reports", "reviews"),
            )
            changed = _seed(regression, metadata)
            lint = subprocess.run(
                [php_path, "-l", str(changed)], cwd=regression, capture_output=True,
                text=True, check=False, timeout=60,
            )
            caught = _invoke(php_path, guard, regression)
            if lint.returncode != 0:
                raise E.EvidenceError("regression_not_buildable", lint.stderr or lint.stdout)
            if caught.returncode != 1 or metadata["selection"]["enum_type"] not in caught.stderr:
                raise E.EvidenceError("guard_did_not_fire", caught.stderr or caught.stdout)
        if E.source_hashes(root) != before:
            raise E.EvidenceError("source_mutated", "guard verification mutated host source")
        payload = {
            "schema_version": "php-state-guard-verification-v1", "language": "php",
            "status": "complete", "outcome": "guard_proved", "native": native,
            "clean_guard_passed": True,
            "seeded_regression": {"without_guard_passed": True, "caught_by_guard": True},
            "source_preserved": True, "nonclaims": metadata["nonclaims"],
        }
        E.write_json(report, payload)
    except (
        OSError,
        AttributeError,
        UnicodeError,
        KeyError,
        TypeError,
        ValueError,
        subprocess.TimeoutExpired,
    ) as error:
        E.write_json(report, {
            "schema_version": "php-state-guard-verification-v1", "language": "php",
            "status": "failed", "outcome": "unproved",
            "failure_kind": getattr(error, "kind", "verification_failed"), "message": str(error),
        })
        print(f"[verify_php_state_guard] ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
