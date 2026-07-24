"""Final-outcome proof for the bounded compile-database-backed C map."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude" / "skills" / "map-subsystem"
SCRIPT = SKILL / "scripts" / "map_c.py"
FIXTURE = ROOT / "tests" / "fixtures" / "c-pilot" / "host"
CLANG = shutil.which("clang")
CLANGD = shutil.which("clangd")
MAKE = shutil.which("make")
pytestmark = pytest.mark.skipif(
    CLANG is None or CLANGD is None or MAKE is None,
    reason="Clang 21, clangd 21, and Make are required for the frozen C pilot",
)


def _run(*argv: str, cwd: Path, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout
    )


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE, host)
    return host


def _compile_db(host: Path) -> None:
    result = _run(str(MAKE), "clean", "compile-db", f"CC={CLANG}", cwd=host)
    assert result.returncode == 0, result.stdout + result.stderr


def _native_verify(host: Path) -> None:
    result = _run(str(MAKE), "test", f"CC={CLANG}", cwd=host)
    assert result.returncode == 0, result.stdout + result.stderr
    smoke = _run(str(host / ".native-build" / "c-pilot-smoke"), cwd=host)
    assert smoke.returncode == 0
    assert smoke.stdout == "invoice:INV-42:1:pilot\n"


def _fingerprints(host: Path) -> dict[str, str]:
    result = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if any(
            part in {".native-build", ".claude", ".engineering", ".agents", "reports"}
            for part in relative.parts
        ):
            continue
        if path.is_symlink():
            result[relative.as_posix()] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            result[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _map(
    host: Path,
    *,
    script: Path = SCRIPT,
    name: str = "c-pilot",
    target: str = "src",
    clang: str | None = None,
    clangd: str | None = None,
    minimum_clang: str | None = None,
    minimum_clangd: str | None = None,
    output: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    output = output or host / ".engineering" / "docs" / "subsystems" / f"{name}.md"
    evidence = host / "reports" / "map" / name / "c-map.json"
    argv = [
        sys.executable,
        str(script),
        "--name", name,
        "--target", target,
        "--project-root", str(host),
        "--output", str(output),
        "--evidence", str(evidence),
        "--clang", clang or str(CLANG),
        "--clangd", clangd or str(CLANGD),
    ]
    if minimum_clang:
        argv.extend(["--minimum-clang", minimum_clang])
    if minimum_clangd:
        argv.extend(["--minimum-clangd", minimum_clangd])
    return _run(*argv, cwd=host), output, evidence


def _payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_db(host: Path, transform) -> None:
    path = host / "compile_commands.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    transform(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _freshen_db(host: Path) -> None:
    database = host / "compile_commands.json"
    newest = max(path.stat().st_mtime_ns for path in host.rglob("*") if path.is_file())
    os.utime(database, ns=(newest + 2_000_000_000, newest + 2_000_000_000))


def _fake_tool(path: Path, body: str) -> Path:
    path.write_text("#!/bin/sh\nset -eu\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def test_c_map_reaches_exact_inventory_public_surface_edges_and_native_test(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    _compile_db(host)
    _native_verify(host)
    before = _fingerprints(host)

    result, output, evidence = _map(host)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _fingerprints(host) == before
    payload = _payload(evidence)
    rendered = output.read_text(encoding="utf-8")
    assert payload["status"] == "complete"
    assert payload["analyzer"] == "clang-compile-db+dependency-output+ast-json"
    assert payload["translation_units"] == ["src/invoice.c", "src/main.c"]
    assert payload["owned_headers"] == [
        "include/cpilot/invoice.h",
        "src/invoice_internal.h",
        "src/pilot_mode.inc",
    ]
    assert payload["ambiguous_headers"] == ["include/orphan.h", "include/orphan.inc"]
    assert {row["name"] for row in payload["public_surface"]} == {
        "invoice_labeler",
        "invoice_render",
    }
    assert payload["dependency_edges"] == [
        {"header": "include/cpilot/invoice.h", "translation_unit": "src/invoice.c"},
        {"header": "src/invoice_internal.h", "translation_unit": "src/invoice.c"},
        {"header": "src/pilot_mode.inc", "translation_unit": "src/invoice.c"},
        {"header": "include/cpilot/invoice.h", "translation_unit": "src/main.c"},
    ]
    assert payload["translation_unit_edges"] == [{
        "left": "src/invoice.c",
        "right": "src/main.c",
        "shared_headers": ["include/cpilot/invoice.h"],
        "resolution": "shared-compiler-dependency",
    }]
    roles = {row["path"]: (row["role"], row["included"]) for row in payload["source_inventory"]}
    assert roles["tests/invoice_test.c"] == ("test", False)
    assert roles["generated/GeneratedInvoice.c"] == ("generated", False)
    assert roles["vendor/VendorInvoice.c"] == ("vendor", False)
    assert roles["build/BuildSentinel.c"] == ("build", False)
    assert roles["include/orphan.h"] == ("ambiguous-header", False)
    assert payload["completeness"] == {
        "compile_database": "complete",
        "translation_unit_inventory": "complete",
        "dependency_inventory": "complete",
        "declarations_and_public_surface": "complete",
        "cross_translation_unit_edges": "complete",
        "function_pointer_call_resolution": "unsupported",
    }
    assert "Status: **complete**" in rendered
    assert "Function-pointer call targets" in rendered
    _native_verify(host)


def test_c_map_replaces_same_destination_after_failed_and_clean_runs(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _compile_db(host)
    valid, output, evidence = _map(host, name="transition")
    assert valid.returncode == 0
    valid_doc = output.read_text(encoding="utf-8")

    invoice = host / "src" / "invoice.c"
    original = invoice.read_text(encoding="utf-8")
    invoice.write_text(original.replace("return invoice_sequence;", "return ;"), encoding="utf-8")
    _freshen_db(host)
    failed, _, _ = _map(host, name="transition")
    assert failed.returncode == 2
    assert _payload(evidence)["status"] == "failed"
    assert _payload(evidence)["failure_kind"] == "clang_analysis_failed"
    assert output.read_text(encoding="utf-8") != valid_doc
    assert "Status: **failed**" in output.read_text(encoding="utf-8")

    (host / "src" / "invoice.c").write_text(
        "#include <stddef.h>\nint clean_invoice(void) { return 0; }\n", encoding="utf-8"
    )
    (host / "src" / "main.c").write_text(
        "#include <stddef.h>\nint clean_main(void) { return 0; }\n", encoding="utf-8"
    )
    _compile_db(host)
    clean, _, _ = _map(host, name="transition")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    clean_payload = _payload(evidence)
    assert clean_payload["status"] == "complete"
    assert {row["name"] for row in clean_payload["declarations"]} == {
        "clean_invoice", "clean_main",
    }
    assert clean_payload["public_surface"] == []
    assert clean_payload["dependency_edges"] == []
    assert "No public declarations" in output.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("case", "status", "kind"),
    [
        ("missing", "unsupported", "compile_database_missing"),
        ("malformed", "failed", "compile_database_malformed"),
        ("mismatched", "unsupported", "compile_database_mismatched_directory"),
        ("stale", "partial", "compile_database_stale"),
        ("incomplete", "partial", "compile_database_incomplete"),
        ("non-c", "unsupported", "compile_database_non_c_command"),
        ("fallback", "unsupported", "clangd_fallback_forbidden"),
    ],
)
def test_c_map_compile_database_terminal_states(
    tmp_path: Path, case: str, status: str, kind: str
) -> None:
    host = _copy_host(tmp_path, case)
    _compile_db(host)
    database = host / "compile_commands.json"
    if case == "missing":
        database.unlink()
    elif case == "malformed":
        database.write_text("{", encoding="utf-8")
    elif case == "mismatched":
        _write_db(host, lambda rows: rows[0].__setitem__("directory", str(tmp_path)))
    elif case == "stale":
        newer = database.stat().st_mtime_ns + 2_000_000_000
        os.utime(host / "src" / "main.c", ns=(newer, newer))
    elif case == "incomplete":
        _write_db(host, lambda rows: rows.pop())
    elif case == "non-c":
        _write_db(host, lambda rows: rows[0]["arguments"].append("-x=c++"))
    elif case == "fallback":
        database.unlink()
        (host / "compile_flags.txt").write_text("-std=c17\n", encoding="utf-8")

    result, output, evidence = _map(host, name=case)

    assert result.returncode == (2 if status == "failed" else 0)
    payload = _payload(evidence)
    assert payload["status"] == status
    assert payload["failure_kind"] == kind
    assert payload.get("declarations", []) == []
    assert f"Status: **{status}**" in output.read_text(encoding="utf-8")


def test_c_map_tool_boundaries_and_zero_exit_clangd_fallback(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _compile_db(host)
    missing_clang, _, evidence = _map(host, name="missing-clang", clang=str(host / "none"))
    assert missing_clang.returncode == 0
    assert _payload(evidence)["failure_kind"] == "clang_missing"

    old_clang, _, evidence = _map(host, name="old-clang", minimum_clang="99.0")
    assert old_clang.returncode == 0
    assert _payload(evidence)["failure_kind"] == "clang_version_too_old"

    missing_clangd, _, evidence = _map(host, name="missing-clangd", clangd=str(host / "none"))
    assert missing_clangd.returncode == 0
    assert _payload(evidence)["failure_kind"] == "clangd_missing"

    old_clangd, _, evidence = _map(host, name="old-clangd", minimum_clangd="99.0")
    assert old_clangd.returncode == 0
    assert _payload(evidence)["failure_kind"] == "clangd_version_too_old"

    fake = _fake_tool(
        host / "clangd-zero",
        "if [ \"${1:-}\" = \"--version\" ]; then echo 'clangd version 21.0.0'; fi\nexit 0\n",
    )
    fallback, _, evidence = _map(host, name="zero-fallback", clangd=str(fake))
    assert fallback.returncode == 0
    payload = _payload(evidence)
    assert payload["status"] == "unsupported"
    assert payload["failure_kind"] == "clangd_fallback_forbidden"
    assert payload["clangd_checks"][0]["process_exit"] == 0
    assert payload["clangd_checks"][0]["compile_database_attributed"] is False


def test_c_map_refuses_unsafe_target_and_artifact_but_preserves_sources(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _compile_db(host)
    victim = host / "src" / "invoice.c"
    before = victim.read_bytes()
    unsafe, _, _ = _map(host, name="unsafe-output", output=victim)
    assert unsafe.returncode == 2
    assert "output must stay" in unsafe.stderr
    assert victim.read_bytes() == before

    external = tmp_path / "external"
    external.mkdir()
    os.symlink(external, host / "linked")
    linked, _, evidence = _map(host, name="linked", target="linked")
    assert linked.returncode == 0
    assert _payload(evidence)["failure_kind"] == "unsafe_target"
    assert victim.read_bytes() == before


def test_c_map_copied_selected_skill_closure_has_no_checkout_dependency(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _compile_db(host)
    installed_root = host / ".agents" / "skills" / "map-subsystem"
    shutil.copytree(SKILL, installed_root)
    installed = installed_root / "scripts" / "map_c.py"
    before = _fingerprints(host)

    result, _, evidence = _map(host, script=installed, name="copied")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _payload(evidence)["status"] == "complete"
    assert _fingerprints(host) == before
    source = installed.read_text(encoding="utf-8")
    assert str(ROOT) not in source
    assert "libclang" not in source.lower()
    assert "clang.cindex" not in source
