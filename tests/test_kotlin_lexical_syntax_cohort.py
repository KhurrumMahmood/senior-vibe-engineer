"""Outcome and copied-closure contract for Kotlin lexical/syntax skills."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/kotlin-lexical-syntax"
BUILDER = FIXTURE / "kotlin_fixture_build.py"
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: frozen product runtime
)
KOTLINC = Path("/opt/homebrew/bin/kotlinc").resolve()
JAVA = Path("/usr/bin/java").resolve()
PROVIDER = ROOT / ".claude/skills/_kotlin/kotlin_facts.py"
SCRIPTS = {
    "adapt": ROOT / ".claude/skills/adapt-project/scripts/discover_kotlin.py",
    "explain": ROOT / ".claude/skills/explain-code/scripts/explain_kotlin.py",
    "concept": ROOT / ".claude/skills/find-concept-divergence/scripts/scan_kotlin.py",
    "duplication": ROOT / ".claude/skills/find-duplication/scripts/run_kotlin.py",
    "folder": ROOT / ".claude/skills/find-folder-topology-drift/scripts/detect_kotlin.py",
    "audit": ROOT / ".claude/skills/audit-decisions/scripts/audit_kotlin.py",
    "complexity": ROOT / ".claude/skills/find-complexity-hotspots/scripts/run_kotlin.py",
    "omnibus": ROOT / ".claude/skills/find-omnibus/scripts/run_kotlin.py",
    "standards": ROOT / ".claude/skills/find-standard-gaps/scripts/scan_coverage_kotlin.py",
}


pytestmark = pytest.mark.skipif(
    not (PYTHON.is_file() and KOTLINC.is_file() and JAVA.is_file()),
    reason="the pinned product Python, Kotlin/JVM 2.4.10, and JDK 17 are required",
)


def _run(*argv: str, cwd: Path, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, check=False,
        shell=False, timeout=timeout,
    )


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE / "host", host)
    built = _run(
        str(PYTHON), "-I", "-S", str(BUILDER),
        "--project-root", str(host), "--kotlinc", str(KOTLINC),
        "--java", str(JAVA), cwd=tmp_path,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    evidence = json.loads(
        (host / ".native-build/kotlin-build-evidence.json").read_text(encoding="utf-8")
    )
    assert evidence["checks"]["test"]["stdout"] == "kotlin-lexical-tests:ok\n"
    assert evidence["checks"]["smoke"]["stdout"] == "kotlin-lexical:12:queued\n"
    return host


def _state(host: Path) -> dict[str, tuple[str, str]]:
    rows: dict[str, tuple[str, str]] = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if relative.parts and relative.parts[0] in {"reports", ".native-build"}:
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = ("symlink", os.readlink(path))
        elif path.is_file():
            rows[relative.as_posix()] = (
                "file", hashlib.sha256(path.read_bytes()).hexdigest()
            )
    return rows


def _provider(
    host: Path, *, script: Path = PROVIDER, kotlinc: Path = KOTLINC,
) -> subprocess.CompletedProcess[str]:
    return _run(
        str(PYTHON), "-I", "-S", str(script), "--project-root", str(host),
        "--target", ".", "--kotlinc", str(kotlinc), "--java", str(JAVA),
        "--json", cwd=host,
    )


def _output(host: Path, kind: str) -> Path:
    return host / "reports" / kind


def _invoke(
    host: Path, kind: str, *, script: Path | None = None, cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    selected = script or SCRIPTS[kind]
    base = [
        str(PYTHON), "-I", "-S", str(selected), "--project-root", str(host),
        "--kotlinc", str(KOTLINC), "--java", str(JAVA),
    ]
    output = _output(host, kind)
    if kind == "adapt":
        base.extend(["--output-dir", str(output), "."])
    elif kind == "explain":
        base.extend(["--target", ".", "--output", str(output / "kotlin.md")])
    elif kind == "concept":
        base.extend([
            "--glossary", str(host / ".claude/contracts/concepts.json"),
            "--output", str(output / "findings.jsonl"),
            "--report", str(output / "report.md"), ".",
        ])
    elif kind == "duplication":
        base.extend(["--target", "src", "--output-dir", str(output)])
    elif kind == "folder":
        base.extend([
            "--kotlin-root", "src/main/kotlin/cohort", "--min-cluster-size", "3",
            "--output", str(output / "detections.jsonl"),
        ])
    elif kind in {"audit", "complexity"}:
        base.extend([
            "--target", "." if kind == "audit" else "src",
            "--output-dir", str(output),
        ])
    elif kind == "omnibus":
        base.extend([
            "--target", "src", "--output-dir", str(output),
            "--scout-dir", str(host / "kotlin-scouts"),
        ])
    elif kind == "standards":
        base.extend([
            "--target", "src", "--output-dir", str(output),
            "--ideas", str(host / "standards-kotlin.json"),
        ])
    return _run(*base, cwd=cwd or host)


def _artifact(host: Path, kind: str) -> dict:
    names = {
        "adapt": "adapter.json",
        "explain": "kotlin/targets.json",
        "concept": "findings.json",
        "duplication": "findings.json",
        "folder": "findings.json",
        "audit": "raw-drift.json",
        "complexity": "findings.json",
        "omnibus": "findings.json",
        "standards": "coverage.json",
    }
    return json.loads((_output(host, kind) / names[kind]).read_text(encoding="utf-8"))


def test_kotlin_provider_reports_only_bounded_source_syntax(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    (host / "linked-external").symlink_to(FIXTURE / "symlink-target", target_is_directory=True)
    before = _state(host)

    result = _provider(host)

    assert result.returncode == 0, result.stdout + result.stderr
    facts = json.loads(result.stdout)
    assert facts["status"] == "complete"
    assert facts["language"] == "kotlin"
    assert facts["syntax_standard"] == "Kotlin/JVM 2.4 source syntax"
    assert facts["analyzer"] == "kotlinc-jvm17-diagnostic+kotlin-source-tokenizer"
    assert facts["native_evidence"]["state"] == "valid-current-and-replayed"
    assert facts["native_evidence"]["test_stdout"] == "kotlin-lexical-tests:ok\n"
    assert facts["native_evidence"]["smoke_stdout"] == "kotlin-lexical:12:queued\n"
    inventory = {row["file"]: row for row in facts["inventory"]}
    assert inventory["src/main/kotlin/cohort/BillingModel.kt"]["role"] == "source"
    assert inventory["tests/cohort/KotlinLexicalTest.kt"]["role"] == "test"
    assert inventory["generated/Generated.kt"]["role"] == "generated"
    assert inventory["vendor/Vendor.kt"]["role"] == "vendor"
    assert inventory["build/Build.kt"]["role"] == "build"
    assert inventory["scripts/Tooling.kt"]["role"] == "tooling"
    assert "foreign/Foreign.java" not in inventory
    assert "linked-external/External.kt" not in inventory
    assert all(row["file"].endswith(".kt") for row in facts["inventory"])
    declarations = [row for file in facts["files"] for row in file["declarations"]]
    assert any(row["kind"] == "data-class" and row["name"] == "Invoice" for row in declarations)
    assert any(row["kind"] == "sealed-interface" and row["name"] == "BillingOutcome" for row in declarations)
    labels = [row for row in declarations if row["name"] == "label"]
    assert labels[0]["extension_receiver"] == "Invoice"
    totals = [row for row in declarations if row["name"] == "total"]
    assert len({row["signature"] for row in totals}) == 2
    assert any(token["text"] == "cancelledInvoice" for file in facts["files"] for token in file["identifier_tokens"])
    assert facts["boundaries"]["resolved_symbols"] == "not available"
    assert facts["boundaries"]["resolved_calls"] == "not available"
    assert facts["boundaries"]["overrides"] == "not analyzed"
    assert facts["boundaries"]["data_flow"] == "not analyzed"
    assert facts["boundaries"]["compiler_ir"] == "not consumed"
    assert facts["source_manifest"]["preserved"] is True
    assert _state(host) == before


def test_nine_kotlin_consumers_emit_distinct_final_artifacts(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)

    results = {kind: _invoke(host, kind) for kind in SCRIPTS}

    assert {kind: result.returncode for kind, result in results.items()} == {
        "adapt": 0, "explain": 0, "concept": 0, "duplication": 0,
        "folder": 0, "audit": 1, "complexity": 0, "omnibus": 0,
        "standards": 1,
    }, {kind: result.stdout + result.stderr for kind, result in results.items()}
    adapter = _artifact(host, "adapt")
    assert adapter["status"] == "complete"
    assert adapter["stack"]["languages"] == ["kotlin"]
    assert adapter["source_roots"][0]["manifest_sources"] == 7
    assert adapter["source_roots"][0]["manifest_tests"] == 1

    explained = _artifact(host, "explain")
    totals = [row for row in explained["selected"] if row["name"] == "total"]
    assert len({row["signature"] for row in totals}) == 2
    assert any(row["extension_receiver"] == "Invoice" for row in explained["selected"])

    concept = _artifact(host, "concept")
    assert concept["outcome"] == "drift-found"
    assert [(row["file"], row["term"]) for row in concept["findings"]] == [
        ("src/main/kotlin/cohort/BillingParser.kt", "cancelledInvoice")
    ]

    duplication = _artifact(host, "duplication")
    assert len(duplication["findings"]) == 1
    assert {site["qualified_name"] for site in duplication["findings"][0]["sites"]} == {
        "cohort.pendingBillingTotal", "cohort.queuedBillingTotal"
    }

    folder = _artifact(host, "folder")
    assert folder["outcome"] == "drift-found"
    assert folder["findings"][0]["files"] == [
        "src/main/kotlin/cohort/BillingModel.kt",
        "src/main/kotlin/cohort/BillingParser.kt",
        "src/main/kotlin/cohort/BillingTypes.kt",
        "src/main/kotlin/cohort/BillingValidator.kt",
    ]

    audit = _artifact(host, "audit")
    references = {(row["id"], row["resolved"]) for row in audit["references"]}
    assert {("0001", True), ("9999", False)} <= references
    assert "code-ref-orphan" in {row["symptom"] for row in audit["drift"]}

    complexity = _artifact(host, "complexity")
    assert [(row["qualified_name"], row["branch_score"]) for row in complexity["findings"]] == [
        ("cohort.routeInvoice", 8)
    ]

    omnibus = _artifact(host, "omnibus")
    assert omnibus["status"] == "complete"
    assert omnibus["summary"] == {"confirmed_omnibus": 1}
    assert omnibus["findings"][0]["file"] == "src/main/kotlin/cohort/Omnibus.kt"
    assert omnibus["findings"][0]["scout_verdict"] == "explicit"

    standards = _artifact(host, "standards")
    standard = standards["standards"][0]
    assert (standard["situation_sites"], standard["gap_count"], standard["coverage_percent"]) == (2, 1, 50.0)
    assert [(row["file"], row["function"]) for row in standard["gaps"]] == [
        ("src/main/kotlin/cohort/Syntax.kt", "cohort.unhandledParse")
    ]
    analyses = [
        adapter["analysis"]["kotlin"], explained["analysis"]["kotlin"],
        concept["analysis"]["kotlin"], duplication["analysis"]["kotlin"],
        folder["analysis"]["kotlin"], audit["analysis"]["kotlin"],
        complexity["analysis"]["kotlin"], omnibus["analysis"]["kotlin"],
        standards["analysis"]["kotlin"],
    ]
    assert len({row["source_manifest"]["before_sha256"] for row in analyses}) == 1
    assert all(row["source_manifest"]["preserved"] for row in analyses)
    assert _state(host) == before


@pytest.mark.parametrize("kind", sorted(SCRIPTS))
def test_each_kotlin_consumer_runs_from_exact_copied_closure(
    tmp_path: Path, kind: str,
) -> None:
    host = _copy_host(tmp_path, kind)
    installed = host / ".agents/skills"
    shutil.copytree(PROVIDER.parent, installed / "_kotlin")
    copied_skill = installed / SCRIPTS[kind].parents[1].name
    shutil.copytree(SCRIPTS[kind].parents[1], copied_skill)
    copied = copied_skill / "scripts" / SCRIPTS[kind].name
    outside = tmp_path / f"outside-{kind}"
    outside.mkdir()

    result = _invoke(host, kind, script=copied, cwd=outside)

    assert result.returncode in {0, 1}, result.stdout + result.stderr
    assert _artifact(host, kind)["status"] == "complete"
    assert str(ROOT) not in copied.read_text(encoding="utf-8")


def test_kotlin_refusal_lifecycle_replaces_artifacts_and_recovers(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    first = _invoke(host, "complexity")
    assert first.returncode == 0
    assert _artifact(host, "complexity")["status"] == "complete"

    source = host / "src/main/kotlin/cohort/Syntax.kt"
    pristine = source.read_text(encoding="utf-8")
    source.write_text("package cohort\nfun broken( {\n", encoding="utf-8")
    failed = _invoke(host, "complexity")
    assert failed.returncode == 2
    payload = _artifact(host, "complexity")
    assert payload["status"] == "failed"
    assert payload["findings"] == []
    assert payload["failure_kind"] == "kotlinc_diagnostic_failed"

    missing = _provider(host, kotlinc=host / "missing-kotlinc")
    missing_payload = json.loads(missing.stdout)
    assert missing.returncode == 0
    assert missing_payload["status"] == "unsupported"
    assert missing_payload["failure_kind"] == "kotlinc_tool_missing"

    source.write_text(pristine, encoding="utf-8")
    rebuilt = _run(
        str(PYTHON), "-I", "-S", str(BUILDER),
        "--project-root", str(host), "--kotlinc", str(KOTLINC),
        "--java", str(JAVA), cwd=tmp_path,
    )
    assert rebuilt.returncode == 0, rebuilt.stdout + rebuilt.stderr
    recovered = _invoke(host, "complexity")
    assert recovered.returncode == 0
    assert _artifact(host, "complexity")["status"] == "complete"

    manifest = host / "kotlin-project.json"
    manifest.write_text("{}\n", encoding="utf-8")
    refused = _invoke(host, "complexity")
    refused_payload = _artifact(host, "complexity")
    assert refused.returncode == 2
    assert refused_payload["status"] == "failed"
    assert refused_payload["failure_kind"] == "kotlin_project_manifest_invalid"


def test_kotlin_malformed_source_fails_direct_kotlinc_diagnostic(tmp_path: Path) -> None:
    completed = _run(
        str(KOTLINC), "-jvm-target", "17", "-Werror", "-d",
        str(tmp_path / "broken.jar"), str(FIXTURE / "malformed/Broken.kt"),
        cwd=tmp_path,
    )

    assert completed.returncode != 0
    assert "error:" in completed.stderr
