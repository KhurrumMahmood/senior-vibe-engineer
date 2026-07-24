"""Bounded transactional C source-file move with native verification."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".claude/skills/move-path/scripts/c_source_move.py"
FIXTURE = ROOT / "tests/fixtures/c-pilot/host"
CLANG = Path("/usr/bin/clang")
MAKE = Path("/usr/bin/make")

pytestmark = pytest.mark.skipif(
    not CLANG.is_file() or not MAKE.is_file(),
    reason="Apple Clang and Make are required for the bounded C move cohort",
)


def _run(*argv: str, cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE, host)
    prepared = _run(
        str(MAKE), "clean", "compile-db", "test", f"CC={CLANG}", cwd=host
    )
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    return host


def _tree(host: Path) -> dict[str, tuple[str, bytes | str, int]]:
    rows: dict[str, tuple[str, bytes | str, int]] = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if relative.parts[:2] == ("reports", "move-path"):
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = ("link", os.readlink(path), 0)
        elif path.is_file():
            rows[relative.as_posix()] = (
                "file",
                path.read_bytes(),
                stat.S_IMODE(path.stat().st_mode),
            )
    return rows


def _source_tree(host: Path) -> dict[str, tuple[str, bytes | str, int]]:
    return {
        path: value
        for path, value in _tree(host).items()
        if not path.startswith(".native-build/") and path != "compile_commands.json"
    }


def _plan(
    host: Path,
    *,
    source: str = "src/invoice.c",
    destination: str = "src/billing/invoice.c",
    clang: Path = CLANG,
    make: Path = MAKE,
    moves: list[dict[str, str]] | None = None,
) -> Path:
    plan = host / "c-move.json"
    payload = {
        "version": 1,
        "moves": moves or [{"from": source, "to": destination, "mode": "file"}],
        "rewrite": {"code_imports": "update-c"},
        "c": {
            "clang": str(clang),
            "make": str(make),
            "compile_database": "compile_commands.json",
            "native_target": "test",
            "smoke": ".native-build/c-pilot-smoke",
            "smoke_expected_stdout": "invoice:INV-42:1:pilot\n",
        },
    }
    plan.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return plan


def _invoke(
    host: Path,
    plan: Path,
    mode: str,
    *,
    script: Path = SCRIPT,
    evidence: Path | None = None,
    approval: str | None = None,
    cwd: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict, Path]:
    report_dir = host / "reports/move-path"
    argv = [
        str(Path(sys.executable).resolve()),
        "-I",
        "-S",
        str(script),
        "--plan",
        str(plan),
        "--project-root",
        str(host),
        "--report-dir",
        str(report_dir),
        f"--{mode}",
        "--json",
    ]
    if evidence is not None:
        argv.extend(["--evidence", str(evidence)])
    if approval is not None:
        argv.extend(["--approve-evidence-sha256", approval])
    result = _run(*argv, cwd=cwd or host)
    report_path = report_dir / "report.json"
    report = (
        json.loads(report_path.read_text(encoding="utf-8"))
        if report_path.is_file()
        else {}
    )
    return result, report, report_dir


def _preview(host: Path, plan: Path, *, script: Path = SCRIPT) -> tuple[dict, Path, dict]:
    result, report, report_dir = _invoke(host, plan, "dry-run", script=script)
    assert result.returncode == 0, result.stdout + result.stderr
    evidence_path = report_dir / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert report["c"]["evidence_sha256"] == evidence["evidence_sha256"]
    return report, evidence_path, evidence


def _fake_tool(path: Path, body: str) -> Path:
    path.write_text("#!/bin/sh\nset -eu\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def test_c_preview_apply_check_exact_move_and_native_outcome(tmp_path: Path) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    before = _source_tree(host)
    protected = {
        path: hashlib.sha256((host / path).read_bytes()).hexdigest()
        for path in (
            "include/cpilot/invoice.h",
            "src/invoice_internal.h",
            "src/main.c",
            "tests/invoice_test.c",
            "generated/GeneratedInvoice.c",
            "vendor/VendorInvoice.c",
            "build/BuildSentinel.c",
        )
    }

    preview, evidence_path, evidence = _preview(host, plan)

    assert preview["c"]["status"] == "complete"
    assert _source_tree(host) == before
    changes = {
        (row["file_before"], row["kind"], row["old"], row["new"])
        for row in preview["c"]["exact_changes"]
    }
    assert (
        "src/invoice.c",
        "c_relative_include",
        "invoice_internal.h",
        "../invoice_internal.h",
    ) in changes
    assert (
        "Makefile",
        "make_path",
        "src/invoice.c",
        "src/billing/invoice.c",
    ) in changes
    assert preview["c"]["native_preflight"]["make"]["passed"] is True
    assert preview["c"]["native_preflight"]["smoke"]["stdout"] == (
        "invoice:INV-42:1:pilot\n"
    )

    applied_result, applied, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )

    assert applied_result.returncode == 0, applied_result.stdout + applied_result.stderr
    assert applied["c"]["status"] == "complete"
    assert applied["c"]["rolled_back"] is False
    assert applied["c"]["exact_after_tree"]["passed"] is True
    assert not (host / "src/invoice.c").exists()
    moved = host / "src/billing/invoice.c"
    assert moved.is_file()
    assert '#include "../invoice_internal.h"' in moved.read_text(encoding="utf-8")
    makefile = (host / "Makefile").read_text(encoding="utf-8")
    assert "src/billing/invoice.c" in makefile
    assert "src/invoice.c" not in makefile
    database = json.loads((host / "compile_commands.json").read_text(encoding="utf-8"))
    assert {Path(row["file"]).relative_to(host).as_posix() for row in database} == {
        "src/billing/invoice.c",
        "src/main.c",
    }
    assert all(
        hashlib.sha256((host / path).read_bytes()).hexdigest() == digest
        for path, digest in protected.items()
    )

    check_result, checked, _ = _invoke(
        host, plan, "check", evidence=evidence_path
    )
    assert check_result.returncode == 0, check_result.stdout + check_result.stderr
    assert checked["c"]["status"] == "complete"
    assert checked["c"]["old_identity_remaining"] == []


@pytest.mark.parametrize(
    ("mutation", "kind"),
    [
        ("multiple", "c_requires_exactly_one_move"),
        ("generated", "c_destination_role_refused"),
        ("macro-include", "c_dynamic_include_refused"),
        ("excluded-residue", "c_excluded_old_identity"),
        ("symlink", "c_symlink_boundary"),
    ],
)
def test_c_unsafe_shapes_refuse_without_source_writes(
    tmp_path: Path, mutation: str, kind: str
) -> None:
    host = _host(tmp_path)
    if mutation == "multiple":
        plan = _plan(
            host,
            moves=[
                {"from": "src/invoice.c", "to": "src/billing/invoice.c", "mode": "file"},
                {"from": "src/main.c", "to": "src/app/main.c", "mode": "file"},
            ],
        )
    elif mutation == "generated":
        plan = _plan(host, destination="generated/invoice.c")
    else:
        plan = _plan(host)
        if mutation == "macro-include":
            source = host / "src/invoice.c"
            source.write_text(
                source.read_text(encoding="utf-8").replace(
                    '#include "invoice_internal.h"', "#define INTERNAL_HEADER \"invoice_internal.h\"\n#include INTERNAL_HEADER"
                ),
                encoding="utf-8",
            )
        elif mutation == "excluded-residue":
            (host / "generated/GeneratedInvoice.c").write_text(
                'const char *old_path = "src/invoice.c";\n', encoding="utf-8"
            )
        else:
            source = host / "src/invoice.c"
            contents = source.read_bytes()
            source.unlink()
            target = host / "outside.c"
            target.write_bytes(contents)
            source.symlink_to("../outside.c")
    before = _tree(host)

    result, report, report_dir = _invoke(host, plan, "dry-run")

    assert result.returncode == 2
    assert report["c"]["status"] in {"partial", "unsupported", "failed"}
    assert kind in {row["kind"] for row in report["c"]["blocked"]}
    assert _tree(host) == before
    assert not (report_dir / "evidence.json").exists()


def test_c_stale_or_missing_authority_refuses_without_writes(tmp_path: Path) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    _, evidence_path, evidence = _preview(host, plan)
    before = _tree(host)

    missing, _, _ = _invoke(host, plan, "apply")
    assert missing.returncode == 2
    assert _tree(host) == before

    (host / "src/main.c").write_text(
        (host / "src/main.c").read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    changed = _tree(host)
    stale, report, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )
    assert stale.returncode == 2
    assert report["c"]["status"] == "failed"
    assert "c_stale_evidence" in {row["kind"] for row in report["c"]["blocked"]}
    assert _tree(host) == changed


def test_c_postflight_failure_rolls_back_exact_tree(tmp_path: Path) -> None:
    host = _host(tmp_path)
    fake_make = _fake_tool(
        tmp_path / "make",
        f'if [ -f src/billing/invoice.c ]; then exit 19; fi\nexec "{MAKE}" "$@"\n',
    )
    plan = _plan(host, make=fake_make)
    before = _tree(host)
    _, evidence_path, evidence = _preview(host, plan)

    result, report, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )

    assert result.returncode == 2
    assert report["c"]["rolled_back"] is True
    assert report["c"]["status"] == "failed"
    assert _tree(host) == before


def test_c_copied_standalone_closure_runs_outside_repository(tmp_path: Path) -> None:
    copied = tmp_path / "copied/c_source_move.py"
    copied.parent.mkdir(parents=True)
    shutil.copy2(SCRIPT, copied)
    host = _host(tmp_path, "external-host")
    plan = _plan(host)

    preview, evidence_path, evidence = _preview(host, plan, script=copied)
    assert preview["c"]["status"] == "complete"
    result, report, _ = _invoke(
        host,
        plan,
        "apply",
        script=copied,
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert report["c"]["status"] == "complete"
