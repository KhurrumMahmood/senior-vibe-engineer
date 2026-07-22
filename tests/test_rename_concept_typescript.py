"""Installed TypeScript/TSX outcome and safety tests for rename-concept."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / ".claude" / "skills" / "rename-concept"
FIXTURE_HOST = REPO_ROOT / "tests" / "fixtures" / "rename-concept-typescript" / "host"


def _run(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-S", str(script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _make_host(tmp_path: Path, *, nested_in_node_modules: bool = False) -> Path:
    host = tmp_path / "node_modules" / "typescript-host" if nested_in_node_modules else tmp_path / "host"
    shutil.copytree(FIXTURE_HOST, host)
    init = subprocess.run(
        ["git", "init", "--quiet"], cwd=host, capture_output=True, text=True, check=False
    )
    assert init.returncode == 0, init.stdout + init.stderr
    add = subprocess.run(["git", "add", "-A"], cwd=host, capture_output=True, text=True, check=False)
    assert add.returncode == 0, add.stdout + add.stderr
    return host


def _copy_installed_skills(tmp_path: Path, *, include_detector: bool = True) -> Path:
    skills_root = tmp_path / "installed" / ".agents" / "skills"
    shutil.copytree(SKILL_ROOT, skills_root / "rename-concept")
    if include_detector:
        shutil.copytree(
            REPO_ROOT / ".claude" / "skills" / "find-concept-divergence",
            skills_root / "find-concept-divergence",
        )
    return skills_root / "rename-concept"


def _install_host_typescript(host: Path) -> None:
    install = subprocess.run(
        ["npm", "ci", "--offline", "--ignore-scripts"],
        cwd=host,
        capture_output=True,
        text=True,
        check=False,
    )
    assert install.returncode == 0, install.stdout + install.stderr


def _assessment_path(host: Path, name: str) -> Path:
    return host / "reports" / "rename-concept" / name


def _documented_command(skill: Path, name: str) -> str:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(
        rf"\s*<!-- installed-command:{name}:start -->\n\s*```bash\n(.*?)\n\s*```\n"
        rf"\s*<!-- installed-command:{name}:end -->",
        text,
        re.DOTALL,
    )
    assert match is not None, name
    return match.group(1)


def test_installed_assessment_finds_ts_and_tsx_drift_without_mutating_source(tmp_path: Path) -> None:
    host = _make_host(tmp_path, nested_in_node_modules=True)
    installed = _copy_installed_skills(tmp_path)
    outside = tmp_path / "outside.ts"
    outside.write_text(
        "export const legacyStatus = canonicalStatus; // legacy status\n", encoding="utf-8"
    )
    os.symlink(outside, host / "src" / "external.ts")
    _install_host_typescript(host)
    source_before = {
        path.relative_to(host).as_posix(): path.read_bytes()
        for path in (host / "src").glob("*")
        if path.name != "external.ts"
    }
    assessment = _assessment_path(host, "dirty-assessment.json")

    result = _run(
        installed / "scripts" / "assess.py",
        "legacy-status",
        "canonical-status",
        "--project-root",
        str(host),
        "--output",
        str(assessment),
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "src/transition.ts" in result.stdout
    assert "src/retired-copy.tsx" in result.stdout
    assert "node_modules/vendor/legacy.ts" not in result.stdout
    assert "dist/generated.tsx" not in result.stdout
    assert "docs/rename-glossary.md" not in result.stdout
    assert "external.ts" not in result.stdout
    assert "old/new lexical co-occurrence candidates" in result.stdout
    assert "retired prose still using the old phrasing" in result.stdout
    assert "TypeScript/TSX: RESOLVED — compiler API 5.9.3" in result.stdout
    assert "shadowed_local" in result.stdout
    assert "import_alias" in result.stdout
    assert "property_key" in result.stdout
    assert "string_literal" in result.stdout
    assert "comment_text" in result.stdout
    assert "HALF-APPLIED / INCOMPLETE" in result.stdout
    payload = json.loads(assessment.read_text(encoding="utf-8"))
    assert payload["read_only"] is True
    assert payload["verdict"] == "HALF-APPLIED / INCOMPLETE"
    assert {
        candidate["classification"] for candidate in payload["lexical_gate"]["candidate_classifications"]
    } >= {"shadowed_local", "import_alias", "property_key", "string_literal", "comment_text"}
    assert source_before == {
        path.relative_to(host).as_posix(): path.read_bytes()
        for path in (host / "src").glob("*")
        if path.name != "external.ts"
    }

    relative_assessment = Path("reports/rename-concept/relative-assessment.json")
    relative_result = _run(
        installed / "scripts" / "assess.py",
        "legacy-status",
        "canonical-status",
        "--project-root",
        str(host),
        "--output",
        str(relative_assessment),
        cwd=tmp_path,
    )
    assert relative_result.returncode == 0, relative_result.stdout + relative_result.stderr
    assert (host / relative_assessment).is_file()

    escaped_output = tmp_path / "escaped-assessment.json"
    escape_dir = host / "reports" / "rename-concept" / "escape"
    escape_dir.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(tmp_path, escape_dir)
    for rejected_output in (
        host / "reports",
        host / "reports" / "rename-concept",
        host / "src" / "transition.ts",
        host / "src" / "external.ts",
        escaped_output,
        Path("../escaped-relative-assessment.json"),
        escape_dir / "assessment.json",
    ):
        rejected = _run(
            installed / "scripts" / "assess.py",
            "legacy-status",
            "canonical-status",
            "--project-root",
            str(host),
            "--output",
            str(rejected_output),
            cwd=tmp_path,
        )
        assert rejected.returncode == 2
        assert "reports/rename-concept" in rejected.stderr
    assert not escaped_output.exists()
    assert not (tmp_path / "assessment.json").exists()
    assert not (host.parent / "escaped-relative-assessment.json").exists()
    assert outside.read_text(encoding="utf-8") == (
        "export const legacyStatus = canonicalStatus; // legacy status\n"
    )
    assert source_before == {
        path.relative_to(host).as_posix(): path.read_bytes()
        for path in (host / "src").glob("*")
        if path.name != "external.ts"
    }


def test_assessment_output_rejects_all_in_tree_symlink_components(tmp_path: Path) -> None:
    installed = _copy_installed_skills(tmp_path)
    host = _make_host(tmp_path)
    report_root = host / "reports" / "rename-concept"
    contained = report_root / "contained"
    contained.mkdir(parents=True)

    final_target = contained / "final-target.json"
    final_target.write_text("preserve final target\n", encoding="utf-8")
    final_alias = report_root / "final-alias.json"
    os.symlink(final_target, final_alias)

    ancestor_alias = report_root / "ancestor-alias"
    os.symlink(contained, ancestor_alias)

    report_alias_root = tmp_path / "report-alias-case"
    report_alias_root.mkdir()
    report_alias_host = _make_host(report_alias_root)
    source_report_dir = report_alias_host / "src" / "rename-concept"
    source_report_dir.mkdir()
    source_victim = source_report_dir / "victim.py"
    source_victim.write_text("ORIGINAL_SOURCE_CONTENT = True\n", encoding="utf-8")
    source_before = source_victim.read_bytes()
    os.symlink(report_alias_host / "src", report_alias_host / "reports")

    cases = (
        (host, final_alias),
        (host, ancestor_alias / "assessment.json"),
        (report_alias_host, report_alias_host / "reports" / "rename-concept" / "victim.py"),
    )
    for project_root, rejected_output in cases:
        rejected = _run(
            installed / "scripts" / "assess.py",
            "legacy-status",
            "canonical-status",
            "--project-root",
            str(project_root),
            "--output",
            str(rejected_output),
            cwd=tmp_path,
        )
        assert rejected.returncode == 2
        assert "symlink components" in rejected.stderr

    assert final_target.read_text(encoding="utf-8") == "preserve final target\n"
    assert not (contained / "assessment.json").exists()
    assert source_victim.read_bytes() == source_before


def test_coupled_scanner_uses_project_relative_exclusions_and_never_follows_escape(tmp_path: Path) -> None:
    host = _make_host(tmp_path, nested_in_node_modules=True)
    installed = _copy_installed_skills(tmp_path)
    outside = tmp_path / "outside.ts"
    outside.write_text(
        "export const legacyStatus = canonicalStatus; // legacy status\n", encoding="utf-8"
    )
    os.symlink(outside, host / "src" / "external.ts")
    scanner = installed.parent / "find-concept-divergence" / "scripts" / "scan.py"

    first_party = host / "reports" / "first-party.jsonl"
    first_party_result = _run(
        scanner,
        "--project-root",
        str(host),
        "--output",
        str(first_party),
        "--report",
        str(host / "reports" / "first-party.md"),
        "src",
        cwd=tmp_path,
    )
    assert first_party_result.returncode == 0, first_party_result.stdout + first_party_result.stderr
    records = _records(first_party)
    assert {record["file"] for record in records if record["band"] == "superseded_co_occurrence"} == {
        "src/comment-candidate.ts",
        "src/import-alias-candidate.ts",
        "src/property-candidate.ts",
        "src/shadowed-name-candidate.ts",
        "src/string-candidate.ts",
        "src/transition.ts",
    }
    assert {record["file"] for record in records if record["band"] == "avoid_term_hit"} == {
        "src/retired-copy.tsx"
    }
    assert all(not Path(record["file"]).is_absolute() for record in records)
    assert all("external.ts" not in record["file"] for record in records)

    for target in ("node_modules", "node_modules/vendor/legacy.ts", "dist", "src/external.ts"):
        output = host / "reports" / f"{target.replace('/', '_')}.jsonl"
        result = _run(
            scanner,
            "--project-root",
            str(host),
            "--output",
            str(output),
            "--report",
            str(output.with_suffix(".md")),
            target,
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert _records(output) == []

    contained = host / "contained-tree"
    contained.mkdir()
    (contained / "legacy.ts").write_text(
        "export const legacyStatus = canonicalStatus;\n", encoding="utf-8"
    )
    os.symlink(contained, host / "internal-directory-alias")
    (host / "reports").mkdir(exist_ok=True)
    os.symlink(contained, host / "reports" / "logical-alias")
    external_directory = tmp_path / "external-directory"
    external_directory.mkdir()
    (external_directory / "legacy.ts").write_text(
        "export const legacyStatus = canonicalStatus;\n", encoding="utf-8"
    )
    os.symlink(external_directory, host / "external-directory-alias")

    for target in (
        "internal-directory-alias",
        "internal-directory-alias/legacy.ts",
        "reports/logical-alias",
        "external-directory-alias",
    ):
        output = host / "reports" / f"{target.replace('/', '_')}.jsonl"
        result = _run(
            scanner,
            "--project-root",
            str(host),
            "--output",
            str(output),
            "--report",
            str(output.with_suffix(".md")),
            target,
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert _records(output) == []

    contained_output = host / "reports" / "contained-tree.jsonl"
    contained_result = _run(
        scanner,
        "--project-root",
        str(host),
        "--output",
        str(contained_output),
        "--report",
        str(contained_output.with_suffix(".md")),
        "contained-tree",
        cwd=tmp_path,
    )
    assert contained_result.returncode == 0, contained_result.stdout + contained_result.stderr
    assert {record["file"] for record in _records(contained_output)} == {"contained-tree/legacy.ts"}


@pytest.mark.parametrize("router_name", ["which-skill", "which-shape"])
def test_fresh_router_library_handoff_reaches_clean_ts_outcome_without_skill_install(
    tmp_path: Path, router_name: str
) -> None:
    host = _make_host(tmp_path)
    (host / "src" / "transition.ts").write_text(
        "export const canonicalStatus = 'canonical status';\n", encoding="utf-8"
    )
    (host / "src" / "retired-copy.tsx").write_text(
        "export const CanonicalCopy = () => <p>canonical status</p>;\n", encoding="utf-8"
    )
    for candidate in (host / "src").glob("*candidate.ts"):
        candidate.unlink()
    add = subprocess.run(["git", "add", "-A"], cwd=host, capture_output=True, text=True, check=False)
    assert add.returncode == 0, add.stdout + add.stderr
    source_before = {
        path.relative_to(host).as_posix(): path.read_bytes()
        for path in (host / "src").glob("*")
    }

    installed_routers = host / ".agents" / "skills"
    for default_router in ("which-shape", "which-skill", "which-cleanup"):
        shutil.copytree(
            REPO_ROOT / ".claude" / "skills" / default_router,
            installed_routers / default_router,
        )
    bootstrap = _run(
        installed_routers / "which-skill" / "scripts" / "bootstrap_library.py",
        "--project-root",
        str(host),
        "--source",
        str(REPO_ROOT),
        cwd=host,
    )
    assert bootstrap.returncode == 0, bootstrap.stdout + bootstrap.stderr
    library_root = host.parent / ".engineering-skills" / host.name
    router = installed_routers / router_name
    task = (
        "use rename-concept to assess this TypeScript rename"
        if router_name == "which-skill"
        else "rename the domain concept across the glossary and all TypeScript surfaces"
    )
    router_args = [
        task,
        "--project-root",
        str(host),
        "--source",
        str(REPO_ROOT),
        "--json",
    ]
    if router_name == "which-shape":
        router_args.append("--skip-log")
    routed = _run(
        router / "scripts" / ("match.py" if router_name == "which-skill" else "route.py"),
        *router_args,
        cwd=host,
    )
    assert routed.returncode == 0, routed.stdout + routed.stderr
    routing = json.loads(routed.stdout)
    if router_name == "which-skill":
        assert routing["recommendation"] == "rename-concept"
    else:
        assert routing["recommendation"]["shape"] == "concept-rename"
    assert "install" not in routing
    assert routing["handoff"]["available"] is True
    assert routing["handoff"]["skills"] == [
        "rename-concept",
        "find-concept-divergence",
    ]
    assert routing["handoff"]["default_execution"] == "fresh_non_context_subagent"
    assert "--skill rename-concept" in routing["optional_install"]["command"]
    assert "--skill find-concept-divergence" in routing["optional_install"]["command"]
    installed = library_root / ".claude" / "skills" / "rename-concept"
    companion = library_root / ".claude" / "skills" / "find-concept-divergence"
    assert installed.is_dir()
    assert companion.is_dir()
    assert {
        path.name for path in (host / ".agents" / "skills").iterdir() if path.is_dir()
    } == {"which-shape", "which-skill", "which-cleanup"}

    preflight = subprocess.run(
        ["/bin/sh", "-c", _documented_command(installed, "typescript-preflight")],
        cwd=host,
        capture_output=True,
        text=True,
        check=False,
    )
    assert preflight.returncode == 0, preflight.stdout + preflight.stderr

    assess = _run(
        installed / "scripts" / "assess.py",
        "legacy-status",
        "canonical-status",
        "--project-root",
        str(host),
        "--output",
        str(host / "reports" / "rename-concept" / "assessment.json"),
        cwd=host,
    )
    assert assess.returncode == 0, assess.stdout + assess.stderr
    assert "TypeScript/TSX: RESOLVED — compiler API 5.9.3" in assess.stdout
    assert "RESOLVED — no old/new lexical co-occurrence candidates" in assess.stdout
    assert "COMPLETE — both gate bands green, glossary set, guard present, no live residue." in assess.stdout
    assessment_path = host / "reports" / "rename-concept" / "assessment.json"
    payload = json.loads(assessment_path.read_text(encoding="utf-8"))
    assert payload["verdict"] == "COMPLETE"
    assert payload["typescript_identifier_evidence"]["status"] == "resolved"
    assert payload["typescript_identifier_evidence"]["resolution_diagnostics"] == []


def test_missing_host_typescript_blocks_assessment_without_writing_source(tmp_path: Path) -> None:
    host = _make_host(tmp_path)
    installed = _copy_installed_skills(tmp_path)
    source_before = (host / "src" / "transition.ts").read_bytes()
    assessment = _assessment_path(host, "missing-typescript.json")

    result = _run(
        installed / "scripts" / "assess.py",
        "legacy-status",
        "canonical-status",
        "--project-root",
        str(host),
        "--output",
        str(assessment),
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "TypeScript/TSX: UNAVAILABLE" in result.stdout
    assert "TypeScript compiler evidence unavailable" in result.stdout
    assert json.loads(assessment.read_text(encoding="utf-8"))["typescript_identifier_evidence"]["status"] == "unavailable"
    assert (host / "src" / "transition.ts").read_bytes() == source_before


def test_typescript_resolved_from_an_ancestor_is_not_host_compiler_evidence(tmp_path: Path) -> None:
    host = _make_host(tmp_path)
    installed = _copy_installed_skills(tmp_path)
    _install_host_typescript(host)
    shutil.move(str(host / "node_modules"), tmp_path / "node_modules")
    source_before = (host / "src" / "transition.ts").read_bytes()
    assessment = _assessment_path(host, "ancestor-typescript.json")

    result = _run(
        installed / "scripts" / "assess.py",
        "legacy-status",
        "canonical-status",
        "--project-root",
        str(host),
        "--output",
        str(assessment),
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(assessment.read_text(encoding="utf-8"))
    evidence = payload["typescript_identifier_evidence"]
    assert evidence["status"] == "unavailable"
    assert "outside the project root" in evidence["detail"]
    assert (host / "src" / "transition.ts").read_bytes() == source_before


def test_copied_assessment_never_falls_back_to_source_tree_without_companion(tmp_path: Path) -> None:
    host = _make_host(tmp_path)
    installed = _copy_installed_skills(tmp_path, include_detector=False)
    source_before = (host / "src" / "transition.ts").read_bytes()
    assessment = _assessment_path(host, "missing-companion.json")

    result = _run(
        installed / "scripts" / "assess.py",
        "legacy-status",
        "canonical-status",
        "--project-root",
        str(host),
        "--output",
        str(assessment),
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "INCONCLUSIVE — completeness gate could not run" in result.stdout
    payload = json.loads(assessment.read_text(encoding="utf-8"))
    assert payload["lexical_gate"]["superseded_cooccurrence_files"] is None
    assert payload["typescript_identifier_evidence"] is None
    assert (host / "src" / "transition.ts").read_bytes() == source_before


def test_parse_diagnostic_blocks_typescript_identifier_certification(tmp_path: Path) -> None:
    host = _make_host(tmp_path)
    installed = _copy_installed_skills(tmp_path)
    _install_host_typescript(host)
    (host / "src" / "broken.ts").write_text(
        "export const legacyStatus = ;\nexport const canonicalStatus = 'canonical';\n",
        encoding="utf-8",
    )
    assessment = _assessment_path(host, "parse-error.json")

    result = _run(
        installed / "scripts" / "assess.py",
        "legacy-status",
        "canonical-status",
        "--project-root",
        str(host),
        "--output",
        str(assessment),
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "compiler diagnostics affecting resolution" in result.stdout
    payload = json.loads(assessment.read_text(encoding="utf-8"))
    assert payload["verdict"] == "HALF-APPLIED / INCOMPLETE"
    assert "parse" in {
        diagnostic["kind"] for diagnostic in payload["typescript_identifier_evidence"]["resolution_diagnostics"]
    }


def test_internal_only_concept_identifiers_cannot_supply_v1_authority(tmp_path: Path) -> None:
    host = _make_host(tmp_path)
    installed = _copy_installed_skills(tmp_path)
    _install_host_typescript(host)
    for candidate in (host / "src").glob("*candidate.ts"):
        candidate.unlink()
    (host / "src" / "transition.ts").write_text(
        "const legacyStatus = 1;\nconst canonicalStatus = legacyStatus;\n",
        encoding="utf-8",
    )
    source_before = {
        path.relative_to(host).as_posix(): path.read_bytes()
        for path in (host / "src").glob("*")
    }
    assessment = _assessment_path(host, "internal-only.json")

    result = _run(
        installed / "scripts" / "assess.py",
        "legacy-status",
        "canonical-status",
        "--project-root",
        str(host),
        "--output",
        str(assessment),
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "no resolved new concept declaration" in result.stdout
    payload = json.loads(assessment.read_text(encoding="utf-8"))
    assert payload["verdict"] == "HALF-APPLIED / INCOMPLETE"
    assert "internal_or_unexported_identifier" in {
        candidate["classification"] for candidate in payload["lexical_gate"]["candidate_classifications"]
    }
    assert source_before == {
        path.relative_to(host).as_posix(): path.read_bytes()
        for path in (host / "src").glob("*")
    }
