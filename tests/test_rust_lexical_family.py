"""Five Rust lexical/filesystem consumers over one copied fact closure."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "rust-lexical-family"
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: required frozen P7 runtime
)
RUSTC = Path.home() / ".local" / "bin" / "rustc"
CARGO = Path.home() / ".local" / "bin" / "cargo"
RUSTFMT = Path.home() / ".local" / "bin" / "rustfmt"
COMMON = ROOT / ".claude" / "skills" / "_rust" / "rust_lexical_facts.py"
SCRIPTS = {
    "adapt-project": ROOT / ".claude" / "skills" / "adapt-project" / "scripts" / "discover_rust.py",
    "explain-code": ROOT / ".claude" / "skills" / "explain-code" / "scripts" / "explain_rust.py",
    "find-concept-divergence": ROOT
    / ".claude"
    / "skills"
    / "find-concept-divergence"
    / "scripts"
    / "scan_rust.py",
    "find-duplication": ROOT
    / ".claude"
    / "skills"
    / "find-duplication"
    / "scripts"
    / "run_rust.py",
    "find-folder-topology-drift": ROOT
    / ".claude"
    / "skills"
    / "find-folder-topology-drift"
    / "scripts"
    / "detect_rust.py",
}
pytestmark = pytest.mark.skipif(
    not all(path.is_file() for path in (RUSTC, CARGO, RUSTFMT)),
    reason="Rust 1.97.1 pilot toolchain is required",
)


def _run(
    *args: str, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _copy_host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
    (host / "linked-external").symlink_to(FIXTURE / "symlink-target", target_is_directory=True)
    return host


def _hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and "reports" not in path.relative_to(host).parts
    }


def _native(host: Path, tmp_path: Path) -> None:
    env = os.environ.copy()
    env.update(
        CARGO_NET_OFFLINE="true",
        CARGO_TARGET_DIR=str(tmp_path / "native-target"),
        CARGO_HOME=str(tmp_path / "native-cargo-home"),
    )
    commands = (
        ("metadata", "--format-version", "1", "--locked", "--offline", "--no-deps"),
        ("check", "--locked", "--offline", "--workspace", "--all-targets", "--all-features"),
        ("test", "--locked", "--offline", "--workspace", "--all-targets", "--all-features"),
        ("fmt", "--all", "--", "--check"),
    )
    for command in commands:
        result = _run(str(CARGO), *command, cwd=host, env=env)
        assert result.returncode == 0, result.stdout + result.stderr


def _install_closures(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    install = tmp_path / "installed" / ".agents" / "skills"
    common = install / "_rust" / COMMON.name
    common.parent.mkdir(parents=True)
    shutil.copy2(COMMON, common)
    copied: dict[str, Path] = {}
    for skill, source in SCRIPTS.items():
        destination = install / skill / "scripts" / source.name
        destination.parent.mkdir(parents=True)
        shutil.copy2(source, destination)
        copied[skill] = destination
    return common, copied


def _tool_args(*, cargo: Path = CARGO) -> tuple[str, ...]:
    return (
        "--rustc",
        str(RUSTC),
        "--cargo",
        str(cargo),
        "--rustfmt",
        str(RUSTFMT),
    )


def _invoke(
    skill: str, script: Path, host: Path, *, cargo: Path = CARGO
) -> subprocess.CompletedProcess[str]:
    base = (
        str(PYTHON),
        "-I",
        "-S",
        str(script),
        "--project-root",
        str(host),
        *_tool_args(cargo=cargo),
    )
    if skill == "adapt-project":
        args = (*base, "--output-dir", str(host / "reports" / "adapt"), ".")
    elif skill == "explain-code":
        args = (
            *base,
            "--target",
            "src",
            "--output",
            str(host / "reports" / "explain" / "rust.md"),
        )
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
            "--rust-root",
            "src",
            "--output",
            str(host / "reports" / "folder" / "detections.jsonl"),
        )
    return _run(*args, cwd=host)


def _status(skill: str, host: Path) -> str:
    paths = {
        "adapt-project": host / "reports" / "adapt" / "adapter.json",
        "explain-code": host / "reports" / "explain" / "rust" / "targets.json",
        "find-concept-divergence": host / "reports" / "concept" / "findings.json",
        "find-duplication": host / "reports" / "duplication" / "findings.json",
        "find-folder-topology-drift": host / "reports" / "folder" / "findings.json",
    }
    payload = json.loads(paths[skill].read_text(encoding="utf-8"))
    return payload.get("status") or payload.get("scan_meta", {}).get("status")


def test_rust_five_value_outcomes_copied_closures_roles_and_native(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _native(host, tmp_path)
    before = _hashes(host)
    copied_common, copied = _install_closures(tmp_path)

    results = {skill: _invoke(skill, script, host) for skill, script in copied.items()}
    assert all(result.returncode == 0 for result in results.values()), {
        skill: result.stdout + result.stderr for skill, result in results.items()
    }

    adapter = json.loads((host / "reports" / "adapt" / "adapter.json").read_text())
    assert adapter["status"] == "complete"
    assert adapter["stack"]["languages"] == ["rust"]
    assert adapter["stack"]["package_managers"] == ["cargo"]
    assert adapter["source_roots"][0]["rust_files"] == 4
    assert adapter["commands"]["test"] == [
        "cargo test --locked --offline --workspace --all-targets --all-features"
    ]
    assert (host / "reports" / "adapt" / "adapter.yml").is_file()
    evidence = json.loads((host / "reports" / "adapt" / "evidence.json").read_text())
    assert evidence["evidence"] == {"adapter": "adapter.yml", "report": "report.md"}

    targets = json.loads((host / "reports" / "explain" / "rust" / "targets.json").read_text())
    assert targets["status"] == "complete"
    symbols = {row["symbol"] for row in targets["selected"]}
    assert {"Invoice", "InvoiceState", "normalize_invoice"} <= symbols
    assert "InternalSequence" not in symbols
    assert len(list((host / "reports" / "explain" / "rust" / "annotations").glob("*.md"))) == len(
        targets["selected"]
    )
    explanation = (host / "reports" / "explain" / "rust.md").read_text()
    assert "## Public contracts" in explanation
    assert "lexical declaration; behavior remains unexplained" in explanation
    normalize = next(row for row in targets["selected"] if row["symbol"] == "normalize_invoice")
    normalize_source = (host / normalize["file"]).read_bytes()
    normalize_spelling = normalize_source[
        normalize["span"]["start_byte"] : normalize["span"]["end_byte"]
    ]
    assert hashlib.sha256(normalize_spelling).hexdigest() == normalize["spelling_sha256"]

    concept = json.loads((host / "reports" / "concept" / "findings.json").read_text())
    assert concept["status"] == "complete"
    assert concept["outcome"] == "drift-found"
    assert len(concept["findings"]) == 1
    assert concept["findings"][0]["term"] == "cancelled_order"
    assert concept["findings"][0]["file"] == "src/billing_parser.rs"
    concept_hit = concept["findings"][0]
    concept_source = (host / concept_hit["file"]).read_bytes()
    assert (
        concept_source[concept_hit["span"]["start_byte"] : concept_hit["span"]["end_byte"]]
        == b"cancelled_order"
    )

    duplication = json.loads((host / "reports" / "duplication" / "findings.json").read_text())
    assert duplication["scan_meta"]["status"] == "complete"
    assert len(duplication["findings"]) == 1
    sites = {site["symbol"] for site in duplication["findings"][0]["sites"]}
    assert sites == {"pending_invoice_total", "queued_invoice_total"}
    for site in duplication["findings"][0]["sites"]:
        source = (host / site["file"]).read_bytes()
        spelling = source[site["span"]["start_byte"] : site["span"]["end_byte"]]
        assert hashlib.sha256(spelling).hexdigest() == site["spelling_sha256"]
    assert (
        "Do not consolidate automatically"
        in (host / "reports" / "duplication" / "triage.md").read_text()
    )

    folder = json.loads((host / "reports" / "folder" / "findings.json").read_text())
    assert folder["status"] == "complete"
    assert folder["outcome"] == "drift-found"
    assert len(folder["findings"]) == 1
    assert folder["findings"][0]["prefix"] == "billing"
    assert set(folder["findings"][0]["files"]) == {
        "src/billing_parser.rs",
        "src/billing_types.rs",
        "src/billing_validator.rs",
    }
    assert (
        folder["findings"][0]["evidence_sha256"]
        == hashlib.sha256("\n".join(sorted(folder["findings"][0]["files"])).encode()).hexdigest()
    )

    inventories = [
        adapter["analysis"]["rust"]["inventory"],
        targets["analysis"]["rust"]["inventory"],
        concept["analysis"]["rust"]["inventory"],
        duplication["scan_meta"]["analysis"]["inventory"],
        folder["analysis"]["rust"]["inventory"],
    ]
    analyses = [
        adapter["analysis"]["rust"],
        targets["analysis"]["rust"],
        concept["analysis"]["rust"],
        duplication["scan_meta"]["analysis"],
        folder["analysis"]["rust"],
    ]
    assert len({analysis["source_manifest_sha256"] for analysis in analyses}) == 1
    assert all(analysis["cargo_metadata"]["returncode"] == 0 for analysis in analyses)
    assert all(analysis["cargo_check"]["returncode"] == 0 for analysis in analyses)
    for rows in inventories:
        roles = {row["file"]: row.get("reason", row["role"]) for row in rows}
        assert roles["tests/invoice_test.rs"] == "test"
        assert roles["generated/generated_invoice.rs"] == "generated-tree"
        assert roles["vendor/vendor_invoice.rs"] == "vendor"
        assert roles["target/target_invoice.rs"] == "build-tree"
        assert roles["examples/invoice_demo.rs"] == "auxiliary-target"
        assert roles["benches/invoice_bench.rs"] == "auxiliary-target"
        assert roles["build.rs"] == "configuration"
        assert roles["linked-external"] == "symlink"
    assert _hashes(host) == before
    assert copied_common.is_file()
    for script in copied.values():
        text = script.read_text(encoding="utf-8")
        assert "rust_lexical_facts" in text
        assert str(ROOT) not in text


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
def test_each_consumer_missing_tool_clears_stale_and_recovers(skill: str, tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _, copied = _install_closures(tmp_path)
    valid = _invoke(skill, copied[skill], host)
    assert valid.returncode == 0, valid.stdout + valid.stderr
    assert _status(skill, host) == "complete"

    missing = _invoke(skill, copied[skill], host, cargo=tmp_path / "missing-cargo")
    assert missing.returncode == 2
    assert _status(skill, host) == "partial"
    report_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (host / "reports").rglob("*.md")
        if skill.split("-")[-1] in path.as_posix()
        or path.name in {"report.md", "rust.md", "triage.md"}
    )
    assert "complete/clean" not in report_text

    recovered = _invoke(skill, copied[skill], host)
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert _status(skill, host) == "complete"


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
def test_each_consumer_old_and_failing_cargo_are_not_unsupported(
    skill: str, tmp_path: Path
) -> None:
    host = _copy_host(tmp_path)
    _, copied = _install_closures(tmp_path)
    old = _fake_cargo(tmp_path / "old-cargo", version="1.84.9")
    old_result = _invoke(skill, copied[skill], host, cargo=old)
    assert old_result.returncode == 2
    assert _status(skill, host) == "partial"

    failing = _fake_cargo(tmp_path / "failing-cargo", check_exit=9)
    failed_result = _invoke(skill, copied[skill], host, cargo=failing)
    assert failed_result.returncode == 1
    assert _status(skill, host) == "failed"


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
def test_each_consumer_malformed_source_is_partial_and_preserved(
    skill: str, tmp_path: Path
) -> None:
    host = _copy_host(tmp_path)
    shutil.copy2(FIXTURE / "malformed" / "Broken.rs", host / "src" / "broken.rs")
    before = _hashes(host)
    _, copied = _install_closures(tmp_path)

    result = _invoke(skill, copied[skill], host)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _status(skill, host) == "partial"
    assert _hashes(host) == before


def _fake_cargo(path: Path, *, version: str = "1.97.1", check_exit: int = 0) -> Path:
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        f"  printf '%s\\n' 'cargo {version} (fixture)'\n"
        "  exit 0\n"
        "fi\n"
        f"exit {check_exit}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_shared_helper_deletion_and_caller_knowledge_boundary() -> None:
    helper = COMMON.read_text(encoding="utf-8")
    for policy in (
        "cargo metadata",
        "--locked",
        "--offline",
        "source_manifest_sha256",
        "generated-marker",
        "auxiliary-target",
        "symlink",
    ):
        assert policy in helper
    for script in SCRIPTS.values():
        text = script.read_text(encoding="utf-8")
        assert "collect_snapshot" in text
        assert "CARGO_TARGET_DIR" not in text
        assert "cargo metadata" not in text
        assert "generated-marker" not in text
