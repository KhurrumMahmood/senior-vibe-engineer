"""Transactional proof for one compiler-bounded C++20 implementation-unit move."""

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
SCRIPT = ROOT / ".claude/skills/move-path/scripts/cpp_source_move.py"
FIXTURE = ROOT / "tests/fixtures/cpp-move-path/host"
CLANGXX = Path("/usr/bin/clang++")
MAKE = Path("/usr/bin/make")
NM = Path("/usr/bin/nm")

pytestmark = pytest.mark.skipif(
    not all(path.is_file() for path in (CLANGXX, MAKE, NM)),
    reason="Apple Clang++, Make, and nm are required for the C++20 move cohort",
)


def _run(*argv: str, cwd: Path, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _prepare(host: Path) -> None:
    prepared = _run(
        str(MAKE), "clean", "compile-db", "test", f"CXX={CLANGXX}", cwd=host
    )
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr


def _host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE, host)
    _prepare(host)
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
    source: str = "src/invoice.cpp",
    destination: str = "src/billing/invoice.cpp",
    make: Path = MAKE,
    nm: Path = NM,
    moves: list[dict[str, str]] | None = None,
    cpp_extra: dict[str, object] | None = None,
) -> Path:
    plan = host / "cpp-move.json"
    cpp: dict[str, object] = {
        "clangxx": str(CLANGXX),
        "make": str(make),
        "nm": str(nm),
        "compile_database": "compile_commands.json",
        "source_roots": ["src", "tests"],
        "native_target": "test",
        "smoke": ".native-build/cpp-move-smoke",
        "smoke_expected_stdout": "invoice:INV-42:pending\n",
        "moved_object": ".native-build/invoice.o",
        "artifact_kind": "closed-executable",
        "external_consumers": "none-known",
    }
    cpp.update(cpp_extra or {})
    payload = {
        "version": 1,
        "moves": moves or [{"from": source, "to": destination, "mode": "file"}],
        "rewrite": {"code_imports": "update-cpp20"},
        "cpp": cpp,
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
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
    return result, report, report_dir


def _preview(
    host: Path, plan: Path, *, script: Path = SCRIPT
) -> tuple[dict, Path, dict]:
    result, report, report_dir = _invoke(host, plan, "dry-run", script=script)
    assert result.returncode == 0, result.stdout + result.stderr
    evidence_path = report_dir / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert report["cpp"]["evidence_sha256"] == evidence["evidence_sha256"]
    return report, evidence_path, evidence


def _fake_tool(path: Path, body: str) -> Path:
    path.write_text("#!/bin/sh\nset -eu\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def test_cpp_preview_approve_apply_check_exact_compiler_and_native_outcome(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    before = _source_tree(host)
    protected = {
        path: hashlib.sha256((host / path).read_bytes()).hexdigest()
        for path in (
            "include/cppmove/invoice.hpp",
            "src/invoice_internal.hpp",
            "src/main.cpp",
            "tests/invoice_test.cpp",
            "generated/GeneratedInvoice.cpp",
            "vendor/VendorInvoice.cpp",
        )
    }

    preview, evidence_path, evidence = _preview(host, plan)

    cpp = preview["cpp"]
    assert cpp["status"] == "complete"
    assert _source_tree(host) == before
    changes = {
        (row["file_before"], row["kind"], row["old"], row["new"])
        for row in cpp["exact_changes"]
    }
    assert (
        "src/invoice.cpp",
        "cpp_relative_include",
        "invoice_internal.hpp",
        "../invoice_internal.hpp",
    ) in changes
    assert (
        "Makefile",
        "cpp_make_path",
        "src/invoice.cpp",
        "src/billing/invoice.cpp",
    ) in changes
    impacts = {row["source"]: row["headers"] for row in cpp["compiler_impacts_before"]}
    assert impacts["src/invoice.cpp"] == [
        "include/cppmove/invoice.hpp",
        "src/invoice_internal.hpp",
    ]
    assert cpp["native_preflight"]["make"]["passed"] is True
    assert cpp["native_preflight"]["smoke"]["stdout"] == "invoice:INV-42:pending\n"
    assert cpp["identity_proof"]["symbols_before"] == cpp["identity_proof"]["symbols_after"]
    assert evidence["expected_after_tree_sha256"]

    applied_result, applied, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )

    assert applied_result.returncode == 0, applied_result.stdout + applied_result.stderr
    assert applied["cpp"]["status"] == "complete"
    assert applied["cpp"]["rolled_back"] is False
    assert applied["cpp"]["exact_after_tree"]["passed"] is True
    assert not (host / "src/invoice.cpp").exists()
    moved = host / "src/billing/invoice.cpp"
    assert moved.is_file()
    assert '#include "../invoice_internal.hpp"' in moved.read_text(encoding="utf-8")
    assert "src/billing/invoice.cpp" in (host / "Makefile").read_text(encoding="utf-8")
    database = json.loads((host / "compile_commands.json").read_text(encoding="utf-8"))
    assert {Path(row["file"]).relative_to(host).as_posix() for row in database} == {
        "src/billing/invoice.cpp",
        "src/main.cpp",
        "tests/invoice_test.cpp",
    }
    assert all(
        hashlib.sha256((host / path).read_bytes()).hexdigest() == digest
        for path, digest in protected.items()
    )

    checked_result, checked, _ = _invoke(host, plan, "check", evidence=evidence_path)
    assert checked_result.returncode == 0, checked_result.stdout + checked_result.stderr
    assert checked["cpp"]["status"] == "complete"
    assert checked["cpp"]["old_identity_remaining"] == []


@pytest.mark.parametrize(
    ("mutation", "kind"),
    [
        ("multiple", "cpp_requires_exactly_one_move"),
        ("identity", "cpp_identity_change_refused"),
        ("namespace", "cpp_identity_or_scope_change_refused"),
        ("ambiguous-header", "cpp_ambiguous_header_dependency"),
        ("template", "cpp_template_ownership_uncertain"),
        ("macro-variant", "cpp_macro_variant_uncertain"),
        ("odr-source-include", "cpp_odr_source_include_uncertain"),
        ("external-consumer", "cpp_external_consumer_uncertain"),
        ("symlink", "cpp_symlink_boundary"),
    ],
)
def test_cpp_uncertain_identity_header_template_odr_abi_and_consumer_shapes_refuse(
    tmp_path: Path, mutation: str, kind: str
) -> None:
    host = _host(tmp_path)
    if mutation == "multiple":
        plan = _plan(
            host,
            moves=[
                {"from": "src/invoice.cpp", "to": "src/billing/invoice.cpp", "mode": "file"},
                {"from": "src/main.cpp", "to": "src/app/main.cpp", "mode": "file"},
            ],
        )
    elif mutation == "identity":
        plan = _plan(host, destination="src/billing/renamed.cpp")
    elif mutation == "namespace":
        plan = _plan(host, cpp_extra={"namespace_after": "billing"})
    else:
        plan = _plan(host)
        if mutation == "ambiguous-header":
            header = host / "src/invoice_internal.hpp"
            ambiguous = header.with_suffix(".h")
            header.rename(ambiguous)
            source = host / "src/invoice.cpp"
            source.write_text(
                source.read_text(encoding="utf-8").replace(
                    "invoice_internal.hpp", "invoice_internal.h"
                ),
                encoding="utf-8",
            )
            makefile = host / "Makefile"
            makefile.write_text(
                makefile.read_text(encoding="utf-8").replace(
                    "invoice_internal.hpp", "invoice_internal.h"
                ),
                encoding="utf-8",
            )
            _prepare(host)
        elif mutation == "template":
            header = host / "src/invoice_internal.hpp"
            header.write_text(
                header.read_text(encoding="utf-8")
                + "\ntemplate <typename T> T cpp_move_identity(T value) { return value; }\n",
                encoding="utf-8",
            )
            _prepare(host)
        elif mutation == "macro-variant":
            header = host / "src/invoice_internal.hpp"
            header.write_text(
                header.read_text(encoding="utf-8") + "\n#if 1\nstatic_assert(true);\n#endif\n",
                encoding="utf-8",
            )
            _prepare(host)
        elif mutation == "odr-source-include":
            consumer = host / "tests/invoice_test.cpp"
            consumer.write_text(
                '#include "../src/invoice.cpp"\n' + consumer.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        elif mutation == "external-consumer":
            (host / "generated/GeneratedInvoice.cpp").write_text(
                'const char* moved_source = "src/invoice.cpp";\n', encoding="utf-8"
            )
            _prepare(host)
        else:
            source = host / "src/invoice.cpp"
            contents = source.read_bytes()
            source.unlink()
            outside = host / "outside.cpp"
            outside.write_bytes(contents)
            source.symlink_to("../outside.cpp")
    before = _tree(host)

    result, report, report_dir = _invoke(host, plan, "dry-run")

    assert result.returncode == 2
    assert report["cpp"]["status"] in {"partial", "unsupported", "failed"}
    assert kind in {row["kind"] for row in report["cpp"]["blocked"]}
    assert _tree(host) == before
    assert not (report_dir / "evidence.json").exists()


def test_cpp_compile_database_must_be_current_complete_and_single_variant(
    tmp_path: Path,
) -> None:
    for state, mutate, kind in (
        (
            "incomplete",
            lambda rows: rows.pop(),
            "cpp_compile_database_incomplete",
        ),
        (
            "variant",
            lambda rows: rows[0]["arguments"].insert(1, "-DCPP_MOVE_VARIANT=1"),
            "cpp_macro_variant_uncertain",
        ),
    ):
        host = _host(tmp_path / state)
        plan = _plan(host)
        database = host / "compile_commands.json"
        rows = json.loads(database.read_text(encoding="utf-8"))
        mutate(rows)
        database.write_text(json.dumps(rows), encoding="utf-8")
        result, report, _ = _invoke(host, plan, "dry-run")
        assert result.returncode == 2
        assert kind in {row["kind"] for row in report["cpp"]["blocked"]}

    stale = _host(tmp_path / "stale")
    plan = _plan(stale)
    source = stale / "src/main.cpp"
    newer = (stale / "compile_commands.json").stat().st_mtime_ns + 2_000_000_000
    os.utime(source, ns=(newer, newer))
    result, report, _ = _invoke(stale, plan, "dry-run")
    assert result.returncode == 2
    assert "cpp_compile_database_stale" in {
        row["kind"] for row in report["cpp"]["blocked"]
    }


def test_cpp_stale_or_missing_approval_refuses_without_writes(tmp_path: Path) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    _, evidence_path, evidence = _preview(host, plan)
    before = _tree(host)

    missing, _, _ = _invoke(host, plan, "apply")
    assert missing.returncode == 2
    assert _tree(host) == before

    source = host / "src/main.cpp"
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    changed = _tree(host)
    stale, report, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )
    assert stale.returncode == 2
    assert "cpp_stale_evidence" in {row["kind"] for row in report["cpp"]["blocked"]}
    assert _tree(host) == changed


def test_cpp_postflight_failure_rolls_back_exact_tree(tmp_path: Path) -> None:
    host = _host(tmp_path)
    fake_make = _fake_tool(
        tmp_path / "make",
        f'if [ "$PWD" = {json.dumps(str(host))} ] && [ -f src/billing/invoice.cpp ]; '
        f'then exit 19; fi\nexec "{MAKE}" "$@"\n',
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
    assert report["cpp"]["rolled_back"] is True
    assert report["cpp"]["status"] == "failed"
    assert _tree(host) == before


def test_cpp_copied_stock_selected_adapter_runs_outside_repository(
    tmp_path: Path,
) -> None:
    copied = tmp_path / "installed/move-path/scripts/cpp_source_move.py"
    copied.parent.mkdir(parents=True)
    shutil.copy2(SCRIPT, copied)
    host = _host(tmp_path, "external-host")
    plan = _plan(host)

    preview, evidence_path, evidence = _preview(host, plan, script=copied)
    assert preview["cpp"]["status"] == "complete"
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
    assert report["cpp"]["status"] == "complete"
    assert report["cpp"]["exact_after_tree"]["passed"] is True
