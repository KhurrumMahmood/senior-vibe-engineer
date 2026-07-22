"""Contract tests for the shared repository source inventory."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "source_inventory.py"
PROFILES = REPO_ROOT / "scripts" / "language_profiles"


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _fingerprints(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "inventory.json"
    }


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_inventory_covers_first_party_roles_and_honest_boundaries(tmp_path: Path) -> None:
    host = tmp_path / "host"
    _write(host / "src" / "app.py", "VALUE = 1\n")
    _write(host / "src" / "service.ts", "export const value = 1;\n")
    _write(host / "src" / "View.tsx", "export const View = () => <div />;\n")
    _write(host / "src" / "legacy.js", "export const legacy = 1;\n")
    _write(host / "src" / "LegacyView.jsx", "export const LegacyView = () => null;\n")
    _write(host / "src" / "worker.mjs", "export const worker = 1;\n")
    _write(host / "src" / "settings.cjs", "module.exports = {};\n")
    _write(host / "src" / "types.d.ts", "export declare const value: number;\n")
    _write(host / "src" / "client.generated.ts", "export const generated = 1;\n")
    _write(host / "tests" / "test_app.py", "def test_app(): pass\n")
    _write(host / "fixtures" / "ambiguous.ts", "export const maybeData = 1;\n")
    _write(host / "tools" / "release.py", "print('release')\n")
    _write(host / "migrations" / "0001_initial.py", "MIGRATION = True\n")
    _write(host / "vite.config.ts", "export default {};\n")
    _write(host / "src" / "main.go", "package main\n")
    _write(host / "src" / "main_test.go", "package main\n")
    _write(host / "src" / "main.cpp", "int main() { return 0; }\n")
    _write(host / "include" / "main.hpp", "int main();\n")
    _write(host / "src" / "Main.java", "class Main {}\n")
    _write(host / "tests" / "MainTest.java", "class MainTest {}\n")
    _write(host / "src" / "InvoiceService.php", "<?php\nfinal class InvoiceService {}\n")
    _write(host / "tests" / "InvoiceServiceTest.php", "<?php\nfinal class InvoiceServiceTest {}\n")
    _write(host / "Package.swift", "// swift-tools-version: 6.0\n")
    _write(host / "Sources" / "BillingCore" / "InvoiceService.swift", "struct InvoiceService {}\n")
    _write(host / "swift-tests" / "InvoiceServiceTests.swift", "func testInvoice() {}\n")
    _write(host / "generated" / "GeneratedInvoice.swift", "struct GeneratedInvoice {}\n")
    _write(host / "node_modules" / "pkg" / "vendor.ts", "export const vendor = 1;\n")
    _write(host / "dist" / "bundle.ts", "export const bundled = 1;\n")
    _write(host / ".build" / "SwiftBuildOutput.swift", "struct SwiftBuildOutput {}\n")
    external = tmp_path / "external"
    _write(external / "escaped.ts", "export const escaped = 1;\n")
    (host / "linked").symlink_to(external, target_is_directory=True)

    before = _fingerprints(host)
    output = host / "inventory.json"
    result = _run("--project-root", str(host), "--output", str(output))
    assert result.returncode == 0, result.stderr
    assert _fingerprints(host) == before

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["status"] == "complete"
    assert payload["capabilities"]["inventory_languages"] == [
        "c",
        "cpp",
        "go",
        "java",
        "javascript",
        "php",
        "python",
        "swift",
        "typescript",
    ]
    assert payload["capabilities"]["analysis"] == "none"
    assert payload["capabilities"]["profile_schema_version"] == 1

    files = {row["path"]: row for row in payload["files"]}
    assert len(files) == len(payload["files"])
    assert {
        "src/app.py",
        "src/service.ts",
        "src/View.tsx",
        "src/legacy.js",
        "src/LegacyView.jsx",
        "src/worker.mjs",
        "src/settings.cjs",
        "src/types.d.ts",
        "src/client.generated.ts",
        "tests/test_app.py",
        "fixtures/ambiguous.ts",
        "tools/release.py",
        "migrations/0001_initial.py",
        "vite.config.ts",
        "src/main.go",
        "src/main_test.go",
        "src/main.cpp",
        "include/main.hpp",
        "src/Main.java",
        "tests/MainTest.java",
        "src/InvoiceService.php",
        "tests/InvoiceServiceTest.php",
        "Package.swift",
        "Sources/BillingCore/InvoiceService.swift",
        "swift-tests/InvoiceServiceTests.swift",
        "generated/GeneratedInvoice.swift",
    } == set(files)

    assert files["src/app.py"]["role"] == "source"
    assert files["src/service.ts"]["language"] == "typescript"
    assert files["src/View.tsx"]["language"] == "typescript"
    assert files["src/legacy.js"]["language"] == "javascript"
    assert files["src/LegacyView.jsx"]["language"] == "javascript"
    assert files["src/worker.mjs"]["language"] == "javascript"
    assert files["src/settings.cjs"]["language"] == "javascript"
    assert all(
        files[path]["classification"] == "classified"
        for path in (
            "src/legacy.js",
            "src/LegacyView.jsx",
            "src/worker.mjs",
            "src/settings.cjs",
        )
    )
    assert files["src/types.d.ts"]["role"] == "declaration"
    assert files["src/client.generated.ts"]["role"] == "generated"
    assert files["tests/test_app.py"]["role"] == "test"
    assert files["tools/release.py"]["role"] == "tooling"
    assert files["migrations/0001_initial.py"]["role"] == "migration"
    assert files["vite.config.ts"]["role"] == "configuration"
    assert files["fixtures/ambiguous.ts"]["classification"] == "ambiguous"
    assert files["fixtures/ambiguous.ts"]["reason"] == "fixture_or_product_data"
    assert files["src/main.go"]["language"] == "go"
    assert files["src/main.go"]["classification"] == "classified"
    assert files["src/main_test.go"]["role"] == "test"
    assert files["src/main.cpp"]["language"] == "cpp"
    assert files["src/main.cpp"]["role"] == "source"
    assert files["include/main.hpp"]["language"] == "cpp"
    assert files["include/main.hpp"]["role"] == "declaration"
    assert files["src/Main.java"]["language"] == "java"
    assert files["src/Main.java"]["classification"] == "classified"
    assert files["tests/MainTest.java"]["role"] == "test"
    assert files["src/InvoiceService.php"]["language"] == "php"
    assert files["src/InvoiceService.php"]["classification"] == "classified"
    assert files["tests/InvoiceServiceTest.php"]["role"] == "test"
    assert files["Package.swift"]["language"] == "swift"
    assert files["Package.swift"]["role"] == "configuration"
    assert files["Sources/BillingCore/InvoiceService.swift"]["role"] == "source"
    assert files["swift-tests/InvoiceServiceTests.swift"]["role"] == "test"
    assert files["generated/GeneratedInvoice.swift"]["role"] == "generated"

    excluded = {row["path"]: row for row in payload["excluded_roots"]}
    assert excluded["node_modules"] == {
        "path": "node_modules", "role": "vendor", "reason": "external_dependency"
    }
    assert excluded["dist"] == {
        "path": "dist", "role": "build", "reason": "build_output"
    }
    assert excluded[".build"] == {
        "path": ".build", "role": "build", "reason": "build_output"
    }
    assert excluded["linked"] == {
        "path": "linked", "role": "symlink", "reason": "symlink_boundary"
    }
    assert "node_modules/pkg/vendor.ts" not in files
    assert "dist/bundle.ts" not in files
    assert ".build/SwiftBuildOutput.swift" not in files
    assert "linked/escaped.ts" not in files

    assert payload["counts"]["files"] == len(files)
    assert payload["counts"]["classification"]["ambiguous"] == 1
    assert payload["counts"]["excluded_roles"] == {
        "build": 2,
        "vendor": 1,
        "symlink": 1,
    }


def test_inventory_uses_profile_suffix_and_role_rules(tmp_path: Path) -> None:
    profiles = tmp_path / "profiles"
    shutil.copytree(PROFILES, profiles)
    python_profile = profiles / "python.json"
    payload = json.loads(python_profile.read_text(encoding="utf-8"))
    payload["suffixes"].append(".pyx")
    payload["source_roles"]["test_file_globs"].append("*_check.pyx")
    python_profile.write_text(json.dumps(payload), encoding="utf-8")

    host = tmp_path / "host"
    _write(host / "src" / "module.pyx", "VALUE = 1\n")
    _write(host / "src" / "module_check.pyx", "assert True\n")
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(SCRIPT),
            "--project-root",
            str(host),
            "--profiles-root",
            str(profiles),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    files = {row["path"]: row for row in json.loads(completed.stdout)["files"]}
    assert files["src/module.pyx"]["language"] == "python"
    assert files["src/module.pyx"]["role"] == "source"
    assert files["src/module_check.pyx"]["role"] == "test"


def test_inventory_rejects_outside_roots_and_output(tmp_path: Path) -> None:
    host = tmp_path / "host"
    outside = tmp_path / "outside"
    _write(host / "src" / "app.py")
    _write(outside / "external.py")

    bad_root = _run(
        "--project-root",
        str(host),
        "--source-root",
        str(outside),
    )
    assert bad_root.returncode == 2
    assert "source root must stay within project root" in bad_root.stderr

    bad_output = _run(
        "--project-root",
        str(host),
        "--output",
        str(outside / "inventory.json"),
    )
    assert bad_output.returncode == 2
    assert "output must stay within project root" in bad_output.stderr
    assert not (outside / "inventory.json").exists()

    source = host / "src" / "app.py"
    before = source.read_bytes()
    source_output = _run(
        "--project-root",
        str(host),
        "--output",
        str(source),
    )
    assert source_output.returncode == 2
    assert "output may not replace an inventoried source file" in source_output.stderr
    assert source.read_bytes() == before

    case_variant = source.with_name("APP.py")
    if not case_variant.exists() or not case_variant.samefile(source):
        pytest.skip("case-variant alias requires a case-insensitive filesystem")
    case_output = _run(
        "--project-root",
        str(host),
        "--output",
        str(case_variant),
    )
    assert case_output.returncode == 2
    assert "output may not replace an inventoried source file" in case_output.stderr
    assert source.read_bytes() == before


def test_inventory_matches_two_accepted_skill_family_source_boundaries(
    tmp_path: Path,
) -> None:
    adapt_host = tmp_path / "adapt-host"
    seed = REPO_ROOT / "tests" / "fixtures" / "adapt-project-typescript" / "seed_host.py"
    seeded = subprocess.run(
        [
            sys.executable,
            str(seed),
            "--destination",
            str(adapt_host),
            "--source-files",
            "6",
            "--excluded-files",
            "2",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert seeded.returncode == 0, seeded.stderr
    adapt_inventory_path = adapt_host / "inventory.json"
    inventoried = _run(
        "--project-root",
        str(adapt_host),
        "--output",
        str(adapt_inventory_path),
    )
    assert inventoried.returncode == 0, inventoried.stderr
    adapt_inventory = json.loads(adapt_inventory_path.read_text(encoding="utf-8"))

    adapt_artifacts = tmp_path / "adapt-artifacts"
    discovered = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(REPO_ROOT / ".claude" / "skills" / "adapt-project" / "scripts" / "discover.py"),
            "--project-root",
            str(adapt_host),
            "--artifact-root",
            str(adapt_artifacts),
            "--no-host-write",
            "--timestamp",
            "20260720-000000",
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert discovered.returncode == 0, discovered.stderr
    adapt_scan = Path(discovered.stdout.strip())
    adapter = json.loads((adapt_scan / "adapter.json").read_text(encoding="utf-8"))
    adapt_source_count = sum(
        row["language"] == "typescript"
        and row["role"] == "source"
        and row["path"].startswith("src/")
        for row in adapt_inventory["files"]
    )
    assert adapt_source_count == 6
    assert next(row for row in adapter["source_roots"] if row["path"] == "src")[
        "typescript_files"
    ] == adapt_source_count

    map_host = tmp_path / "map-host"
    shutil.copytree(
        REPO_ROOT / "tests" / "fixtures" / "map-subsystem-typescript" / "host",
        map_host,
    )
    installed = subprocess.run(
        ["npm", "ci", "--offline", "--ignore-scripts"],
        cwd=map_host,
        check=False,
        capture_output=True,
        text=True,
    )
    assert installed.returncode == 0, installed.stderr
    map_inventory_path = map_host / "inventory.json"
    inventoried = _run(
        "--project-root",
        str(map_host),
        "--output",
        str(map_inventory_path),
    )
    assert inventoried.returncode == 0, inventoried.stderr
    map_inventory = json.loads(map_inventory_path.read_text(encoding="utf-8"))
    map_source_count = sum(
        row["language"] == "typescript"
        and row["role"] == "source"
        and row["path"].startswith("src/")
        for row in map_inventory["files"]
    )

    map_evidence = map_host / "reports" / "map" / "inventory-proof.json"
    mapped = subprocess.run(
        [
            "node",
            str(
                REPO_ROOT
                / ".claude"
                / "skills"
                / "map-subsystem"
                / "scripts"
                / "map_typescript.mjs"
            ),
            "--target",
            "src",
            "--project-root",
            str(map_host),
            "--tsconfig",
            "tsconfig.json",
            "--output",
            str(map_host / ".claude" / "docs" / "subsystems" / "inventory-proof.md"),
            "--evidence",
            str(map_evidence),
        ],
        cwd=map_host,
        check=False,
        capture_output=True,
        text=True,
    )
    assert mapped.returncode == 0, mapped.stderr
    map_payload = json.loads(map_evidence.read_text(encoding="utf-8"))
    assert map_source_count == 6
    assert map_payload["counts"]["source_files"] == map_source_count
