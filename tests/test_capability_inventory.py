"""Portable capability-inventory contract over the shared source inventory."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "capability_inventory.py"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run(host: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(SCRIPT),
            "--project-root",
            str(host),
            *args,
        ],
        cwd=host,
        check=False,
        capture_output=True,
        text=True,
    )


CASES = {
    "python": (
        "src/capability.py",
        '"""Build reusable invoice exports.\n\nImplementation detail.\n"""\n',
        "src/use.py",
        "import capability\n",
        1,
        "file",
    ),
    "typescript": (
        "src/capability.ts",
        "/** Build reusable invoice exports. */\nexport const value = 1;\n",
        "src/use.ts",
        'import "./capability";\n',
        1,
        "file",
    ),
    "javascript": (
        "src/capability.js",
        "/** Build reusable invoice exports. */\nexport const value = 1;\n",
        "src/use.js",
        'const value = require("./capability");\n',
        1,
        "file",
    ),
    "go": (
        "src/capability/capability.go",
        "// Package capability builds reusable invoice exports.\npackage capability\n",
        "src/use/use.go",
        'package use\nimport "example.test/inventory/src/capability"\n',
        1,
        "package",
    ),
    "java": (
        "src/com/example/capability/Capability.java",
        "/** Build reusable invoice exports. */\n"
        "package com.example.capability;\npublic class Capability {}\n",
        "src/com/example/use/Use.java",
        "package com.example.use;\n"
        "import com.example.capability.Capability;\npublic class Use {}\n",
        1,
        "file",
    ),
    "kotlin": (
        "src/com/example/capability/Capability.kt",
        "/** Build reusable invoice exports. */\n"
        "package com.example.capability\nclass Capability\n",
        "src/com/example/use/Use.kt",
        "package com.example.use\nimport com.example.capability.Capability\nclass Use\n",
        1,
        "file",
    ),
    "php": (
        "src/Capability.php",
        "<?php\n/** Build reusable invoice exports. */\n"
        "namespace App\\Service;\nfinal class Capability {}\n",
        "src/Use.php",
        "<?php\nnamespace App\\Use;\n" "use App\\Service\\Capability;\nfinal class Use {}\n",
        1,
        "file",
    ),
    "ruby": (
        "src/capability.rb",
        "# Build reusable invoice exports.\nmodule Capability; end\n",
        "src/use.rb",
        'require_relative "capability"\n',
        1,
        "file",
    ),
    "rust": (
        "src/capability.rs",
        "//! Build reusable invoice exports.\npub fn export() {}\n",
        "src/main.rs",
        "mod capability;\nfn main() {}\n",
        1,
        "file",
    ),
    "dart": (
        "lib/capability.dart",
        "/// Build reusable invoice exports.\nvoid exportInvoice() {}\n",
        "lib/use.dart",
        "import 'capability.dart';\n",
        1,
        "file",
    ),
    "c": (
        "src/capability.c",
        "/** Build reusable invoice exports. */\nvoid export_invoice(void) {}\n",
        "src/use.c",
        '#include "capability.c"\n',
        1,
        "file",
    ),
    "cpp": (
        "include/capability.hpp",
        "/** Build reusable invoice exports. */\nvoid export_invoice();\n",
        "src/use.cpp",
        '#include "../include/capability.hpp"\n',
        1,
        "file",
    ),
    "swift": (
        "Sources/Capability/Capability.swift",
        "/// Build reusable invoice exports.\npublic struct Capability {}\n",
        "Sources/Use/Use.swift",
        "import Capability\npublic struct Use {}\n",
        None,
        "unavailable",
    ),
    "csharp": (
        "src/Capability.cs",
        "/// Build reusable invoice exports.\n"
        "namespace App.Service;\npublic sealed class Capability {}\n",
        "src/Use.cs",
        "using App.Service;\nnamespace App.Use;\npublic sealed class Use {}\n",
        None,
        "unavailable",
    ),
}


@pytest.mark.parametrize("language", sorted(CASES))
def test_all_advertised_languages_emit_described_capability_units(
    tmp_path: Path, language: str
) -> None:
    host = tmp_path / language
    provider, provider_source, importer, importer_source, used_by, scope = CASES[language]
    _write(host / provider, provider_source)
    _write(host / importer, importer_source)
    if language == "go":
        _write(host / "go.mod", "module example.test/inventory\n\ngo 1.22\n")

    completed = _run(host, "--stdout", "--format", "json")

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    row = {item["path"]: item for item in payload["units"]}[provider]
    assert row["language"] == language
    assert row["description"] in {
        "Build reusable invoice exports.",
        "Package capability builds reusable invoice exports.",
    }
    assert row["description_status"] == "described"
    assert row["used_by"] == used_by
    assert row["reference_scope"] == scope
    assert row["inbound_paths"] == ([importer] if used_by else [])


def test_inventory_uses_source_roles_and_keeps_failures_visible(tmp_path: Path) -> None:
    host = tmp_path / "host"
    _write(host / "src/good.py", '"""Build reusable invoice exports."""\n')
    _write(host / "src/malformed.py", '"""unterminated\n')
    _write(host / "tests/test_good.py", "from src import good\n")
    _write(host / "generated/client.generated.ts", "/** Generated client. */\n")
    _write(host / "scripts/tool.py", '"""Release helper for maintainers."""\n')

    completed = _run(host, "--stdout", "--format", "json")

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    units = {row["path"]: row for row in payload["units"]}
    assert set(units) == {"src/good.py", "src/malformed.py"}
    assert payload["status"] == "partial"
    assert units["src/malformed.py"]["analysis_status"] == "partial"
    assert units["src/malformed.py"]["description_status"] == "unavailable"
    assert payload["counts"]["excluded_roles"] == {
        "generated": 1,
        "test": 1,
        "tooling": 1,
    }


def test_default_inventory_excludes_agent_state_and_generated_reports(
    tmp_path: Path,
) -> None:
    host = tmp_path / "host"
    _write(host / "src/app.py", '"""Provide the application capability."""\n')
    _write(host / ".agents/skills/router.py", '"""Route agent work."""\n')
    _write(host / "reports/run/generated.py", '"""Recorded result."""\n')

    completed = _run(host, "--stdout", "--format", "json")

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert {row["path"] for row in payload["units"]} == {"src/app.py"}
    assert payload["counts"]["excluded_roles"] == {
        "generated": 1,
        "tooling": 1,
    }


def test_empty_and_reexport_only_python_packages_are_not_capability_units(
    tmp_path: Path,
) -> None:
    host = tmp_path / "host"
    _write(host / "src/empty/__init__.py", "")
    _write(host / "src/reexport/__init__.py", "from .service import Service\n")
    _write(
        host / "src/active/__init__.py",
        '"""Configure the active capability package."""\nVALUE = 1\n',
    )

    completed = _run(host, "--stdout", "--format", "json")

    assert completed.returncode == 0, completed.stderr
    assert {row["path"] for row in json.loads(completed.stdout)["units"]} == {
        "src/active/__init__.py"
    }


def test_markdown_is_deterministic_searchable_and_escapes_tables(tmp_path: Path) -> None:
    host = tmp_path / "host"
    _write(
        host / "src/capability.py",
        '"""Split invoices on | and build reusable exports."""\n',
    )
    _write(host / "src/undocumented.py", "VALUE = 1\n")

    first = _run(host, "--stdout").stdout
    second = _run(host, "--stdout").stdout

    assert first == second
    assert first.startswith("<!-- GENERATED by scripts/capability_inventory.py")
    assert "Split invoices on \\| and build reusable exports." in first
    assert "## Not described — 1" in first
    assert "`src/undocumented.py`" in first
    assert "Static references are bounded evidence" in first


def test_default_write_check_and_no_host_write_boundaries(tmp_path: Path) -> None:
    host = tmp_path / "host"
    _write(host / "src/capability.py", '"""Build reusable invoice exports."""\n')

    written = _run(host)
    output = host / ".engineering/docs/capability-inventory.md"
    assert written.returncode == 0, written.stderr
    assert output.is_file()
    assert _run(host, "--check").returncode == 0

    _write(host / "src/second.py", '"""Build another reusable export."""\n')
    stale = _run(host, "--check")
    assert stale.returncode == 1
    assert "is stale" in stale.stderr

    refused = _run(host, "--no-host-write")
    assert refused.returncode == 2
    assert "outside --project-root or use --stdout" in refused.stderr

    external = tmp_path / "artifacts/capabilities.md"
    accepted = _run(
        host,
        "--output",
        str(external),
        "--no-host-write",
    )
    assert accepted.returncode == 0, accepted.stderr
    assert external.is_file()


def test_language_and_role_filters_are_explicit(tmp_path: Path) -> None:
    host = tmp_path / "host"
    _write(host / "src/capability.py", '"""Build reusable invoice exports."""\n')
    _write(host / "src/capability.ts", "/** Build reusable web exports. */\n")
    _write(host / "scripts/release.py", '"""Publish a release candidate."""\n')

    completed = _run(
        host,
        "--stdout",
        "--format",
        "json",
        "--language",
        "python",
        "--include-role",
        "source",
        "--include-role",
        "tooling",
    )

    assert completed.returncode == 0, completed.stderr
    units = {row["path"] for row in json.loads(completed.stdout)["units"]}
    assert units == {"src/capability.py", "scripts/release.py"}


def test_python_relative_imports_resolve_without_overwriting_source(tmp_path: Path) -> None:
    host = tmp_path / "host"
    _write(host / "src/pkg/capability.py", '"""Build reusable exports."""\n')
    _write(host / "src/pkg/use.py", "from . import capability\n")

    completed = _run(host, "--stdout", "--format", "json")

    assert completed.returncode == 0, completed.stderr
    units = {row["path"]: row for row in json.loads(completed.stdout)["units"]}
    assert units["src/pkg/capability.py"]["inbound_paths"] == ["src/pkg/use.py"]

    refused = _run(host, "--output", str(host / "src/pkg/capability.py"))
    assert refused.returncode == 2
    assert "may not replace an inventoried source file" in refused.stderr

    case_variant = host / "src/pkg/CAPABILITY.py"
    if case_variant.exists() and case_variant.samefile(host / "src/pkg/capability.py"):
        aliased = _run(host, "--output", str(case_variant))
        assert aliased.returncode == 2
        assert "may not replace an inventoried source file" in aliased.stderr


def test_declaration_docs_win_over_license_and_directive_boilerplate(
    tmp_path: Path,
) -> None:
    host = tmp_path / "host"
    _write(
        host / "src/Capability.kt",
        "/* Copyright 2026 Example */\n"
        "package example\n\n"
        "/** Build reusable invoice exports. */\n"
        "class Capability\n",
    )
    _write(
        host / "src/capability.ts",
        "/* Licensed under the Example License. */\n"
        'import {value} from "./value";\n\n'
        "/** Build reusable web exports. */\n"
        "export class Capability {}\n",
    )
    _write(
        host / "Sources/Capability.swift",
        "// swift-tools-version: 6.0\n"
        "/// Build reusable Swift exports.\n"
        "public struct Capability {}\n",
    )

    completed = _run(host, "--stdout", "--format", "json")

    assert completed.returncode == 0, completed.stderr
    units = {row["path"]: row for row in json.loads(completed.stdout)["units"]}
    assert units["src/Capability.kt"]["description"] == ("Build reusable invoice exports.")
    assert units["src/capability.ts"]["description"] == ("Build reusable web exports.")
    assert units["Sources/Capability.swift"]["description"] == ("Build reusable Swift exports.")


def test_typescript_runtime_extensions_and_dart_package_imports_resolve(
    tmp_path: Path,
) -> None:
    host = tmp_path / "host"
    _write(
        host / "src/capability.ts",
        "/** Build reusable web exports. */\nexport const value = 1;\n",
    )
    _write(host / "src/use.ts", 'import "./capability.js";\n')
    _write(host / "pubspec.yaml", "name: example_inventory\n")
    _write(
        host / "lib/capability.dart",
        "/// Build reusable Dart exports.\nvoid exportInvoice() {}\n",
    )
    _write(
        host / "lib/use.dart",
        "import 'package:example_inventory/capability.dart';\n",
    )

    completed = _run(host, "--stdout", "--format", "json")

    assert completed.returncode == 0, completed.stderr
    units = {row["path"]: row for row in json.loads(completed.stdout)["units"]}
    assert units["src/capability.ts"]["inbound_paths"] == ["src/use.ts"]
    assert units["lib/capability.dart"]["inbound_paths"] == ["lib/use.dart"]
