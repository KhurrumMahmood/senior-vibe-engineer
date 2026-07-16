#!/usr/bin/env python3
"""Machine-check the verified WP4 dependency before WP5 parser work starts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
TRACKER = Path("ai-docs/plans/portable-skill-ecosystem-completion.md")
FINAL_REPORT = Path(
    "reports/portable-skill-ecosystem-completion/WP4/clean-reverification.md"
)
VERIFIED_REVISION = "d1a6316f0c57abc5e2162c477d6d56f51165cf14"
VERIFIED_TREE = "0ab795ec7b6b19dfa987393530404f7e17e98bb6"
REPORT_COMMIT = "f9ef09acb853fa6fcba400d6bd1d3131e04a7f6c"
VERIFIED_SOURCE_TREE_SHA256 = (
    "92aca126917a35a078f4b3d40f72de46c2e707a4580def146094425cd4cc70f0"
)
VERIFIED_STABLE_RESULT_SHA256 = (
    "a8c3596589629e79af1a601ae14c620ddb0d0127887225245c30d543311e7674"
)

# Byte hashes prevent a later edit from silently weakening the independent evidence.
EVIDENCE_SHA256 = {
    FINAL_REPORT: "2008a818b90c627020de556283ac5e223902628b67f1ad88c0a6c935c9b0817f",
    Path("reports/portable-skill-ecosystem-completion/WP4/darwin-arm64.json"):
        "9ed3d76ee0be2f77873f15ef06f9d6bfb05d98e630aa03596460b2fd94cce039",
    Path("reports/portable-skill-ecosystem-completion/WP4/linux-x86_64.json"):
        "8a903bb629b0c27421362fb00faf4a5bfd97fde438ffcacea5f4194ea67c741d",
    Path("reports/portable-skill-ecosystem-completion/WP4/platform-matrix.json"):
        "3d6a39aa395ab4c97d64e69448b986427787547c8f589d23cb160f7f2935ad55",
    Path("reports/portable-skill-ecosystem-completion/WP4/adversarial-comparison.txt"):
        "732a4c20152f3450c976fb8df3f724e65b09060a23107576193528fd0c7c53ec",
}

# Fresh exact-revision verifier artifacts were temporary; their hashes remain bound
# by the immutable final verifier report.
FRESH_VERIFIER_HASHES = {
    "fresh D3 rerun": "5c00dfb65530f4682ba038c6cdee59ca230488b9e09f2a25dd22a0225ff3abcd",
    "fresh Darwin report": "43d692aef80842deedbcb943134d0af5b8d93b640245968d66f5741e9a0261b5",
    "fresh Linux report": "20912a253093dfdd4d388f9e4e0b333f2e4bedee36221f51169dc600a7469af1",
    "forward matrix": "d49b676842e747be253e287cb2b67db19a9cdcb33e7cdd92baae43e8e76c48e5",
    "reverse matrix": "d49b676842e747be253e287cb2b67db19a9cdcb33e7cdd92baae43e8e76c48e5",
    "adversarial replay": "35ac05fd23115279fc8f0bab38a6d34f84dd905e36950d7c5122f44e34056319",
}

SUBSTRATE_PATHS = (
    "scripts/analysis_fact_benchmark.py",
    "scripts/analysis_fact_cold_probe.py",
    "requirements.txt",
    "scripts/_lib/lang_adapter",
    "tests/fixtures/analysis_facts",
    "tests/fixtures/analysis_portfolio_spike",
    "tests/test_analysis_facts.py",
    "tests/test_lang_adapter.py",
    "tests/test_omnibus_language_adapters.py",
    "ai-docs/specs/portable-analysis-substrate.md",
)
DARWIN_REPORT = Path("reports/portable-skill-ecosystem-completion/WP4/darwin-arm64.json")
LINUX_REPORT = Path("reports/portable-skill-ecosystem-completion/WP4/linux-x86_64.json")
MATRIX_REPORT = Path("reports/portable-skill-ecosystem-completion/WP4/platform-matrix.json")
CONTRACT_TESTS = (
    "tests/test_analysis_facts.py",
    "tests/test_lang_adapter.py",
    "tests/test_omnibus_language_adapters.py",
)
DEPENDENCY_RECORD_PATHS = (str(TRACKER), *(str(path) for path in EVIDENCE_SHA256))


class GateFailure(RuntimeError):
    """A WP4 prerequisite is absent, stale, dirty, mismatched, or weaker."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(argv: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            argv,
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise GateFailure(f"command timed out: {' '.join(argv)}") from exc
    if check and result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        raise GateFailure(f"command failed ({result.returncode}): {' '.join(argv)}\n{detail}")
    return result


def _git(*args: str) -> str:
    return _run(["git", *args]).stdout.strip()


def validate_tracker(text: str) -> None:
    rows = [line for line in text.splitlines() if line.startswith("| WP4 ")]
    if len(rows) != 1:
        raise GateFailure("authoritative tracker must contain exactly one WP4 row")
    cells = [cell.strip() for cell in rows[0].strip("|").split("|")]
    if len(cells) != 7:
        raise GateFailure("authoritative WP4 tracker row has an unexpected shape")
    work_package, status, _owner, dependency, criteria, evidence, action = cells
    if work_package != "WP4 Multi-language analysis substrate" or status != "verified":
        raise GateFailure("authoritative tracker does not mark WP4 verified")
    if dependency != "WP1" or criteria != "AC-4.1–AC-4.6":
        raise GateFailure("authoritative WP4 dependency/acceptance range is weaker or changed")
    if str(FINAL_REPORT) not in evidence:
        raise GateFailure("authoritative WP4 row does not link the final clean verifier")
    required_action = (
        "passed AC-4.1–AC-4.6 at exact clean revision `d1a6316`"
    )
    if required_action not in action or "parser-backed WP5 work is dependency-ready" not in action:
        raise GateFailure("authoritative WP4 row lacks the exact clean-revision PASS handoff")


def validate_final_report(text: str, digest: str) -> None:
    if digest != EVIDENCE_SHA256[FINAL_REPORT]:
        raise GateFailure("WP4 final clean verifier report hash is stale or mismatched")
    required = (
        "# WP4 clean re-verification — PASS",
        VERIFIED_REVISION,
        f"tree\n`{VERIFIED_TREE}`",
        "AC-4.1 through AC-4.6 pass independently",
        "549/549",
        "Missing or ambiguous evidence: **none**.",
        "Unsupported claims found: **none**.",
    )
    for marker in required:
        if marker not in text:
            raise GateFailure(f"WP4 final verifier report is missing: {marker}")
    for label, expected in FRESH_VERIFIER_HASHES.items():
        if f"| {label} | `{expected}` |" not in text:
            raise GateFailure(f"WP4 final verifier does not bind {label}")


def validate_platform_matrix_payload(matrix: dict[str, Any]) -> None:
    expected_executions = {
        "Darwin-arm64": ("3.11.10", "0.26.0", "1.12.5"),
        "Linux-x86_64": ("3.11.15", "0.26.0", "1.12.5"),
    }
    if matrix.get("required_platforms") != sorted(expected_executions):
        raise GateFailure("WP4 platform matrix is missing a required platform")
    if matrix.get("passed") is not True or matrix.get("cross_platform_deterministic") is not True:
        raise GateFailure("WP4 platform matrix is not a deterministic PASS")
    if matrix.get("source_tree_sha256") != VERIFIED_SOURCE_TREE_SHA256:
        raise GateFailure("WP4 platform matrix source hash does not match verified substrate")
    if matrix.get("stable_result_sha256") != VERIFIED_STABLE_RESULT_SHA256:
        raise GateFailure("WP4 platform matrix stable result is stale")
    for key, versions in expected_executions.items():
        row = matrix.get("executions", {}).get(key, {})
        if tuple(row.get(name) for name in ("python", "tree_sitter", "tree_sitter_language_pack")) != versions:
            raise GateFailure(f"WP4 platform/tool evidence is weaker or mismatched: {key}")
        if row.get("passed") is not True:
            raise GateFailure(f"WP4 platform evidence is not passing: {key}")


def validate_platform_matrix(root: Path = REPO_ROOT) -> dict[str, Any]:
    for relative, expected in EVIDENCE_SHA256.items():
        path = root / relative
        if not path.is_file() or _sha256(path) != expected:
            raise GateFailure(f"WP4 evidence is absent or hash-mismatched: {relative}")
    matrix = json.loads((root / MATRIX_REPORT).read_text(encoding="utf-8"))
    validate_platform_matrix_payload(matrix)
    return matrix


def validate_repository_state() -> str:
    if _git("rev-parse", "--verify", f"{VERIFIED_REVISION}^{{commit}}") != VERIFIED_REVISION:
        raise GateFailure("verified WP4 substrate revision is absent")
    if _git("rev-parse", f"{VERIFIED_REVISION}^{{tree}}") != VERIFIED_TREE:
        raise GateFailure("verified WP4 substrate tree is mismatched")
    head = _git("rev-parse", "HEAD^{commit}")
    if _run(["git", "merge-base", "--is-ancestor", VERIFIED_REVISION, head], check=False).returncode:
        raise GateFailure("current HEAD does not descend from verified WP4 substrate")
    report_tip = _git("log", "-1", "--format=%H", "--", str(FINAL_REPORT))
    if report_tip != REPORT_COMMIT:
        raise GateFailure("final WP4 verifier is not the bound report commit")
    dependency_dirty = _git(
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        *DEPENDENCY_RECORD_PATHS,
    )
    if dependency_dirty:
        raise GateFailure(f"WP4 tracker/evidence is dirty:\n{dependency_dirty}")
    dirty = _git("status", "--porcelain=v1", "--untracked-files=all", "--", *SUBSTRATE_PATHS)
    if dirty:
        raise GateFailure(f"WP4 substrate/contracts are dirty:\n{dirty}")
    drift = _git("diff", "--name-only", f"{VERIFIED_REVISION}..{head}", "--", *SUBSTRATE_PATHS)
    if drift:
        raise GateFailure(f"WP4 substrate/contracts changed after verification:\n{drift}")
    return head


def _command_record(argv: list[str]) -> dict[str, Any]:
    result = _run(argv)
    return {"argv": argv, "exit_code": result.returncode, "stdout": result.stdout.strip()}


def rerun_contracts(
    head: str, matrix: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    python = str(REPO_ROOT / ".venv/bin/python")
    if Path(sys.executable).resolve() != Path(python).resolve():
        raise GateFailure("entry gate must run with .venv/bin/python")
    commands = [
        _command_record([
            python,
            "-m",
            "pytest",
            "--override-ini",
            "addopts=",
            "-q",
            "-p",
            "no:cacheprovider",
            *CONTRACT_TESTS,
        ])
    ]
    with tempfile.TemporaryDirectory(prefix="wp5-wp4-entry-") as directory:
        live_path = Path(directory) / "live-platform.json"
        commands.append(_command_record([
            python,
            "scripts/analysis_fact_benchmark.py",
            "--source-revision",
            head,
            "--output",
            str(live_path),
        ]))
        live = json.loads(live_path.read_text(encoding="utf-8"))
        if live.get("passed") is not True or live.get("violations") != []:
            raise GateFailure("current-platform WP4 budget rerun did not pass")
        if live.get("source_tree_sha256") != VERIFIED_SOURCE_TREE_SHA256:
            raise GateFailure("current-platform rerun does not use verified WP4 substrate")
        if live.get("stable_result_sha256") != VERIFIED_STABLE_RESULT_SHA256:
            raise GateFailure("current-platform facts/goldens differ from verified WP4 output")
        execution = live.get("platform_execution", {})
        platform_key = execution.get("platform_key")
        expected_execution = matrix["executions"].get(platform_key)
        if expected_execution is None:
            raise GateFailure(f"current platform is outside verified WP4 matrix: {platform_key}")
        version_fields = ("python", "tree_sitter", "tree_sitter_language_pack")
        if any(execution.get(field) != expected_execution.get(field) for field in version_fields):
            raise GateFailure("current runtime tools differ from the verified WP4 matrix")
        rebuilt_path = Path(directory) / "rebuilt-matrix.json"
        commands.append(_command_record([
            python,
            "scripts/analysis_fact_benchmark.py",
            "--compare-platform-reports",
            str(REPO_ROOT / DARWIN_REPORT),
            str(REPO_ROOT / LINUX_REPORT),
            "--output",
            str(rebuilt_path),
        ]))
        if rebuilt_path.read_bytes() != (REPO_ROOT / MATRIX_REPORT).read_bytes():
            raise GateFailure("recomputed WP4 platform matrix differs from committed evidence")
        live_summary = {
            "report_sha256": _sha256(live_path),
            "platform_execution": live["platform_execution"],
            "source_tree_sha256": live["source_tree_sha256"],
            "stable_result_sha256": live["stable_result_sha256"],
            "passed": True,
        }
    return commands, live_summary


def check(*, preflight_only: bool = False) -> dict[str, Any]:
    tracker_text = (REPO_ROOT / TRACKER).read_text(encoding="utf-8")
    report_path = REPO_ROOT / FINAL_REPORT
    report_text = report_path.read_text(encoding="utf-8")
    validate_tracker(tracker_text)
    validate_final_report(report_text, _sha256(report_path))
    matrix = validate_platform_matrix()
    head = validate_repository_state()
    result: dict[str, Any] = {
        "schema_version": 1,
        "gate": "WP5-IM-12-WP4-entry",
        "verified_revision": VERIFIED_REVISION,
        "verified_tree": VERIFIED_TREE,
        "current_head": head,
        "final_verifier": str(FINAL_REPORT),
        "evidence_sha256": {str(path): digest for path, digest in EVIDENCE_SHA256.items()},
        "platform_matrix": matrix,
        "preflight_only": preflight_only,
        "entry_allowed": False,
    }
    if not preflight_only:
        commands, live_summary = rerun_contracts(head, matrix)
        result.update(commands=commands, live_rerun=live_summary, entry_allowed=True)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="validate evidence/state only; never claims entry is allowed",
    )
    args = parser.parse_args(argv)
    try:
        result = check(preflight_only=args.preflight_only)
    except (GateFailure, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"WP5 IM-12 entry gate: FAIL — {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
