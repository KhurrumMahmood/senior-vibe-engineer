"""Final-artifact and copied-closure proof for the bounded Go package map."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "map-subsystem"
SCRIPT = SKILL / "scripts" / "map_go.go"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "map-subsystem-go" / "host"
GO = shutil.which("go")
pytestmark = pytest.mark.skipif(GO is None, reason="Go toolchain is required")


def _run(
    *args: str,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE, host)
    return host


def _fingerprints(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and (path.suffix == ".go" or path.name in {"go.mod", "go.sum"})
        and ".agents" not in path.relative_to(host).parts
    }


def _map(
    host: Path,
    *,
    name: str = "go-features",
    target: str = "internal/features",
    output: Path | None = None,
    evidence: Path | None = None,
    minimum_go: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    output = output or host / ".claude" / "docs" / "subsystems" / f"{name}.md"
    evidence = evidence or host / "reports" / "map" / name / "go-map.json"
    args = [
        GO,
        "run",
        str(SCRIPT),
        "--name",
        name,
        "--target",
        target,
        "--project-root",
        str(host),
        "--output",
        str(output),
        "--evidence",
        str(evidence),
        "--effectiveness-log",
        str(host / "reports" / "_meta" / "effectiveness.jsonl"),
    ]
    if minimum_go is not None:
        args.extend(["--minimum-go", minimum_go])
    return _run(*args, cwd=host), output, evidence


def _payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _documented_command(skill: Path) -> str:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(
        r"<!-- installed-command:go-map:start -->\n```bash\n(.*?)\n```\n"
        r"<!-- installed-command:go-map:end -->",
        text,
        re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def test_go_map_reaches_final_artifacts_with_active_package_and_first_party_edges(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    assert _run(GO, "fmt", "./...", cwd=host).returncode == 0
    native = _run(GO, "test", "./...", cwd=host)
    assert native.returncode == 0, native.stdout + native.stderr
    before = _fingerprints(host)

    result, output, evidence = _map(host)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _fingerprints(host) == before
    payload = _payload(evidence)
    rendered = output.read_text(encoding="utf-8")
    assert payload["status"] == "complete"
    assert payload["language"] == "go"
    assert payload["analyzer"] == "go-list-plus-stdlib-ast"
    assert payload["module"]["path"] == "example.com/map-subsystem-go"
    assert payload["target"] == {
        "path": "internal/features",
        "kind": "package_directory",
        "package": "features",
        "import_path": "example.com/map-subsystem-go/internal/features",
        "source_files": 2,
        "excluded_files": ["internal/features/wire_generated.go:generated"],
    }
    assert payload["counts"] == {
        "source_files": 2,
        "exported_symbols": 6,
        "outbound_imports": 2,
        "inbound_imports": 2,
        "unresolved_imports": 0,
        "workflow_entries": 1,
    }
    assert {item["name"] for item in payload["exported_surface"]} == {
        "Widget",
        "DefaultLabel",
        "BuildWidget",
        "PublicLabel",
        "DefaultPanel",
        "NewPanel",
    }
    assert any(item["name"] == "PublicLabel" and item["kind"] == "method" for item in payload["exported_surface"])
    assert all(edge["resolution"] == "first_party" for edge in payload["outbound_imports"])
    assert {edge["style"] for edge in payload["inbound_imports"]} == {"default", "alias"}
    assert payload["active_build"]["ignored_go_files"] == ["internal/features/not_selected.go"]
    assert payload["workflow_participation"] == {
        "availability": "available",
        "entries": [{
            "name": "feature-checkout",
            "path": ".claude/docs/workflows/feature-checkout.md",
            "matched_paths": ["internal/features/widget.go"],
        }],
    }
    assert payload["completeness"]["build_matrix"] == "unavailable"
    assert "Status: **complete**" in rendered
    assert "Current active Go build only" in rendered
    assert len((host / "reports" / "_meta" / "effectiveness.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_go_map_preserves_partial_and_failed_states(tmp_path: Path) -> None:
    partial_host = _copy_host(tmp_path, "partial")
    (partial_host / "internal" / "features" / "unresolved.go").write_text(
        'package features\n\nimport "example.com/map-subsystem-go/internal/missing"\n\nfunc Missing() {}\n',
        encoding="utf-8",
    )
    partial, _, partial_evidence = _map(partial_host, name="partial")
    assert partial.returncode == 0, partial.stdout + partial.stderr
    partial_payload = _payload(partial_evidence)
    assert partial_payload["status"] == "partial"
    assert partial_payload["unresolved_imports"] == [{
        "file": "internal/features/unresolved.go",
        "line": 3,
        "import_path": "example.com/map-subsystem-go/internal/missing",
        "style": "default",
        "resolution": "unresolved_first_party",
    }]
    assert partial_payload["completeness"]["first_party_module_edges"] == "partial"

    cgo_host = _copy_host(tmp_path, "cgo")
    (cgo_host / "internal" / "features" / "cgo.go").write_text(
        'package features\n\n/*\n#include <stdlib.h>\n*/\nimport "C"\n\nfunc CgoBoundary() {}\n',
        encoding="utf-8",
    )
    cgo, _, cgo_evidence = _map(cgo_host, name="cgo")
    assert cgo.returncode == 0, cgo.stdout + cgo.stderr
    cgo_payload = _payload(cgo_evidence)
    assert cgo_payload["status"] == "partial"
    assert cgo_payload["failure_kind"] == "cgo_unavailable"

    malformed_host = _copy_host(tmp_path, "malformed")
    (malformed_host / "internal" / "features" / "broken.go").write_text(
        "package features\n\nfunc Broken( {\n", encoding="utf-8"
    )
    malformed, _, malformed_evidence = _map(malformed_host, name="malformed")
    assert malformed.returncode != 0
    malformed_payload = _payload(malformed_evidence)
    assert malformed_payload["status"] == "failed"
    assert malformed_payload["failure_kind"] == "syntax_error"


def test_go_map_refuses_excluded_symlinked_and_unsafe_artifact_paths(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    excluded, _, excluded_evidence = _map(host, name="vendor", target="vendor/example.com/ignored")
    assert excluded.returncode == 0, excluded.stdout + excluded.stderr
    assert _payload(excluded_evidence)["status"] == "unsupported"
    assert _payload(excluded_evidence)["failure_kind"] == "excluded_target"

    external = tmp_path / "external"
    external.mkdir()
    os.symlink(external, host / "internal" / "linked")
    linked, _, linked_evidence = _map(host, name="linked", target="internal/linked")
    assert linked.returncode == 0, linked.stdout + linked.stderr
    assert _payload(linked_evidence)["failure_kind"] == "unsafe_target"

    victim = host / "internal" / "features" / "widget.go"
    before = victim.read_bytes()
    unsafe, _, _ = _map(
        host,
        name="unsafe",
        output=victim,
        evidence=host / "reports" / "map" / "unsafe" / "go-map.json",
    )
    assert unsafe.returncode != 0
    assert "artifact output" in unsafe.stderr
    assert victim.read_bytes() == before

    shutil.rmtree(host / "reports", ignore_errors=True)
    os.symlink(host / "internal", host / "reports")
    unsafe_report, _, _ = _map(host, name="unsafe-report")
    assert unsafe_report.returncode != 0
    assert "symbolic link" in unsafe_report.stderr


def test_go_map_old_tool_and_documented_copied_closure_are_self_contained(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    old, _, old_evidence = _map(host, name="old", minimum_go="99.0")
    assert old.returncode == 0, old.stdout + old.stderr
    assert _payload(old_evidence)["failure_kind"] == "go_version_too_old"

    before = _fingerprints(host)
    installed = host / ".agents" / "skills" / "map-subsystem"
    shutil.copytree(SKILL, installed)
    result = _run(
        "/bin/bash",
        "-c",
        _documented_command(installed),
        cwd=host,
        env={**os.environ, "MAP_NAME": "copied", "MAP_TARGET": "internal/features"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert _fingerprints(host) == before
    payload = _payload(host / "reports" / "map" / "copied" / "go-map.json")
    assert payload["status"] == "complete"
    closure = (installed / "scripts" / "map_go.go").read_text(encoding="utf-8")
    assert "golang.org/x/tools" not in closure
    assert '"golang.org/x/tools/go/packages"' not in closure
    assert '"go/types"' not in closure
    assert str(REPO_ROOT) not in closure
    assert _run(GO, "test", "./...", cwd=host).returncode == 0


def test_go_map_workspace_is_explicitly_unsupported(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    (host / "go.work").write_text("go 1.22\n\nuse .\n", encoding="utf-8")
    result, _, evidence = _map(host, name="workspace")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = _payload(evidence)
    assert payload["status"] == "unsupported"
    assert payload["failure_kind"] == "go_workspace_active"


def test_go_map_docs_state_the_bounded_family_local_contract() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "scans: [python, typescript, javascript, go]" in text
    assert "Go 1.22" in text
    assert "go list -e -json -mod=readonly ./..." in text
    assert "go/parser` and `go/ast" in text
    assert "go/packages" in text
    assert "go/types" in text
