"""Accepted, refused, copied, and native Kotlin structure proposals."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: frozen product runtime
)
KOTLINC = Path("/opt/homebrew/bin/kotlinc").resolve()
JAVA = Path("/usr/bin/java").resolve()
BASE = ROOT / "tests/fixtures/kotlin-lexical-syntax"
COMMENT_OVERLAY = ROOT / "tests/fixtures/kotlin-comment-map/overlay"
STRUCTURE_OVERLAY = ROOT / "tests/fixtures/kotlin-structure-proposals/overlay"
BUILDER = BASE / "kotlin_fixture_build.py"
MAP = ROOT / ".claude/skills/map-subsystem/scripts/map_kotlin.py"
OMNIBUS = ROOT / ".claude/skills/find-omnibus/scripts/run_kotlin.py"
TOPOLOGY = ROOT / ".claude/skills/find-folder-topology-drift/scripts/detect_kotlin.py"
BOUNDARY = ROOT / ".claude/skills/propose-boundary/scripts/propose_kotlin.py"
FOLDER = (
    ROOT / ".claude/skills/propose-folder-reorganization/scripts/propose_kotlin.py"
)
HELPER = ROOT / ".claude/skills/_kotlin-semantic/kotlin_structure_proposals.py"
UNCERTAINTIES = {
    "overload_ambiguity": "none",
    "reflection_callable_references": "none",
    "delegation": "none",
    "generated_kapt_ksp_plugins": "none",
    "gradle_variants": "none",
    "java_external_callers": "none",
    "runtime_dispatch_equivalence": "not_established",
    "jvm_abi": "separate_approval_required",
}

pytestmark = pytest.mark.skipif(
    not (PYTHON.is_file() and KOTLINC.is_file() and JAVA.is_file()),
    reason="product Python and pinned Kotlin/JVM 2.4.10/JDK 17 are required",
)


def _run(
    *argv: str | Path,
    cwd: Path,
    expected: int = 0,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(item) for item in argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        shell=False,
        timeout=timeout,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    return result


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(payload: dict[str, Any]) -> str:
    rendered = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(rendered.encode()).hexdigest()


def _source_state(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): _sha256(path)
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and not any(
            part in {"reports", ".native-build", ".engineering"}
            for part in path.relative_to(host).parts
        )
    }


def _accepted_sources(host: Path) -> list[dict[str, str]]:
    manifest = _json(host / "kotlin-semantic-project.json")
    paths = [
        "kotlin-project.json",
        "kotlin-semantic-project.json",
        *manifest["sources"],
        *manifest["tests"],
    ]
    return [{"path": path, "sha256": _sha256(host / path)} for path in paths]


def _host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(BASE / "host", host)
    shutil.copytree(COMMENT_OVERLAY, host, dirs_exist_ok=True)
    shutil.copytree(STRUCTURE_OVERLAY, host, dirs_exist_ok=True)
    _run(
        PYTHON,
        "-I",
        "-S",
        BUILDER,
        "--project-root",
        host,
        "--kotlinc",
        KOTLINC,
        "--java",
        JAVA,
        cwd=host,
    )
    return host


def _producers(host: Path) -> tuple[Path, Path, Path]:
    map_path = host / "reports/map/cohort/kotlin-map.json"
    _run(
        PYTHON,
        "-I",
        "-S",
        MAP,
        "--name",
        "cohort",
        "--target",
        "src/main/kotlin/cohort",
        "--project-root",
        ".",
        "--output",
        ".engineering/docs/subsystems/cohort.md",
        "--evidence",
        "reports/map/cohort/kotlin-map.json",
        "--semantic-manifest",
        "kotlin-semantic-project.json",
        "--kotlinc",
        KOTLINC,
        "--java",
        JAVA,
        cwd=host,
    )
    assert _json(map_path)["status"] == "complete"

    omnibus = host / "reports/omnibus/kotlin/findings.json"
    _run(
        PYTHON,
        "-I",
        "-S",
        OMNIBUS,
        "--project-root",
        ".",
        "--kotlinc",
        KOTLINC,
        "--java",
        JAVA,
        "--target",
        "src",
        "--output-dir",
        "reports/omnibus/kotlin",
        "--scout-dir",
        "kotlin-scouts",
        cwd=host,
    )
    assert _json(omnibus)["summary"] == {"confirmed_omnibus": 1}

    topology = host / "reports/folder/findings.json"
    _run(
        PYTHON,
        "-I",
        "-S",
        TOPOLOGY,
        "--project-root",
        ".",
        "--kotlinc",
        KOTLINC,
        "--java",
        JAVA,
        "--kotlin-root",
        "src/main/kotlin",
        "--min-cluster-size",
        "3",
        "--output",
        "reports/folder/detections.jsonl",
        cwd=host,
    )
    assert _json(topology)["outcome"] == "drift-found"
    return omnibus, topology, map_path


def _callers(
    map_payload: dict[str, Any], signatures: set[str], paths: set[str]
) -> list[dict[str, Any]]:
    return [
        row
        for row in map_payload["direct_resolved_calls"]
        if row.get("target_signature") in signatures or row.get("path") in paths
    ]


def _manifest_after(
    host: Path, replacements: dict[str, str], additions: list[str] | None = None
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for manifest_name in ("kotlin-project.json", "kotlin-semantic-project.json"):
        sources = _json(host / manifest_name)["sources"]
        rewritten = [replacements.get(path, path) for path in sources]
        rewritten.extend(additions or [])
        result[manifest_name] = rewritten
    return result


def _acceptance(
    host: Path,
    *,
    consumer: str,
    artifacts: dict[str, Path],
    selection: dict[str, Any],
) -> Path:
    payload: dict[str, Any] = {
        "schema_version": "kotlin-structure-accepted-evidence-v1",
        "consumer": consumer,
        "artifacts": [
            {
                "kind": kind,
                "path": path.relative_to(host).as_posix(),
                "sha256": _sha256(path),
            }
            for kind, path in sorted(artifacts.items())
        ],
        "source_hashes": _accepted_sources(host),
        "selection": selection,
        "human_verdict": {
            "status": "accepted",
            "reviewer": "kotlin-structure-fixture-owner",
            "boundary_verdicts": UNCERTAINTIES,
        },
    }
    payload["acceptance_sha256"] = _canonical(payload)
    return _write(
        host / f"reports/accepted/{consumer}/acceptance.json", payload
    )


def _boundary_acceptance(host: Path, omnibus: Path, map_path: Path) -> Path:
    map_payload = _json(map_path)
    candidate = _json(omnibus)["findings"][0]
    names = set(candidate["clusters"]["exports"])
    declarations = [
        row
        for row in map_payload["qualified_declarations"]
        if row["fq_name"] in names
    ]
    signatures = {row["signature"] for row in declarations}
    source = host / candidate["file"]
    text = source.read_text(encoding="utf-8")
    blocks = [line for line in text.splitlines(keepends=True) if any(
        line.startswith(f"fun {name.rsplit('.', 1)[-1]}(") for name in names
    )]
    assert len(blocks) == len(declarations) == 3
    new_path = "src/main/kotlin/cohort/Exports.kt"
    selection = {
        "candidate_id": candidate["candidate_id"],
        "target": candidate["file"],
        "domain": "exports",
        "declarations": declarations,
        "caller_impact": _callers(map_payload, signatures, {candidate["file"]}),
        "package_impact": {
            "before": "cohort",
            "after": "cohort",
            "jvm_identity_change": False,
        },
        "exact_edits": [
            {
                "path": candidate["file"],
                "before": block,
                "after": "",
                "expected_occurrences": 1,
            }
            for block in blocks
        ],
        "create_files": [
            {"path": new_path, "contents": "package cohort\n\n" + "".join(blocks)}
        ],
        "manifest_sources_after": _manifest_after(host, {}, [new_path]),
        "test_surface": [
            "tests/cohort/KotlinLexicalTest.kt",
            "src/main/kotlin/cohort/Main.kt",
        ],
    }
    return _acceptance(
        host,
        consumer="propose-boundary",
        artifacts={"confirmed-omnibus": omnibus, "kotlin-map": map_path},
        selection=selection,
    )


def _folder_acceptance(host: Path, topology: Path, map_path: Path) -> Path:
    map_payload = _json(map_path)
    finding = next(
        row for row in _json(topology)["findings"] if row["prefix"] == "Billing"
    )
    replacements = {
        path: path.replace("/cohort/", "/cohort/billing/")
        for path in finding["files"]
    }
    selected_paths = set(finding["files"])
    signatures = {
        row["signature"]
        for row in map_payload["qualified_declarations"]
        if row["path"] in selected_paths
    }
    selection = {
        "finding_evidence_sha256": finding["evidence_sha256"],
        "parent": finding["file"],
        "prefix": finding["prefix"],
        "files": finding["files"],
        "project_convention": "group-three-or-more-authored-kotlin-siblings",
        "exact_moves": [
            {"from": source, "to": destination}
            for source, destination in replacements.items()
        ],
        "caller_impact": _callers(map_payload, signatures, selected_paths),
        "package_impact": {
            "before": ["cohort"],
            "after": ["cohort"],
            "package_declarations_changed": False,
        },
        "manifest_sources_after": _manifest_after(host, replacements),
        "test_surface": [
            "tests/cohort/KotlinLexicalTest.kt",
            "src/main/kotlin/cohort/Main.kt",
        ],
    }
    return _acceptance(
        host,
        consumer="propose-folder-reorganization",
        artifacts={"lexical-topology": topology, "kotlin-map": map_path},
        selection=selection,
    )


def _invoke(
    script: Path,
    host: Path,
    producer: Path,
    map_path: Path,
    acceptance: Path,
    name: str,
    *,
    expected: int = 0,
) -> Path:
    skill = script.parents[1].name
    producer_flag = "--omnibus" if skill == "propose-boundary" else "--topology"
    output = host / "reports" / skill / name
    _run(
        PYTHON,
        "-I",
        "-S",
        script,
        "--project-root",
        ".",
        producer_flag,
        producer.relative_to(host),
        "--map-evidence",
        map_path.relative_to(host),
        "--acceptance",
        acceptance.relative_to(host),
        "--output-dir",
        output.relative_to(host),
        "--kotlinc",
        KOTLINC,
        "--java",
        JAVA,
        cwd=host,
        expected=expected,
    )
    return output


def _apply_scope(root: Path, scope: dict[str, Any]) -> None:
    for row in scope.get("exact_moves", []):
        destination = root / row["to"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        (root / row["from"]).replace(destination)
    for row in scope.get("exact_edits", []):
        path = root / row["path"]
        text = path.read_text(encoding="utf-8")
        assert text.count(row["before"]) == row["expected_occurrences"]
        path.write_text(text.replace(row["before"], row["after"]), encoding="utf-8")
    for row in scope.get("create_files", []):
        path = root / row["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(row["contents"], encoding="utf-8")
    for manifest_name, sources in scope["manifest_sources_after"].items():
        path = root / manifest_name
        payload = _json(path)
        payload["sources"] = sources
        _write(path, payload)


def _rehash(path: Path, mutate) -> None:
    payload = _json(path)
    mutate(payload)
    payload.pop("acceptance_sha256", None)
    payload["acceptance_sha256"] = _canonical(payload)
    _write(path, payload)


def test_kotlin_structure_proposals_reach_native_copied_and_refused_outcomes(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    omnibus, topology, map_path = _producers(host)
    boundary_acceptance = _boundary_acceptance(host, omnibus, map_path)
    folder_acceptance = _folder_acceptance(host, topology, map_path)
    before = _source_state(host)

    cases = (
        (BOUNDARY, omnibus, boundary_acceptance, "boundary"),
        (FOLDER, topology, folder_acceptance, "folder"),
    )
    for script, producer, acceptance, name in cases:
        output = _invoke(script, host, producer, map_path, acceptance, "accepted")
        assert {path.name for path in output.iterdir()} == {
            "proposal.md",
            "evidence.json",
            "scope.json",
        }
        evidence = _json(output / "evidence.json")
        scope = _json(output / "scope.json")
        assert evidence["status"] == "ready_for_human_review"
        assert evidence["native_verification"]["current_tree"]["status"] == "passed"
        assert evidence["native_verification"]["disposable_after_tree"]["status"] == "passed"
        assert evidence["source_preservation"]["verified"] is True
        assert scope["read_only"] is True
        assert scope["mutation_authorized"] is False
        assert scope["declarations"]
        assert scope["caller_impact"]
        assert scope["package_impact"]
        assert scope["manifest_sources_after"]
        assert _source_state(host) == before

        independent = tmp_path / f"independent-{name}"
        shutil.copytree(
            host,
            independent,
            ignore=shutil.ignore_patterns(
                "reports", ".native-build", ".engineering"
            ),
        )
        _apply_scope(independent, scope)
        _run(
            PYTHON,
            "-I",
            "-S",
            BUILDER,
            "--project-root",
            independent,
            "--kotlinc",
            KOTLINC,
            "--java",
            JAVA,
            cwd=independent,
        )

        copied = tmp_path / f"installed/{script.parents[1].name}/scripts/{script.name}"
        copied.parent.mkdir(parents=True)
        shutil.copy2(script, copied)
        copied_helper = copied.parents[2] / "_kotlin-semantic" / HELPER.name
        copied_helper.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HELPER, copied_helper)
        copied_output = _invoke(
            copied, host, producer, map_path, acceptance, "copied"
        )
        assert _json(copied_output / "evidence.json")["status"] == (
            "ready_for_human_review"
        )
        copied_text = copied.read_text(encoding="utf-8")
        assert str(ROOT) not in copied_text
        assert "run_kotlin.py" not in copied_text
        assert "detect_kotlin.py" not in copied_text
        assert "map_kotlin.py" not in copied_text

    original = _json(boundary_acceptance)
    for boundary in UNCERTAINTIES:
        _rehash(
            boundary_acceptance,
            lambda payload, key=boundary: payload["human_verdict"][
                "boundary_verdicts"
            ].update({key: "unknown"}),
        )
        refused = _invoke(
            BOUNDARY,
            host,
            omnibus,
            map_path,
            boundary_acceptance,
            f"refused-{boundary}",
            expected=2,
        )
        assert _json(refused / "evidence.json")["failure_kind"] == (
            "kotlin_uncertainty_unresolved"
        )
        _write(boundary_acceptance, original)

    _rehash(
        folder_acceptance,
        lambda payload: payload["selection"].update(project_convention=""),
    )
    refused = _invoke(
        FOLDER,
        host,
        topology,
        map_path,
        folder_acceptance,
        "refused-convention",
        expected=2,
    )
    assert _json(refused / "evidence.json")["failure_kind"] == (
        "project_convention_required"
    )
    assert _source_state(host) == before
