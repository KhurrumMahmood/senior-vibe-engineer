"""Go inventory, final-document, failure, and copied-closure proof."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "explain-code"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "explain-code-go-g1"


def _go_bin() -> str:
    go = shutil.which("go")
    if go is None:
        pytest.skip("Go toolchain is unavailable")
    version = subprocess.run([go, "version"], capture_output=True, text=True, check=False)
    if version.returncode != 0 or "go1." not in version.stdout:
        pytest.skip("Go toolchain version is unavailable")
    if int(version.stdout.split("go1.", 1)[1].split(".", 1)[0]) < 22:
        pytest.skip("Go 1.22+ is required")
    return go


def _go_env(tmp_path: Path, *, path: str | None = None) -> dict[str, str]:
    go = Path(_go_bin())
    return {
        **os.environ,
        "PATH": path if path is not None else f"{go.parent}{os.pathsep}{os.environ.get('PATH', '')}",
        "GOCACHE": str(tmp_path / "go-cache"),
    }


def _run(
    *args: str, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, cwd=cwd, env=env, capture_output=True, text=True, check=False
    )


def _fingerprints(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and "reports" not in path.relative_to(root).parts
        and ".agents" not in path.relative_to(root).parts
    }


def _host(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    env = _go_env(tmp_path)
    native = _run("go", "test", "./...", cwd=host, env=env)
    assert native.returncode == 0, native.stdout + native.stderr
    return host, env


def _inventory(
    skill: Path,
    host: Path,
    target: str,
    output: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return _run(
        sys.executable,
        "-I",
        "-S",
        str(skill / "scripts" / "inventory_symbols.py"),
        "--target",
        target,
        "--repo-root",
        str(host),
        "--output",
        str(output),
        cwd=host,
        env=env,
    )


def _write_annotation(path: Path, target: dict) -> None:
    path.write_text(
        f"""# Annotation — {target['symbol_key']}

## Location
- Symbol: `{target['symbol']}`
- File: `{target['file']}`
- Kind: `{target['kind']}`
- Status: `found`

## Intent
`{target['symbol']}` exposes one direct Go declaration from the locked fixture.

## Preconditions
None beyond the source declaration.

## Postconditions
- **Success:** provides the declared package behavior.
- **Failure:** does not resolve ambiguous aliases or build constraints.
- **Side effects:** none in the fixture.

## Invariants
- The exported declaration remains package-visible.

## Callers (0 total)
No in-fixture callers beyond native tests.

## Unexplained regions
No unexplained regions — symbol is fully self-contained.

## Surprising behavior
No surprises — behavior matches the symbol name.
""",
        encoding="utf-8",
    )


def test_go_direct_declarations_reach_complete_inventory(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    before = _fingerprints(host)
    output = host / "reports" / "service-targets.json"

    result = _inventory(SKILL, host, "service/service.go", output, env)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["language"] == "go"
    assert payload["status"] == "complete"
    assert payload["analysis"]["go"] == {
        "status": "complete",
        "analyzer": "go-parser-go-ast",
        "minimum_go_version": "1.22",
    }
    assert {item["symbol"] for item in payload["targets"]} == {
        "Processor",
        "Version",
        "Ready",
        "Decide",
        "Processor.Run",
    }
    assert {item["kind"] for item in payload["targets"]} == {
        "type",
        "module-var",
        "function",
        "method",
    }
    assert payload["unexplained"] == []
    assert _fingerprints(host) == before


def test_go_partial_inventory_renders_alias_and_build_constraint_honestly(
    tmp_path: Path,
) -> None:
    host, env = _host(tmp_path)
    for directory in (
        "testdata",
        "fixture",
        "fixtures",
        "third_party",
        "third-party",
        "deps",
        "dependencies",
    ):
        excluded = host / "service" / directory / "excluded.go"
        excluded.parent.mkdir(parents=True, exist_ok=True)
        excluded.write_text(
            "package excluded\n\nfunc Excluded() string { return \"excluded\" }\n",
            encoding="utf-8",
        )
    before = _fingerprints(host)
    report_dir = host / "reports" / "explanations" / "service"
    targets = report_dir / "targets.json"

    collect = _inventory(SKILL, host, "service", targets, env)

    assert collect.returncode == 0, collect.stdout + collect.stderr
    payload = json.loads(targets.read_text(encoding="utf-8"))
    assert payload["status"] == "partial"
    assert payload["analysis"]["go"]["status"] == "partial"
    assert {item["kind"] for item in payload["unexplained"]} == {
        "unresolved-go-alias",
        "build-constraint-ambiguous",
    }
    assert all("_test.go" not in path for path in payload["files"])
    assert all("generated" not in path for path in payload["files"])
    assert all("vendor" not in path for path in payload["files"])
    assert {item["symbol"] for item in payload["targets"]}.isdisjoint(
        {"hidden", "(*Processor).reset", "GeneratedExport", "VendorExport"}
    )

    annotations = report_dir / "annotations"
    annotations.mkdir(parents=True)
    for target in payload["targets"]:
        _write_annotation(annotations / f"{target['symbol_key']}.md", target)
    document = host / "reports" / "explanations" / "service.md"
    render = _run(
        sys.executable,
        "-I",
        "-S",
        str(SKILL / "scripts" / "render_explanation.py"),
        "--targets",
        str(targets),
        "--annotations-dir",
        str(annotations),
        "--output",
        str(document),
        "--summary",
        "Direct Go declarations are annotated while aliases and constrained files remain visible.",
        "--regenerated",
        "2026-07-20T00:00:00Z",
        "--project-root",
        str(host),
        cwd=host,
        env=env,
    )
    assert render.returncode == 0, render.stdout + render.stderr
    latest = host / "reports" / "explanations" / "latest"
    assert latest.is_symlink()
    assert latest.resolve() == report_dir.resolve()
    rendered = document.read_text(encoding="utf-8")
    assert "| Status | partial |" in rendered
    assert "### Decide" in rendered
    assert "type Remote = strings.Builder" in rendered
    assert "does not select files across build constraints" in rendered
    unexplained = (report_dir / "unexplained.txt").read_text(encoding="utf-8")
    assert "Go v1 does not resolve exported type aliases" in unexplained
    assert "build constraints" in unexplained
    assert _fingerprints(host) == before


def test_go_filename_constraints_are_partial_and_generated_files_are_excluded(
    tmp_path: Path,
) -> None:
    host, env = _host(tmp_path)
    filename_constrained = host / "service" / "platform_amd64.go"
    filename_constrained.write_text(
        "package service\n\nfunc ArchitectureName() string { return \"amd64\" }\n",
        encoding="utf-8",
    )
    generated_constrained = host / "service" / "marker_linux.go"
    generated_constrained.write_text(
        "\n".join(
            ["/*", "package documentation", "*/"]
            + ["// leading fixture comment" for _ in range(400)]
            + [
                "// Code generated by locked fixture. DO NOT EDIT.",
                "",
                "package service",
                "",
                "func GeneratedPlatform() string { return \"excluded\" }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    filename_output = host / "reports" / "filename.json"
    filename_result = _inventory(
        SKILL, host, "service/platform_amd64.go", filename_output, env
    )

    assert filename_result.returncode == 0, filename_result.stdout + filename_result.stderr
    filename_payload = json.loads(filename_output.read_text(encoding="utf-8"))
    assert filename_payload["status"] == "partial"
    assert filename_payload["analysis"]["go"]["status"] == "partial"
    assert filename_payload["targets"] == []
    assert filename_payload["unexplained"] == [
        {
            "file": "service/platform_amd64.go",
            "symbol": "service/platform_amd64.go",
            "kind": "build-constraint-ambiguous",
            "lineno": 1,
            "reason": "Go v1 does not select files across build constraints; this file is left unexplained.",
        }
    ]

    generated_output = host / "reports" / "generated.json"
    generated_result = _inventory(
        SKILL, host, "service/marker_linux.go", generated_output, env
    )

    assert generated_result.returncode == 1
    assert "status=unsupported" in generated_result.stderr
    assert not generated_output.exists()


def test_go_project_root_exclusions_apply_to_narrowed_target(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    excluded = host / "service" / "testdata" / "direct.go"
    excluded.parent.mkdir(parents=True)
    excluded.write_text(
        "package testdata\n\nfunc Direct() string { return \"excluded\" }\n",
        encoding="utf-8",
    )
    output = host / "reports" / "narrowed.json"

    result = _inventory(SKILL, host, "service/testdata", output, env)

    assert result.returncode == 1
    assert "status=unsupported" in result.stderr
    assert not output.exists()


def test_go_malformed_missing_tool_and_excluded_target_have_explicit_status(
    tmp_path: Path,
) -> None:
    malformed, env = _host(tmp_path / "malformed")
    (malformed / "service" / "broken.go").write_text(
        "package service\nfunc Broken( {\n", encoding="utf-8"
    )
    malformed_report = malformed / "reports" / "explanations" / "service"
    malformed_output = malformed_report / "targets.json"
    annotations = malformed_report / "annotations"
    annotations.mkdir(parents=True)
    (annotations / "stale.md").write_text("stale annotation\n", encoding="utf-8")
    (malformed_report / "unexplained.txt").write_text("stale\n", encoding="utf-8")
    (malformed_report / "surprises.txt").write_text("stale\n", encoding="utf-8")
    stale_document = malformed / "reports" / "explanations" / "service.md"
    stale_document.write_text("stale complete explanation\n", encoding="utf-8")
    malformed_output.write_text('{"status": "complete"}\n', encoding="utf-8")
    latest = malformed / "reports" / "explanations" / "latest"
    latest.symlink_to("service")
    malformed_result = _inventory(SKILL, malformed, "service", malformed_output, env)
    assert malformed_result.returncode == 2
    assert "status=failed" in malformed_result.stderr
    assert "syntax error" in malformed_result.stderr
    assert not malformed_output.exists()
    assert not annotations.exists()
    assert not (malformed_report / "unexplained.txt").exists()
    assert not (malformed_report / "surprises.txt").exists()
    assert not stale_document.exists()
    assert not latest.exists() and not latest.is_symlink()
    assert (malformed / "service" / "service.go").is_file()

    missing, _ = _host(tmp_path / "missing")
    missing_output = missing / "reports" / "missing.json"
    missing_output.parent.mkdir(parents=True)
    missing_output.write_text('{"status": "complete"}\n', encoding="utf-8")
    missing_result = _inventory(
        SKILL,
        missing,
        "service/service.go",
        missing_output,
        _go_env(tmp_path / "missing-env", path=""),
    )
    assert missing_result.returncode == 2
    assert "status=unsupported" in missing_result.stderr
    assert "Go toolchain is unavailable" in missing_result.stderr
    assert not missing_output.exists()

    excluded, excluded_env = _host(tmp_path / "excluded")
    excluded_output = excluded / "reports" / "excluded.json"
    excluded_output.parent.mkdir(parents=True)
    excluded_output.write_text('{"status": "complete"}\n', encoding="utf-8")
    excluded_result = _inventory(
        SKILL,
        excluded,
        "service/generated/generated.go",
        excluded_output,
        excluded_env,
    )
    assert excluded_result.returncode == 1
    assert "status=unsupported" in excluded_result.stderr
    assert not excluded_output.exists()


def test_inventory_rejects_source_output_overlap_without_deleting_source(
    tmp_path: Path,
) -> None:
    host, env = _host(tmp_path)
    source = host / "service" / "service.go"
    before = source.read_bytes()

    result = _inventory(SKILL, host, "service/service.go", source, env)

    assert result.returncode == 2
    assert "output overlaps a supported source path" in result.stderr
    assert source.read_bytes() == before

    directory_result = _inventory(SKILL, host, "service", host / "service", env)

    assert directory_result.returncode == 2
    assert "output path must be a file" in directory_result.stderr
    assert source.read_bytes() == before
    assert (host / "service").is_dir()

    source_annotations = host / "service" / "annotations"
    source_annotations.mkdir()
    preserved = source_annotations / "preserved.md"
    preserved.write_text("source-owned\n", encoding="utf-8")
    explanations = host / "reports" / "explanations"
    explanations.mkdir(parents=True)
    (explanations / "service").symlink_to(host / "service")
    escaped_result = _inventory(
        SKILL,
        host,
        "service/service.go",
        explanations / "service" / "targets.json",
        env,
    )

    assert escaped_result.returncode == 2
    assert "must stay directly under" in escaped_result.stderr
    assert preserved.read_text(encoding="utf-8") == "source-owned\n"
    assert not (host / "service" / "targets.json").exists()


def test_copied_go_explanation_closure_runs_outside_source_checkout(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    installed = tmp_path / "installed" / "explain-code"
    shutil.copytree(SKILL, installed)
    output = host / "reports" / "copied-targets.json"

    result = _inventory(installed, host, "service/service.go", output, env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "complete"
    assert (installed / "scripts" / "inventory_go.go").is_file()
    closure = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (installed / "scripts").iterdir()
        if path.is_file()
    )
    assert "scripts/_lib" not in closure
    assert str(REPO_ROOT) not in closure


def test_go_explain_contract_declares_narrow_status_boundary() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    assert "Go v1 contract" in text
    assert "Go 1.22" in text
    assert "go/parser" in text
    assert "complete" in text
    assert "partial" in text
    assert "unsupported" in text
    assert "failed" in text
