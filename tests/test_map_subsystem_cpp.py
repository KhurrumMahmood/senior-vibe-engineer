"""Final-artifact proof for the compile-database-backed C++20 subsystem map."""
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
SCRIPT = SKILL / "scripts" / "map_cpp.py"
FIXTURE = ROOT / "tests" / "fixtures" / "map-subsystem-cpp" / "host"
CLANGXX = shutil.which("clang++")
CLANGD = shutil.which("clangd")
MAKE = shutil.which("make")
pytestmark = pytest.mark.skipif(
    CLANGXX is None or CLANGD is None or MAKE is None,
    reason="Clang++ 21, clangd 21, and Make are required for C++ map conformance",
)


def _run(*argv: str, cwd: Path, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout)


def _host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE, host)
    return host


def _prepare(host: Path) -> None:
    completed = _run(str(MAKE), "clean", "compile-db", f"CXX={CLANGXX}", cwd=host)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _native(host: Path) -> None:
    completed = _run(str(MAKE), "test", f"CXX={CLANGXX}", cwd=host)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    smoke = _run(str(host / ".native-build" / "store-demo"), cwd=host)
    assert smoke.returncode == 0
    assert smoke.stdout == "book:book:book\n"


def _source_bytes(host: Path) -> dict[str, str]:
    result = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if any(
            part in {".agents", ".claude", ".engineering", ".native-build", "reports"}
            for part in relative.parts
        ):
            continue
        if path.is_symlink():
            result[relative.as_posix()] = f"symlink:{os.readlink(path)}"
        elif path.is_file() and path.name != "compile_commands.json":
            result[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _map(
    host: Path,
    *,
    script: Path = SCRIPT,
    name: str = "store",
    target: str = "src",
    clangxx: str | None = None,
    clangd: str | None = None,
    make: str | None = None,
    verify: bool = False,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    output = host / ".engineering" / "docs" / "subsystems" / f"{name}.md"
    evidence = host / "reports" / "map" / name / "cpp-map.json"
    argv = [
        sys.executable, str(script), "--name", name, "--target", target,
        "--project-root", str(host), "--output", str(output), "--evidence", str(evidence),
        "--clangxx", clangxx or str(CLANGXX), "--clangd", clangd or str(CLANGD),
        "--make", make or str(MAKE),
    ]
    if verify:
        argv.append("--verify-artifacts")
    return _run(*argv, cwd=host), output, evidence


def _payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_db(host: Path, transform) -> None:
    database = host / "compile_commands.json"
    payload = json.loads(database.read_text(encoding="utf-8"))
    transform(payload)
    database.write_text(json.dumps(payload), encoding="utf-8")


def _freshen_db(host: Path) -> None:
    database = host / "compile_commands.json"
    newest = max(path.stat().st_mtime_ns for path in host.rglob("*") if path.is_file())
    os.utime(database, ns=(newest + 2_000_000_000, newest + 2_000_000_000))


def _fake_tool(path: Path, body: str) -> Path:
    path.write_text("#!/bin/sh\nset -eu\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def test_cpp_map_copied_closure_produces_useful_verified_artifacts_and_native_smoke(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    _prepare(host)
    _native(host)
    installed_root = host / ".agents" / "skills" / "on-demand" / "map-subsystem"
    shutil.copytree(SKILL, installed_root)
    before = _source_bytes(host)

    result, output, evidence = _map(host, script=installed_root / "scripts" / "map_cpp.py")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _source_bytes(host) == before
    payload = _payload(evidence)
    markdown = output.read_text(encoding="utf-8")
    assert payload["status"] == "complete"
    assert payload["diagnostic_state"] == "clean"
    assert payload["analyzer"] == "clang++-compile-db+dependency-output+ast-json"
    assert payload["compile_database"]["state"] == "valid-current-complete-c++20-mode"
    assert payload["translation_units"] == ["src/catalog.cpp", "src/query.cpp"]
    assert payload["owned_headers"] == [
        "include/store/catalog.hpp", "include/store/labels.tpp",
        "include/store/query.hpp", "src/catalog_detail.hpp",
    ]
    roles = {row["path"]: (row["role"], row["included"]) for row in payload["source_inventory"]}
    assert roles["tests/catalog_test.cpp"] == ("test", False)
    assert roles["generated/Generated.cpp"] == ("generated", False)
    assert roles["vendor/Vendor.cc"] == ("vendor", False)
    assert roles["build/Build.cxx"] == ("build", False)
    assert "foreign/Foreign.c" not in roles
    assert roles["include/orphan.hpp"] == ("ambiguous-header", False)

    surface = {(row["qualified_name"], row["signature"]) for row in payload["public_surface"]}
    assert ("store::Catalog", "unavailable") in surface
    assert ("store::Catalog::find", "const Item *(int) const") in surface
    assert ("store::Catalog::find", "const Item *(std::string_view) const") in surface
    assert ("store::Repository", "unavailable") in surface
    assert ("store::label_for", "std::string (const T &)") in surface
    assert not any(row["qualified_name"].startswith("store::Catalog::items_") for row in payload["public_surface"])

    dependencies = {(row["translation_unit"], row["header"]) for row in payload["dependency_edges"]}
    assert ("src/catalog.cpp", "src/catalog_detail.hpp") in dependencies
    assert ("src/query.cpp", "include/store/query.hpp") in dependencies
    references = {
        (row["direction"], row["source"]["qualified_name"], row["target"]["qualified_name"], row["target"]["signature"])
        for row in payload["reference_edges"]
    }
    assert ("internal", "store::Catalog::label", "store::Catalog::find", "const Item *(int) const") in references
    assert ("internal", "store::describe_item", "store::Catalog::find", "const Item *(int) const") in references
    assert ("inbound", "main", "store::Catalog::find", "const Item *(std::string_view) const") in references
    assert ("internal", "store::Catalog::add", "store::detail::normalize", "std::string (std::string)") in references

    targets = {row["path"] for row in payload["build_targets"]}
    assert {".native-build/catalog.o", ".native-build/query.o", ".native-build/libstore.a", ".native-build/store-demo"} <= targets
    build_edges = {(row["target"], row.get("depends_on"), row["relationship"]) for row in payload["build_relationships"]}
    assert (".native-build/libstore.a", ".native-build/catalog.o", "make-prerequisite") in build_edges
    assert (".native-build/store-demo", ".native-build/libstore.a", "make-prerequisite") in build_edges
    assert payload["completeness"]["virtual_dynamic_dispatch"] == "unsupported"
    assert payload["completeness"]["reflection_runtime_loading"] == "unsupported"
    assert payload["completeness"]["all_template_instantiations"] == "unsupported"
    assert "Status: **complete**" in markdown
    assert "Diagnostic state: **clean**" in markdown
    assert "virtual and dynamic dispatch" in markdown

    verified, _, _ = _map(host, script=installed_root / "scripts" / "map_cpp.py", verify=True)
    assert verified.returncode == 0, verified.stdout + verified.stderr
    assert "verified" in verified.stdout
    _native(host)


def test_cpp_map_verifier_rejects_stale_artifact_and_source_hashes(tmp_path: Path) -> None:
    host = _host(tmp_path)
    _prepare(host)
    mapped, output, evidence = _map(host)
    assert mapped.returncode == 0, mapped.stdout + mapped.stderr
    original_output = output.read_text(encoding="utf-8")
    original_evidence = evidence.read_text(encoding="utf-8")

    changed_payload = json.loads(original_evidence)
    changed_payload["name"] = "tampered"
    evidence.write_text(json.dumps(changed_payload), encoding="utf-8")
    stale_evidence, _, _ = _map(host, verify=True)
    assert stale_evidence.returncode == 2
    assert '"evidence_payload": false' in stale_evidence.stderr
    evidence.write_text(original_evidence, encoding="utf-8")

    output.write_text(original_output + "tampered\n", encoding="utf-8")
    stale_artifact, _, _ = _map(host, verify=True)
    assert stale_artifact.returncode == 2
    assert '"markdown": false' in stale_artifact.stderr
    output.write_text(original_output, encoding="utf-8")

    source = host / "src" / "query.cpp"
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    stale_source, _, _ = _map(host, verify=True)
    assert stale_source.returncode == 2
    assert '"source_snapshot": false' in stale_source.stderr


@pytest.mark.parametrize(
    ("case", "status", "kind"),
    [
        ("missing", "unsupported", "compile_database_missing"),
        ("malformed", "failed", "compile_database_malformed"),
        ("stale", "partial", "compile_database_stale"),
        ("incomplete", "partial", "compile_database_incomplete"),
        ("wrong-language", "unsupported", "compile_database_wrong_language"),
        ("mismatched", "unsupported", "compile_database_mismatched_directory"),
        ("fallback", "unsupported", "clangd_fallback_forbidden"),
    ],
)
def test_cpp_map_compile_database_fails_closed(
    tmp_path: Path, case: str, status: str, kind: str,
) -> None:
    host = _host(tmp_path, case)
    _prepare(host)
    database = host / "compile_commands.json"
    if case == "missing":
        database.unlink()
    elif case == "malformed":
        database.write_text("{", encoding="utf-8")
    elif case == "stale":
        newer = database.stat().st_mtime_ns + 2_000_000_000
        os.utime(host / "src" / "query.cpp", ns=(newer, newer))
    elif case == "incomplete":
        _write_db(host, lambda rows: rows.pop())
    elif case == "wrong-language":
        _write_db(host, lambda rows: rows[0]["arguments"].append("-x=c"))
    elif case == "mismatched":
        _write_db(host, lambda rows: rows[0].__setitem__("directory", str(tmp_path)))
    elif case == "fallback":
        database.unlink()
        (host / "compile_flags.txt").write_text("-std=c++20\n", encoding="utf-8")

    result, output, evidence = _map(host, name=case)

    assert result.returncode == (2 if status == "failed" else 0)
    payload = _payload(evidence)
    assert payload["status"] == status
    assert payload["failure_kind"] == kind
    assert payload.get("public_surface", []) == []
    assert f"Status: **{status}**" in output.read_text(encoding="utf-8")


def test_cpp_map_replaces_complete_artifacts_with_compiler_failure(tmp_path: Path) -> None:
    host = _host(tmp_path)
    _prepare(host)
    complete, output, evidence = _map(host, name="transition")
    assert complete.returncode == 0, complete.stdout + complete.stderr
    previous = output.read_text(encoding="utf-8")

    source = host / "src" / "catalog.cpp"
    source.write_text(source.read_text(encoding="utf-8").replace("return found == values.end()", "return unknown == values.end()", 1), encoding="utf-8")
    _freshen_db(host)
    failed, _, _ = _map(host, name="transition")

    assert failed.returncode == 2
    payload = _payload(evidence)
    assert payload["status"] == "failed"
    assert payload["diagnostic_state"] == "errors"
    assert payload["failure_kind"] in {"clangd_check_failed", "clang_analysis_failed"}
    assert payload.get("public_surface", []) == []
    assert output.read_text(encoding="utf-8") != previous
    assert "Status: **failed**" in output.read_text(encoding="utf-8")


def test_cpp_map_tool_and_clangd_attribution_boundaries(tmp_path: Path) -> None:
    host = _host(tmp_path)
    _prepare(host)
    missing, _, evidence = _map(host, name="missing-clang", clangxx=str(host / "none"))
    assert missing.returncode == 0
    assert _payload(evidence)["failure_kind"] == "clangxx_missing"

    fake_clangd = _fake_tool(
        host / "clangd-zero",
        "if [ \"${1:-}\" = \"--version\" ]; then echo 'clangd version 21.0.0'; fi\nexit 0\n",
    )
    fallback, _, evidence = _map(host, name="zero-fallback", clangd=str(fake_clangd))
    assert fallback.returncode == 0
    payload = _payload(evidence)
    assert payload["status"] == "unsupported"
    assert payload["failure_kind"] == "clangd_fallback_forbidden"
    assert payload["clangd_checks"][0]["process_exit"] == 0
    assert payload["clangd_checks"][0]["compile_database_attributed"] is False


def test_cpp_map_refuses_unsafe_targets_and_artifact_paths(tmp_path: Path) -> None:
    host = _host(tmp_path)
    _prepare(host)
    victim = host / "src" / "catalog.cpp"
    before = victim.read_bytes()
    output = victim
    evidence = host / "reports" / "map" / "unsafe" / "cpp-map.json"
    result = _run(
        sys.executable, str(SCRIPT), "--name", "unsafe", "--target", "src",
        "--project-root", str(host), "--output", str(output), "--evidence", str(evidence),
        "--clangxx", str(CLANGXX), "--clangd", str(CLANGD), "--make", str(MAKE), cwd=host,
    )
    assert result.returncode == 2
    assert "output must stay" in result.stderr
    assert victim.read_bytes() == before

    external = tmp_path / "external"
    external.mkdir()
    (host / "linked").symlink_to(external, target_is_directory=True)
    linked, _, evidence = _map(host, name="linked", target="linked")
    assert linked.returncode == 0
    assert _payload(evidence)["failure_kind"] == "unsafe_target"
    assert victim.read_bytes() == before
