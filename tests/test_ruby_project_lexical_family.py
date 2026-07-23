"""Five Ruby A1 consumers over one copied project/lexical fact closure."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ruby-project-lexical-family"
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: required frozen F2 runtime
)
RUBY = Path.home() / ".local" / "bin" / "ruby"
BUNDLER = Path.home() / ".local" / "bin" / "bundle"
PROVIDER = (
    ROOT
    / ".claude"
    / "skills"
    / "_ruby-project-lexical"
    / "ruby_project_lexical_facts.py"
)
SCRIPTS = {
    "adapt-project": ROOT / ".claude" / "skills" / "adapt-project" / "scripts" / "discover_ruby.py",
    "explain-code": ROOT / ".claude" / "skills" / "explain-code" / "scripts" / "explain_ruby.py",
    "find-concept-divergence": ROOT
    / ".claude"
    / "skills"
    / "find-concept-divergence"
    / "scripts"
    / "scan_ruby.py",
    "find-duplication": ROOT
    / ".claude"
    / "skills"
    / "find-duplication"
    / "scripts"
    / "run_ruby.py",
    "find-folder-topology-drift": ROOT
    / ".claude"
    / "skills"
    / "find-folder-topology-drift"
    / "scripts"
    / "detect_ruby.py",
}
pytestmark = pytest.mark.skipif(
    not all(path.is_file() for path in (PYTHON, RUBY, BUNDLER)),
    reason="Ruby 3.4.1, Bundler 2.6.2, and frozen product Python are required",
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


def _source_hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and (
            path.suffix in {".rb", ".gemspec", ".rake", ".ru"}
            or path.name in {"Gemfile", "Gemfile.lock", "Rakefile", "gems.rb", "gems.locked"}
            or path.name == "ruby-lexical-smoke"
        )
    }


def _native(host: Path, tmp_path: Path) -> None:
    ruby_version = _run(str(RUBY), "--version", cwd=host)
    assert ruby_version.returncode == 0
    assert ruby_version.stdout.startswith("ruby 3.4.1")
    prism = _run(str(RUBY), "--disable-gems", "-rprism", "-e", "puts Prism::VERSION", cwd=host)
    assert prism.returncode == 0
    assert prism.stdout == "1.2.0\n"
    bundler_version = _run(str(BUNDLER), "--version", cwd=host)
    assert bundler_version.returncode == 0
    assert bundler_version.stdout == "Bundler version 2.6.2\n"
    for source in sorted(
        path
        for path in host.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and (path.suffix == ".rb" or path.name == "ruby-lexical-smoke")
        and not ({"vendor", "generated", "build", "reports"} & set(path.relative_to(host).parts))
    ):
        syntax = _run(str(RUBY), "--disable-gems", "-c", str(source), cwd=host)
        assert syntax.returncode == 0, syntax.stdout + syntax.stderr
    env = os.environ.copy()
    env.update(
        BUNDLE_APP_CONFIG=str(tmp_path / "bundle-config"),
        BUNDLE_DISABLE_VERSION_CHECK="true",
        BUNDLE_FROZEN="true",
        BUNDLE_GEMFILE=str(host / "Gemfile"),
        BUNDLE_USER_HOME=str(tmp_path / "bundle-home"),
        ALL_PROXY="http://127.0.0.1:9",
        http_proxy="http://127.0.0.1:9",
        https_proxy="http://127.0.0.1:9",
    )
    bundle_check = _run(str(BUNDLER), "check", cwd=host, env=env)
    assert bundle_check.returncode == 0, bundle_check.stdout + bundle_check.stderr
    test = _run(str(RUBY), "--disable-gems", f"-I{host / 'lib'}", "test/invoice_test.rb", cwd=host)
    assert test.returncode == 0
    assert test.stdout == "ruby-native-test:ok\n"
    smoke = _run(
        str(RUBY),
        "--disable-gems",
        f"-I{host / 'lib'}",
        "bin/ruby-lexical-smoke",
        cwd=host,
    )
    assert smoke.returncode == 0
    assert smoke.stdout == "ruby-lexical-smoke:300\n"


def _install_closures(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    install = tmp_path / "installed" / ".agents" / "skills"
    copied_provider = install / "_ruby-project-lexical" / PROVIDER.name
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
    ruby: Path = RUBY,
    bundler: Path = BUNDLER,
    min_cluster_size: int = 3,
    target: str | None = None,
    test: str = "test/invoice_test.rb",
    smoke: str = "bin/ruby-lexical-smoke",
) -> subprocess.CompletedProcess[str]:
    base = (
        str(PYTHON),
        "-I",
        "-S",
        str(script),
        "--project-root",
        str(host),
        "--ruby",
        str(ruby),
        "--bundler",
        str(bundler),
        "--test",
        test,
        "--smoke",
        smoke,
    )
    if skill == "adapt-project":
        args = (*base, "--output-dir", str(host / "reports" / "adapt"), target or ".")
    elif skill == "explain-code":
        args = (
            *base,
            "--target",
            target or "lib",
            "--output",
            str(host / "reports" / "explain" / "ruby.md"),
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
            target or ".",
        )
    elif skill == "find-duplication":
        args = (
            *base,
            "--target",
            target or "lib",
            "--output-dir",
            str(host / "reports" / "duplication"),
        )
    else:
        args = (
            *base,
            "--ruby-root",
            target or "lib/billing",
            "--min-cluster-size",
            str(min_cluster_size),
            "--output",
            str(host / "reports" / "folder" / "detections.jsonl"),
        )
    return _run(*args, cwd=host)


def _artifact(skill: str, host: Path) -> dict:
    paths = {
        "adapt-project": host / "reports" / "adapt" / "adapter.json",
        "explain-code": host / "reports" / "explain" / "ruby" / "targets.json",
        "find-concept-divergence": host / "reports" / "concept" / "findings.json",
        "find-duplication": host / "reports" / "duplication" / "findings.json",
        "find-folder-topology-drift": host / "reports" / "folder" / "findings.json",
    }
    return json.loads(paths[skill].read_text(encoding="utf-8"))


def _status(skill: str, host: Path) -> str:
    payload = _artifact(skill, host)
    return payload.get("status") or payload.get("scan_meta", {}).get("status")


def test_ruby_five_copied_value_outcomes_roles_decoys_and_native(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _source_hashes(host)
    _native(host, tmp_path)
    copied_provider, copied = _install_closures(tmp_path)

    results = {skill: _invoke(skill, script, host) for skill, script in copied.items()}
    assert all(result.returncode == 0 for result in results.values()), {
        skill: result.stdout + result.stderr for skill, result in results.items()
    }

    adapter = _artifact("adapt-project", host)
    assert adapter["status"] == "complete"
    assert adapter["stack"] == {
        "frameworks": [],
        "languages": ["ruby"],
        "package_managers": ["bundler"],
    }
    assert adapter["source_roots"][0]["ruby_files"] == 6
    assert adapter["commands"]["check"] == [
        "ruby --disable-gems -c <each selected file>",
        "bundle check",
    ]
    assert (host / "reports" / "adapt" / "adapter.yml").is_file()
    evidence = json.loads((host / "reports" / "adapt" / "evidence.json").read_text())
    assert evidence["evidence"] == {"adapter": "adapter.yml", "report": "report.md"}

    targets = _artifact("explain-code", host)
    assert targets["status"] == "complete"
    symbols = {row["symbol"] for row in targets["selected"]}
    assert {"Billing::Invoice", "Billing::InvoiceState", "Billing::Parser#cancelled_order"} <= symbols
    assert all(row["visibility"] == "runtime-unresolved" for row in targets["selected"])
    assert len(list((host / "reports" / "explain" / "ruby" / "annotations").glob("*.md"))) == len(
        targets["selected"]
    )
    explanation = (host / "reports" / "explain" / "ruby.md").read_text()
    assert "not runtime identity, reachability, visibility, or behavior" in explanation
    explained = next(row for row in targets["selected"] if row["symbol"] == "Billing::Invoice")
    source = (host / explained["file"]).read_bytes()
    spelling = source[explained["span"]["start_byte"] : explained["span"]["end_byte"]]
    assert hashlib.sha256(spelling).hexdigest() == explained["spelling_sha256"]

    concept = _artifact("find-concept-divergence", host)
    assert concept["status"] == "complete"
    assert concept["outcome"] == "drift-found"
    assert len(concept["findings"]) == 1
    concept_hit = concept["findings"][0]
    assert concept_hit["term"] == "cancelled_order"
    assert concept_hit["file"] == "lib/billing/billing_parser.rb"
    source = (host / concept_hit["file"]).read_bytes()
    assert source[concept_hit["span"]["start_byte"] : concept_hit["span"]["end_byte"]] == b"cancelled_order"

    duplication = _artifact("find-duplication", host)
    assert duplication["scan_meta"]["status"] == "complete"
    assert len(duplication["findings"]) == 1
    sites = duplication["findings"][0]["sites"]
    assert {site["method_name"] for site in sites} == {"pending_total", "queued_total"}
    assert {site["file"] for site in sites} == {
        "lib/billing/billing_parser.rb",
        "lib/billing/billing_validator.rb",
    }
    for site in sites:
        source = (host / site["file"]).read_bytes()
        spelling = source[site["span"]["start_byte"] : site["span"]["end_byte"]]
        assert hashlib.sha256(spelling).hexdigest() == site["spelling_sha256"]
    assert "Exact Prism method-body spelling" in (
        host / "reports" / "duplication" / "triage.md"
    ).read_text()

    folder = _artifact("find-folder-topology-drift", host)
    assert folder["status"] == "complete"
    assert folder["outcome"] == "drift-found"
    assert len(folder["findings"]) == 1
    finding = folder["findings"][0]
    assert finding["prefix"] == "billing"
    assert set(finding["files"]) == {
        "lib/billing/billing_parser.rb",
        "lib/billing/billing_types.rb",
        "lib/billing/billing_validator.rb",
    }
    assert "Zeitwerk" in finding["recommendation"]

    analyses = [
        adapter["analysis"]["ruby"],
        targets["analysis"]["ruby"],
        concept["analysis"]["ruby"],
        duplication["scan_meta"]["analysis"],
        folder["analysis"]["ruby"],
    ]
    assert len({analysis["source_manifest_sha256"] for analysis in analyses}) == 1
    for analysis in analyses:
        assert analysis["prism"]["version"] == "1.2.0"
        assert analysis["bundle_check"]["returncode"] == 0
        assert analysis["native"]["test"]["stdout"] == "ruby-native-test:ok\n"
        assert analysis["native"]["smoke"]["stdout"] == "ruby-lexical-smoke:300\n"
        assert analysis["source_preserved"] is True
        assert any("reopening" in limit for limit in analysis["limits"])
        roles = {row["file"]: row.get("reason", row["role"]) for row in analysis["inventory"]}
        assert roles["test/billing_alpha.rb"] == "test"
        assert roles["generated/billing_alpha.rb"] == "generated"
        assert roles["vendor/example/billing_alpha.rb"] == "vendor"
        assert roles["build/billing_alpha.rb"] == "build"
        assert roles["reports/decoys/billing_alpha.rb"] == "report"
        assert roles["lib/billing/generated_marker.rb"] == "generated-marker"
        assert roles["linked-external"] == "symlink"
        assert roles["Gemfile"] == "configuration"
        assert roles["bin/ruby-lexical-smoke"] == "entrypoint"
    assert _source_hashes(host) == before
    assert copied_provider.is_file()
    for script in copied.values():
        text = script.read_text(encoding="utf-8")
        assert "ruby_project_lexical_facts" in text
        assert str(ROOT) not in text


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
def test_each_consumer_valid_failed_valid_clears_stale_and_recovers(
    skill: str, tmp_path: Path
) -> None:
    host = _copy_host(tmp_path)
    _, copied = _install_closures(tmp_path)
    valid = _invoke(skill, copied[skill], host)
    assert valid.returncode == 0, valid.stdout + valid.stderr
    assert _status(skill, host) == "complete"

    failing = _fake_bundler(tmp_path / "failing-bundle", check_exit=9)
    failed = _invoke(skill, copied[skill], host, bundler=failing)
    assert failed.returncode == 1
    assert _status(skill, host) == "failed"
    payload = _artifact(skill, host)
    findings = payload.get("findings", [])
    selected = payload.get("selected", [])
    assert findings == []
    assert selected == []

    recovered = _invoke(skill, copied[skill], host)
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert _status(skill, host) == "complete"


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
def test_each_consumer_missing_old_and_missing_project_states_are_partial(
    skill: str, tmp_path: Path
) -> None:
    host = _copy_host(tmp_path)
    _, copied = _install_closures(tmp_path)

    missing = _invoke(skill, copied[skill], host, ruby=tmp_path / "missing-ruby")
    assert missing.returncode == 2
    assert _status(skill, host) == "partial"

    old = _fake_ruby(tmp_path / "old-ruby", version="3.2.9")
    too_old = _invoke(skill, copied[skill], host, ruby=old)
    assert too_old.returncode == 2
    assert _status(skill, host) == "partial"

    (host / "Gemfile.lock").unlink()
    incomplete = _invoke(skill, copied[skill], host)
    assert incomplete.returncode == 2
    assert _status(skill, host) == "partial"


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
def test_each_consumer_malformed_selected_source_is_partial_and_preserved(
    skill: str, tmp_path: Path
) -> None:
    host = _copy_host(tmp_path)
    shutil.copy2(FIXTURE / "malformed" / "broken.rb", host / "lib" / "billing" / "broken.rb")
    before = _source_hashes(host)
    _, copied = _install_closures(tmp_path)

    result = _invoke(skill, copied[skill], host)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _status(skill, host) == "partial"
    assert _source_hashes(host) == before


def test_detectors_emit_clean_results_only_from_complete_evidence(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _, copied = _install_closures(tmp_path)
    parser = host / "lib" / "billing" / "billing_parser.rb"
    parser.write_text(parser.read_text().replace("cancelled_order", "cancelled_invoice"))

    concept = _invoke("find-concept-divergence", copied["find-concept-divergence"], host)
    duplication = _invoke(
        "find-duplication", copied["find-duplication"], host, target="lib/clean"
    )
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


@pytest.mark.parametrize(
    ("kind", "relative"),
    (("test", "test/invoice_test.rb"), ("smoke", "bin/ruby-lexical-smoke")),
)
def test_native_test_and_smoke_failures_replace_final_artifacts(
    kind: str, relative: str, tmp_path: Path
) -> None:
    host = _copy_host(tmp_path)
    (host / relative).write_text("raise 'native gate failed'\n", encoding="utf-8")
    _, copied = _install_closures(tmp_path)

    result = _invoke("adapt-project", copied["adapt-project"], host)

    assert result.returncode == 1
    payload = _artifact("adapt-project", host)
    assert payload["status"] == "failed"
    analysis = payload["analysis"]["ruby"]
    assert analysis["failure_kind"] == f"native-{kind}-failed"
    assert analysis["source_preserved"] is True
    assert payload["source_roots"][0]["ruby_files"] == 0


def test_native_path_through_symlink_is_rejected_without_traversal(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _, copied = _install_closures(tmp_path)

    result = _invoke(
        "adapt-project",
        copied["adapt-project"],
        host,
        test="linked-external/billing_alpha.rb",
    )

    assert result.returncode == 1
    analysis = _artifact("adapt-project", host)["analysis"]["ruby"]
    assert analysis["failure_kind"] == "native-test-unsafe"
    assert analysis["source_preserved"] is True


def _fake_ruby(path: Path, *, version: str) -> Path:
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        f"  printf '%s\\n' 'ruby {version} (fixture)'\n"
        "  exit 0\n"
        "fi\n"
        "exit 9\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _fake_bundler(path: Path, *, check_exit: int) -> Path:
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        "  printf '%s\\n' 'Bundler version 2.6.2'\n"
        "  exit 0\n"
        "fi\n"
        f"exit {check_exit}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_shared_provider_deletion_and_caller_knowledge_boundary() -> None:
    provider = PROVIDER.read_text(encoding="utf-8")
    for policy in (
        "bundle check",
        "BUNDLE_FROZEN",
        "source_manifest_sha256",
        "generated-marker",
        "--disable-gems",
        "symlink",
        "Rails",
        "Zeitwerk",
    ):
        assert policy in provider
    for script in SCRIPTS.values():
        text = script.read_text(encoding="utf-8")
        assert "collect_snapshot" in text
        assert "BUNDLE_FROZEN" not in text
        assert "Prism.parse" not in text
        assert "generated-marker" not in text
