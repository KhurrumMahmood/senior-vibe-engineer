"""End-to-end Go proposal, deferral, source-safety, and copied-closure proof."""
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
SKILL = REPO_ROOT / ".claude" / "skills" / "propose-boundary"
SCRIPT = SKILL / "scripts" / "propose_go.go"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "propose-boundary-go"
GO = shutil.which("go")
pytestmark = pytest.mark.skipif(GO is None, reason="Go toolchain is required")


def _run(
    *args: str,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _copy_host(tmp_path: Path, name: str) -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE / name, host)
    return host


def _fingerprints(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and (
            path.suffix == ".go"
            or path.name in {"go.mod", "go.sum"}
        )
        and ".agents" not in path.relative_to(host).parts
    }


def _propose(
    host: Path,
    target: str,
    *,
    name: str,
    candidates: int = 1,
    minimum_go: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    inspection = host / "reports" / "propose-boundary" / name / "inspection.json"
    proposal = inspection.with_name("proposal.md")
    args = [
        GO,
        "run",
        str(SCRIPT),
        "--target",
        target,
        "--project-root",
        str(host),
        "--candidates",
        str(candidates),
        "--inspection",
        str(inspection),
        "--proposal",
        str(proposal),
    ]
    if minimum_go is not None:
        args.extend(["--minimum-go", minimum_go])
    return _run(*args, cwd=host), inspection, proposal


def _payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _documented_command(skill: Path) -> str:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(
        r"<!-- installed-command:go-proposal:start -->\n```bash\n(.*?)\n```\n"
        r"<!-- installed-command:go-proposal:end -->",
        text,
        re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def test_go_positive_proposal_reaches_final_artifact_with_tied_cutoff(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path, "positive")
    before = _fingerprints(host)

    formatted = _run(GO, "fmt", "./...", cwd=host)
    assert formatted.returncode == 0, formatted.stderr
    native_test = _run(GO, "test", "./...", cwd=host)
    assert native_test.returncode == 0, native_test.stdout + native_test.stderr
    result, inspection, proposal = _propose(host, "internal/legacy", name="positive")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _fingerprints(host) == before
    payload = _payload(inspection)
    rendered = proposal.read_text(encoding="utf-8")

    assert payload["status"] == "complete"
    assert payload["recommendation"] == "refactor"
    assert payload["analyzer"] == "go-list-plus-stdlib-ast"
    assert payload["tooling"]["go_path"]
    assert payload["tooling"]["minimum_go"] == "1.22"
    assert payload["module"]["path"] == "example.com/propose-boundary-go"
    assert payload["target"]["import_path"] == "example.com/propose-boundary-go/internal/legacy"
    assert payload["candidate_selection"] == {
        "requested": 1,
        "eligible": 2,
        "returned": 2,
        "cutoff_score": 3,
        "ties_included": True,
        "omitted_count": 0,
        "omitted": [],
    }
    assert {row["cluster_id"] for row in payload["candidate_seams"]} == {
        "quote",
        "settlement",
    }
    quote = next(row for row in payload["candidate_seams"] if row["cluster_id"] == "quote")
    assert quote["proposed_public_api"] == ["QuotePreview", "QuotePrice"]
    assert quote["exported_named_type_dependencies"] == {
        "QuotePreview": ["Input"],
        "QuotePrice": ["Input"],
    }
    assert any(
        symbol["name"] == "QuotePrice"
        and symbol["exported_named_type_dependencies"] == ["Input"]
        for symbol in payload["symbols"]
    )
    assert any(
        edge["caller_symbol"] == "SettlementCapture"
        and edge["callee_symbol"] == "quoteNormalize"
        and edge["resolution"] == "syntax_candidate"
        for edge in quote["private_cross_domain_calls"]
    )
    assert {row["style"] for row in payload["caller_impact"]} == {"default", "alias"}
    assert "go list -e -json -mod=readonly ./..." in rendered
    assert "gofmt -w <human-approved changed .go files>" in rendered
    assert "go test ./..." in rendered
    assert "ties included: true" in rendered
    assert "Preserve named type identity for `Input`" in rendered


def test_go_cohesive_package_defers_without_inventing_a_boundary(tmp_path: Path) -> None:
    host = _copy_host(tmp_path, "cohesive")
    result, inspection, proposal = _propose(host, "internal/shipping", name="cohesive")

    assert result.returncode == 0, result.stdout + result.stderr
    payload = _payload(inspection)
    assert payload["status"] == "complete"
    assert payload["recommendation"] == "defer_no_seam"
    assert payload["candidate_seams"] == []
    assert payload["defer_signals"] == ["single_cluster_no_seam"]
    rendered = proposal.read_text(encoding="utf-8")
    assert "No extraction proposal is safe" in rendered
    assert "<nil>" not in rendered
    assert "no second viable named declaration domain" in rendered


def test_go_package_and_caller_ambiguity_and_unresolved_graphs_defer(
    tmp_path: Path,
) -> None:
    build_tagged = _copy_host(tmp_path, "ambiguous")
    build_result, build_inspection, _ = _propose(
        build_tagged, "internal/legacy", name="build-tagged"
    )
    assert build_result.returncode == 0, build_result.stdout + build_result.stderr
    build_payload = _payload(build_inspection)
    assert build_payload["status"] == "partial"
    assert build_payload["recommendation"] == "defer_build_constraints"

    dot_import = _copy_host(tmp_path, "ambiguous-caller")
    dot_result, dot_inspection, dot_proposal = _propose(dot_import, "internal/legacy", name="dot-import")
    assert dot_result.returncode == 0, dot_result.stdout + dot_result.stderr
    dot_payload = _payload(dot_inspection)
    assert dot_payload["status"] == "partial"
    assert dot_payload["recommendation"] == "defer_ambiguous_caller_evidence"
    assert dot_payload["ambiguous_caller_evidence"]
    dot_rendered = dot_proposal.read_text(encoding="utf-8")
    assert "<nil>" not in dot_rendered
    assert "caller-impact evidence is ambiguous" in dot_rendered

    unresolved = _copy_host(tmp_path, "unresolved")
    unresolved_result, unresolved_inspection, _ = _propose(
        unresolved, "internal/legacy", name="unresolved"
    )
    assert unresolved_result.returncode == 0, unresolved_result.stdout + unresolved_result.stderr
    unresolved_payload = _payload(unresolved_inspection)
    assert unresolved_payload["status"] == "partial"
    assert unresolved_payload["recommendation"] == "defer_unresolved_package_graph"


def test_go_malformed_and_excluded_targets_never_produce_a_clean_proposal(
    tmp_path: Path,
) -> None:
    malformed = _copy_host(tmp_path, "malformed")
    malformed_result, malformed_inspection, _ = _propose(
        malformed, "internal/legacy", name="malformed"
    )
    assert malformed_result.returncode != 0
    malformed_payload = _payload(malformed_inspection)
    assert malformed_payload["status"] == "failed"
    assert malformed_payload["failure_kind"] == "syntax_error"

    excluded = _copy_host(tmp_path, "excluded")
    for target, name in (
        ("internal/generated", "generated"),
        ("vendor/example.com/ignored", "vendor"),
    ):
        result, inspection, _ = _propose(excluded, target, name=name)
        assert result.returncode == 0, result.stdout + result.stderr
        payload = _payload(inspection)
        assert payload["status"] == "unsupported"
        assert payload["recommendation"] == "defer_excluded_target"


def test_go_old_and_missing_tool_paths_are_explicitly_unsupported(tmp_path: Path) -> None:
    host = _copy_host(tmp_path, "positive")
    old_result, old_inspection, _ = _propose(
        host, "internal/legacy", name="old", minimum_go="99.0"
    )
    assert old_result.returncode == 0, old_result.stdout + old_result.stderr
    old_payload = _payload(old_inspection)
    assert old_payload["status"] == "unsupported"
    assert old_payload["failure_kind"] == "go_version_too_old"

    installed = host / ".agents" / "skills" / "propose-boundary"
    shutil.copytree(SKILL, installed)
    missing = _run(
        "/bin/bash",
        "-c",
        _documented_command(installed),
        cwd=host,
        env={**os.environ, "PATH": ""},
    )
    assert missing.returncode == 0, missing.stdout + missing.stderr
    assert json.loads(missing.stdout)["status"] == "unsupported"
    assert "go_tool_missing" in missing.stdout


def test_go_workspace_and_replace_directives_are_explicitly_unsupported(
    tmp_path: Path,
) -> None:
    workspace = _copy_host(tmp_path, "positive")
    (workspace / "go.work").write_text("go 1.22\n\nuse .\n", encoding="utf-8")
    workspace_result, workspace_inspection, _ = _propose(
        workspace, "internal/legacy", name="workspace"
    )
    assert workspace_result.returncode == 0, workspace_result.stdout + workspace_result.stderr
    workspace_payload = _payload(workspace_inspection)
    assert workspace_payload["status"] == "unsupported"
    assert workspace_payload["recommendation"] == "defer_workspace"
    assert workspace_payload["failure_kind"] == "go_workspace_active"

    replaced = tmp_path / "replace"
    shutil.copytree(FIXTURE / "positive", replaced)
    go_mod = replaced / "go.mod"
    go_mod.write_text(
        go_mod.read_text(encoding="utf-8") + "\nreplace example.com/unused => ./unused\n",
        encoding="utf-8",
    )
    replace_result, replace_inspection, _ = _propose(
        replaced, "internal/legacy", name="replace"
    )
    assert replace_result.returncode == 0, replace_result.stdout + replace_result.stderr
    replace_payload = _payload(replace_inspection)
    assert replace_payload["status"] == "unsupported"
    assert replace_payload["recommendation"] == "defer_module_topology"
    assert replace_payload["failure_kind"] == "go_mod_replace"


def test_go_runner_source_avoids_go_1_18_any_alias() -> None:
    assert re.search(r"\bany\b", SCRIPT.read_text(encoding="utf-8")) is None


def test_documented_command_rejects_old_go_before_go_run(tmp_path: Path) -> None:
    host = _copy_host(tmp_path, "positive")
    installed = host / ".agents" / "skills" / "propose-boundary"
    shutil.copytree(SKILL, installed)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    attempted_run = tmp_path / "go-run-attempted"
    fake_go = fake_bin / "go"
    fake_go.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = version ]; then\n"
        "  printf '%s\\n' 'go version go1.21.9 darwin/arm64'\n"
        "  exit 0\n"
        "fi\n"
        f"printf '%s\\n' attempted > {str(attempted_run)!r}\n"
        "exit 99\n",
        encoding="utf-8",
    )
    fake_go.chmod(0o755)

    result = _run(
        "/bin/bash",
        "-c",
        _documented_command(installed),
        cwd=host,
        env={**os.environ, "PATH": f"{fake_bin}:/usr/bin:/bin"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {
        "status": "unsupported",
        "failure_kind": "go_version_too_old",
        "minimum_go": "1.22",
    }
    assert not attempted_run.exists()


def test_go_copied_skill_closure_runs_without_repository_imports(tmp_path: Path) -> None:
    host = _copy_host(tmp_path, "positive")
    before = _fingerprints(host)
    installed = host / ".agents" / "skills" / "propose-boundary"
    shutil.copytree(SKILL, installed)

    result = _run(
        "/bin/bash",
        "-c",
        _documented_command(installed),
        cwd=host,
        env={**os.environ, "PROPOSE_NAME": "copied"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert _fingerprints(host) == before
    payload = _payload(host / "reports" / "propose-boundary" / "copied" / "inspection.json")
    assert payload["recommendation"] == "refactor"
    closure = (installed / "scripts" / "propose_go.go").read_text(encoding="utf-8")
    assert "golang.org/x/tools" not in closure
    assert '"golang.org/x/tools/go/packages"' not in closure
    assert str(REPO_ROOT) not in closure


def test_go_skill_docs_limit_the_family_local_v1() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    assert "scans: [python, typescript, javascript, go, java]" in text
    assert "Go 1.22" in text
    assert "go list -e -json -mod=readonly ./..." in text
    assert "go/parser`/`go/ast" in text
    assert "go/packages" in text
    assert "go env GOWORK" in text
    assert "go mod edit -json" in text
