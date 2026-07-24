"""Five bounded C17 lexical/filesystem consumers over one copied fact closure."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "c-lexical-filesystem"
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: required frozen P7 runtime
)
CLANG = Path(shutil.which("clang") or "")
MAKE = Path(shutil.which("make") or "")
PROVIDER = ROOT / ".claude" / "skills" / "_c" / "c_lexical_facts.py"
SCRIPTS = {
    "adapt-project": ROOT / ".claude" / "skills" / "adapt-project" / "scripts" / "discover_c.py",
    "explain-code": ROOT / ".claude" / "skills" / "explain-code" / "scripts" / "explain_c.py",
    "find-concept-divergence": ROOT
    / ".claude"
    / "skills"
    / "find-concept-divergence"
    / "scripts"
    / "scan_c.py",
    "find-duplication": ROOT / ".claude" / "skills" / "find-duplication" / "scripts" / "run_c.py",
    "find-folder-topology-drift": ROOT
    / ".claude"
    / "skills"
    / "find-folder-topology-drift"
    / "scripts"
    / "detect_c.py",
}
pytestmark = pytest.mark.skipif(
    not all(path.is_file() for path in (PYTHON, CLANG, MAKE)),
    reason="Apple Clang 21, Make, and frozen product Python are required",
)


def _run(*args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE / "host", host)
    (host / "linked-external").symlink_to(FIXTURE / "symlink-target", target_is_directory=True)
    return host


def _prepare(host: Path) -> None:
    result = _run(str(MAKE), "clean", "compile-db", f"CC={CLANG}", cwd=host)
    assert result.returncode == 0, result.stdout + result.stderr


def _native(host: Path) -> None:
    result = _run(
        str(MAKE),
        "test",
        f"CC={CLANG}",
        cwd=host,
        env={
            **os.environ,
            "ALL_PROXY": "http://127.0.0.1:9",
            "http_proxy": "http://127.0.0.1:9",
            "https_proxy": "http://127.0.0.1:9",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "c-native-test:ok\n" in result.stdout
    smoke = _run(str(host / ".native-build" / "c-lexical-smoke"), cwd=host)
    assert smoke.returncode == 0
    assert smoke.stdout == "c-lexical-smoke:132\n"


def _source_hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and (path.suffix in {".c", ".i", ".h", ".inc"} or path.name == "Makefile")
        and ".native-build" not in path.relative_to(host).parts
    }


def _install_closures(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    install = tmp_path / "installed" / ".agents" / "skills"
    copied_provider = install / "_c" / PROVIDER.name
    copied_provider.parent.mkdir(parents=True)
    shutil.copy2(PROVIDER, copied_provider)
    copied: dict[str, Path] = {}
    for skill, source in SCRIPTS.items():
        destination = install / skill / "scripts" / source.name
        destination.parent.mkdir(parents=True)
        shutil.copy2(source, destination)
        copied[skill] = destination
    return copied_provider, copied


def _invoke(
    skill: str,
    script: Path,
    host: Path,
    *,
    clang: Path = CLANG,
    make: Path = MAKE,
    min_cluster_size: int = 3,
) -> subprocess.CompletedProcess[str]:
    base = (
        str(PYTHON),
        "-I",
        "-S",
        str(script),
        "--project-root",
        str(host),
        "--clang",
        str(clang),
        "--make",
        str(make),
        "--test-target",
        "test",
        "--smoke",
        ".native-build/c-lexical-smoke",
    )
    if skill == "adapt-project":
        args = (*base, "--output-dir", str(host / "reports" / "adapt"), ".")
    elif skill == "explain-code":
        args = (*base, "--target", ".", "--output", str(host / "reports" / "explain" / "c.md"))
    elif skill == "find-concept-divergence":
        args = (
            *base,
            "--glossary",
            str(host / ".claude" / "contracts" / "concepts.yaml"),
            "--output",
            str(host / "reports" / "concept" / "findings.jsonl"),
            "--report",
            str(host / "reports" / "concept" / "report.md"),
            ".",
        )
    elif skill == "find-duplication":
        args = (*base, "--target", "src", "--output-dir", str(host / "reports" / "duplication"))
    else:
        args = (
            *base,
            "--c-root",
            "src",
            "--min-cluster-size",
            str(min_cluster_size),
            "--output",
            str(host / "reports" / "folder" / "detections.jsonl"),
        )
    return _run(*args, cwd=host)


def _artifact(skill: str, host: Path) -> dict:
    paths = {
        "adapt-project": host / "reports" / "adapt" / "adapter.json",
        "explain-code": host / "reports" / "explain" / "c" / "targets.json",
        "find-concept-divergence": host / "reports" / "concept" / "findings.json",
        "find-duplication": host / "reports" / "duplication" / "findings.json",
        "find-folder-topology-drift": host / "reports" / "folder" / "findings.json",
    }
    return json.loads(paths[skill].read_text(encoding="utf-8"))


def _status(skill: str, host: Path) -> str:
    payload = _artifact(skill, host)
    return payload.get("status") or payload.get("scan_meta", {}).get("status")


def test_c_five_copied_value_outcomes_roles_preservation_and_native(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _prepare(host)
    _native(host)
    before = _source_hashes(host)
    copied_provider, copied = _install_closures(tmp_path)

    results = {skill: _invoke(skill, script, host) for skill, script in copied.items()}
    assert all(result.returncode == 0 for result in results.values()), {
        skill: result.stdout + result.stderr for skill, result in results.items()
    }

    adapter = _artifact("adapt-project", host)
    assert adapter["status"] == "complete"
    assert adapter["stack"] == {
        "build_systems": ["make"],
        "frameworks": [],
        "languages": ["c"],
        "package_managers": [],
    }
    assert adapter["source_roots"] == [
        {
            "c_translation_units": 5,
            "compiler_owned_headers": 2,
            "path": ".",
            "source_languages": ["c"],
        }
    ]
    assert (host / "reports" / "adapt" / "adapter.yml").is_file()
    assert "do not endorse" in adapter["standardization"]["cautions"][0]

    explained = _artifact("explain-code", host)
    symbols = {row["symbol"] for row in explained["selected"]}
    assert {"billing_state", "billing_invoice", "billing_pending_total"} <= symbols
    assert "printf" not in symbols
    assert len(list((host / "reports" / "explain" / "c" / "annotations").glob("*.md"))) == len(
        explained["selected"]
    )
    declaration = next(row for row in explained["selected"] if row["symbol"] == "billing_invoice")
    source = (host / declaration["file"]).read_bytes()
    spelling = source[declaration["span"]["start_byte"] : declaration["span"]["end_byte"]]
    assert hashlib.sha256(spelling).hexdigest() == declaration["spelling_sha256"]

    concept = _artifact("find-concept-divergence", host)
    assert concept["outcome"] == "drift-found"
    assert [(row["file"], row["term"]) for row in concept["findings"]] == [
        ("src/billing_parser.c", "cancelled_order")
    ]
    concept_hit = concept["findings"][0]
    source = (host / concept_hit["file"]).read_bytes()
    assert source[concept_hit["span"]["start_byte"] : concept_hit["span"]["end_byte"]] == b"cancelled_order"

    duplication = _artifact("find-duplication", host)
    assert len(duplication["findings"]) == 1
    sites = duplication["findings"][0]["sites"]
    assert {site["symbol"] for site in sites} == {"billing_pending_total", "billing_queued_total"}
    assert "not semantic or behavioral equivalence" in (
        host / "reports" / "duplication" / "triage.md"
    ).read_text()

    folder = _artifact("find-folder-topology-drift", host)
    assert folder["outcome"] == "drift-found"
    assert folder["findings"] == [
        {
            "count": 3,
            "evidence_sha256": hashlib.sha256(
                b"src/billing_parser.c\nsrc/billing_types.c\nsrc/billing_validator.c"
            ).hexdigest(),
            "file": "src",
            "files": [
                "src/billing_parser.c",
                "src/billing_types.c",
                "src/billing_validator.c",
            ],
            "language": "c",
            "pattern": "flat_prefix_cluster",
            "prefix": "billing",
            "recommendation": (
                "Human triage only; compiler ownership, include/build impact, framework layout, and move safety are unresolved."
            ),
        }
    ]

    analyses = [
        adapter["analysis"]["c"],
        explained["analysis"]["c"],
        concept["analysis"]["c"],
        duplication["scan_meta"]["analysis"],
        folder["analysis"]["c"],
    ]
    assert len({analysis["source_manifest_sha256"] for analysis in analyses}) == 1
    for analysis in analyses:
        assert analysis["compile_database"]["status"] == "valid"
        assert analysis["native"]["test"]["status"] == "passed"
        assert analysis["native"]["smoke"]["stdout"] == "c-lexical-smoke:132\n"
        assert analysis["source_preserved"] is True
        assert any("not semantic or behavioral equivalence" in limit for limit in analysis["limits"])
        roles = {row["file"]: row.get("reason", row["role"]) for row in analysis["inventory"]}
        assert roles["tests/billing_alpha.c"] == "test"
        assert roles["generated/billing_alpha.c"] == "generated"
        assert roles["vendor/example/billing_alpha.c"] == "vendor"
        assert roles["build/billing_alpha.c"] == "build"
        assert roles["reports/decoys/billing_alpha.c"] == "report"
        assert roles["src/wire_generated.c"] == "generated-marker"
        assert roles["include/orphan.h"] == "ambiguous-header"
        assert roles["linked-external"] == "symlink"
        assert roles["Makefile"] == "configuration"
    assert _source_hashes(host) == before
    assert copied_provider.is_file()
    for script in copied.values():
        text = script.read_text(encoding="utf-8")
        assert "c_lexical_facts" in text
        assert str(ROOT) not in text


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
def test_each_consumer_missing_tool_clears_stale_and_recovers(skill: str, tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _prepare(host)
    _, copied = _install_closures(tmp_path)
    valid = _invoke(skill, copied[skill], host)
    assert valid.returncode == 0, valid.stdout + valid.stderr
    assert _status(skill, host) == "complete"

    missing = _invoke(skill, copied[skill], host, clang=tmp_path / "missing-clang")
    assert missing.returncode == 2
    assert _status(skill, host) == "partial"
    payload = _artifact(skill, host)
    assert payload.get("findings", []) == []
    assert payload.get("selected", []) == []

    recovered = _invoke(skill, copied[skill], host)
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert _status(skill, host) == "complete"


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
def test_each_consumer_malformed_source_is_partial_and_preserved(skill: str, tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    shutil.copy2(FIXTURE / "malformed" / "Broken.c", host / "src" / "Broken.c")
    _prepare(host)
    before = _source_hashes(host)
    _, copied = _install_closures(tmp_path)

    result = _invoke(skill, copied[skill], host)

    assert result.returncode == 2, result.stdout + result.stderr
    assert _status(skill, host) == "partial"
    payload = _artifact(skill, host)
    analysis = payload.get("analysis", {}).get("c") or payload["scan_meta"]["analysis"]
    assert analysis["failure_kind"] == "compile-database-incomplete"
    assert _source_hashes(host) == before


def test_detectors_emit_clean_only_from_complete_evidence(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    parser = host / "src" / "billing_parser.c"
    parser.write_text(parser.read_text().replace("cancelled_order", "cancelled_invoice"))
    validator = host / "src" / "billing_validator.c"
    validator.write_text(
        validator.read_text().replace("subtotal + service_fee", "(subtotal + service_fee) + 0")
    )
    _prepare(host)
    _, copied = _install_closures(tmp_path)

    concept = _invoke("find-concept-divergence", copied["find-concept-divergence"], host)
    duplication = _invoke("find-duplication", copied["find-duplication"], host)
    folder = _invoke(
        "find-folder-topology-drift",
        copied["find-folder-topology-drift"],
        host,
        min_cluster_size=4,
    )

    assert concept.returncode == duplication.returncode == folder.returncode == 0
    assert _artifact("find-concept-divergence", host)["outcome"] == "clean-within-complete"
    assert _artifact("find-duplication", host)["findings"] == []
    assert _artifact("find-folder-topology-drift", host)["outcome"] == "clean"


def _fake_make(path: Path, *, test_exit: int) -> Path:
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        "  printf '%s\\n' 'GNU Make 3.81'\n"
        "  exit 0\n"
        "fi\n"
        f"exit {test_exit}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_compile_database_and_native_failure_states_replace_artifacts(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _prepare(host)
    _, copied = _install_closures(tmp_path)
    valid = _invoke("adapt-project", copied["adapt-project"], host)
    assert valid.returncode == 0

    failing_make = _fake_make(tmp_path / "failing-make", test_exit=9)
    failed = _invoke("adapt-project", copied["adapt-project"], host, make=failing_make)
    assert failed.returncode == 1
    failed_payload = _artifact("adapt-project", host)
    assert failed_payload["status"] == "failed"
    assert failed_payload["analysis"]["c"]["failure_kind"] == "native-test-failed"
    assert failed_payload["source_roots"][0]["c_translation_units"] == 0

    (host / "compile_commands.json").write_text("{", encoding="utf-8")
    malformed = _invoke("adapt-project", copied["adapt-project"], host)
    assert malformed.returncode == 1
    malformed_payload = _artifact("adapt-project", host)
    assert malformed_payload["analysis"]["c"]["failure_kind"] == "compile-database-malformed"

    (host / "compile_commands.json").unlink()
    missing = _invoke("adapt-project", copied["adapt-project"], host)
    assert missing.returncode == 2
    assert _artifact("adapt-project", host)["analysis"]["c"]["failure_kind"] == "compile-database-missing"


def test_shared_provider_deletion_and_caller_knowledge_boundary() -> None:
    provider = PROVIDER.read_text(encoding="utf-8")
    for policy in (
        "compile_commands.json",
        "-std=c17",
        "source_manifest_sha256",
        "generated-marker",
        "ambiguous-header",
        "symlink",
        "native-test-failed",
    ):
        assert policy in provider
    for script in SCRIPTS.values():
        text = script.read_text(encoding="utf-8")
        assert "collect_snapshot" in text
        assert "compile_commands.json" not in text
        assert "generated-marker" not in text
        assert "native-test-failed" not in text
