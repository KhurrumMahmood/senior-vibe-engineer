"""Frozen Ruby-only P7 spine, native boundary, and pending-work truth."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ruby-pilot"
PROFILE = ROOT / "scripts" / "language_profiles" / "ruby.json"
BASELINE = ROOT / ".claude" / "tasks" / "p7-baseline" / "ruby-pilot-baseline.json"
COVERAGE = ROOT / ".claude" / "tasks" / "ruby-language-coverage.json"
DOCTOR = ROOT / "scripts" / "language_doctor.py"
INVENTORY = ROOT / "scripts" / "source_inventory.py"

EXPECTED_SKILLS = {
    "adapt-project", "audit-decisions", "explain-code", "extract-enum",
    "find-comment-drift", "find-complexity-hotspots",
    "find-concept-divergence", "find-dormant", "find-duplication",
    "find-folder-topology-drift", "find-implicit-state",
    "find-incomplete-sweep", "find-omnibus", "find-semantic-duplication",
    "find-standard-gaps", "map-subsystem", "move-path",
    "prevent-regression", "propose-boundary",
    "propose-folder-reorganization", "rename-concept", "unify-shadows",
}


def _manifest(root: Path) -> tuple[str, int, list[str]]:
    rows: list[tuple[str, str, int]] = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        content = path.read_bytes()
        rows.append(
            (path.relative_to(root).as_posix(), hashlib.sha256(content).hexdigest(), len(content))
        )
    digest = hashlib.sha256()
    for path, file_digest, _size in rows:
        digest.update(path.encode() + b"\0" + file_digest.encode() + b"\n")
    return digest.hexdigest(), sum(row[2] for row in rows), [row[0] for row in rows]


def _tree_state(root: Path) -> dict[str, tuple[str, str]]:
    state: dict[str, tuple[str, str]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            state[relative] = ("symlink", os.readlink(path))
        elif path.is_file():
            state[relative] = ("file", hashlib.sha256(path.read_bytes()).hexdigest())
    return state


def _run(
    argv: list[str],
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _fake_tool(path: Path, output: str, *, exit_code: int = 0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' {json.dumps(output)}\n"
        f"exit {exit_code}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _fake_project_tools(
    host: Path,
    versions: dict[str, str],
    *,
    exit_code: int = 0,
) -> dict[str, Path]:
    names = {"ruby": "ruby", "gem": "gem", "bundler": "bundle", "steep": "steep"}
    return {
        tool_id: _fake_tool(
            host / ".tools" / "ruby" / "bin" / filename,
            versions[tool_id],
            exit_code=exit_code,
        )
        for tool_id, filename in names.items()
    }


def _doctor(host: Path, *, path: str) -> dict[str, object]:
    completed = _run(
        [
            sys.executable,
            "-I",
            "-S",
            str(DOCTOR),
            "--project-root",
            str(host),
            "--language",
            "ruby",
        ],
        host.parent,
        env={**os.environ, "PATH": path},
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(completed.stdout)


def _bundle_environment(host: Path, app_config: Path) -> dict[str, str]:
    return {
        **os.environ,
        "BUNDLE_APP_CONFIG": str(app_config),
        "BUNDLE_DISABLE_VERSION_CHECK": "true",
        "BUNDLE_FROZEN": "true",
        "BUNDLE_GEMFILE": str(host / "Gemfile"),
        "ALL_PROXY": "http://127.0.0.1:9",
        "http_proxy": "http://127.0.0.1:9",
        "https_proxy": "http://127.0.0.1:9",
    }


def test_ruby_fixture_and_runtime_closure_match_frozen_manifests() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert _manifest(FIXTURE) == (
        baseline["fixture"]["manifest_sha256"],
        baseline["fixture"]["total_bytes"],
        baseline["fixture"]["files"],
    )

    closure = baseline["runtime_closure"]
    paths = [ROOT / path for path in closure["files"]]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0" + hashlib.sha256(path.read_bytes()).hexdigest().encode() + b"\n")
    assert digest.hexdigest() == closure["manifest_sha256"]
    assert sum(path.stat().st_size for path in paths) == closure["total_bytes"]


def test_ruby_profile_inventory_roles_dsl_boundaries_symlink_and_preservation(
    tmp_path: Path,
) -> None:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    assert profile["suffixes"] == [".rb"]
    assert {"Gemfile", "Gemfile.lock", "gems.rb", "gems.locked", "Rakefile"} <= set(
        profile["project_markers"]
    )
    assert set(profile["fact_tiers"]) == {
        "lexical-filesystem", "syntax", "semantic-project"
    }
    assert "*.gemspec" in "\n".join(profile["explicit_limits"])
    assert "Each ruby -c verification must run once" in "\n".join(
        profile["explicit_limits"]
    )

    pilot = tmp_path / "ruby-pilot"
    shutil.copytree(FIXTURE, pilot)
    host = pilot / "host"
    (host / "linked-external").symlink_to(
        pilot / "symlink-target", target_is_directory=True
    )
    before = _tree_state(host)
    completed = _run(
        [
            sys.executable, "-I", "-S", str(INVENTORY),
            "--project-root", str(host),
        ],
        tmp_path,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert _tree_state(host) == before
    payload = json.loads(completed.stdout)
    ruby_files = {
        row["path"]: row for row in payload["files"] if row["language"] == "ruby"
    }
    assert ruby_files["lib/billing/invoice_service.rb"]["role"] == "source"
    assert ruby_files["lib/billing/invoice_registry.rb"]["role"] == "source"
    assert ruby_files["lib/billing/dynamic_features.rb"]["role"] == "source"
    assert ruby_files["test/invoice_service_test.rb"]["role"] == "test"
    assert ruby_files["generated/GeneratedInvoice.rb"]["role"] == "generated"
    assert not ({"Gemfile", "Gemfile.lock", "Rakefile", "ruby_pilot.gemspec"} & ruby_files.keys())
    excluded = {row["path"]: row["role"] for row in payload["excluded_roots"]}
    assert excluded["build"] == "build"
    assert excluded["vendor"] == "vendor"
    assert excluded["linked-external"] == "symlink"
    assert not any(
        path.startswith(("build/", "vendor/", "linked-external/"))
        for path in ruby_files
    )


def test_ruby_native_copied_test_smoke_prism_bundle_and_invalid_boundaries(
    tmp_path: Path,
) -> None:
    ruby = shutil.which("ruby")
    bundle = shutil.which("bundle")
    if ruby is None or bundle is None:
        pytest.skip("Ruby/Bundler unavailable; the profile doctor reports this boundary")
    host = tmp_path / "copied-host"
    shutil.copytree(FIXTURE / "host", host)
    before = _tree_state(host)

    first_party = sorted(
        path for path in host.rglob("*.rb")
        if not ({"build", "vendor"} & set(path.relative_to(host).parts))
    )
    assert first_party
    for source in first_party:
        syntax = _run([ruby, "--disable-gems", "-c", str(source)], host)
        assert syntax.returncode == 0, syntax.stdout + syntax.stderr
        assert syntax.stdout == "Syntax OK\n"

    native = _run(
        [ruby, "--disable-gems", f"-I{host / 'lib'}", str(host / "test/invoice_service_test.rb")],
        host,
    )
    assert native.returncode == 0, native.stdout + native.stderr
    assert native.stdout == "native-test:ok\n"
    smoke = _run([str(host / "bin/ruby-pilot-smoke")], host)
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr
    assert smoke.stdout == "invoice:INV-42:125\n"

    bundled = _run(
        [bundle, "check"],
        host,
        env=_bundle_environment(host, tmp_path / "bundle-config"),
    )
    assert bundled.returncode == 0, bundled.stdout + bundled.stderr
    assert "dependencies are satisfied" in bundled.stdout

    prism = _run(
        [
            ruby,
            "--disable-gems",
            "-rprism",
            "-e",
            "r=Prism.parse_file(ARGV[0]); abort(r.errors.inspect) unless r.success?; puts [Prism::VERSION, r.comments.length].join(':')",
            str(host / "lib/billing/invoice_service.rb"),
        ],
        host,
    )
    assert prism.returncode == 0, prism.stdout + prism.stderr
    prism_version, comment_count = prism.stdout.strip().split(":")
    assert tuple(int(part) for part in prism_version.split(".")) >= (1, 0, 0)
    assert int(comment_count) >= 3

    malformed = _run(
        [ruby, "--disable-gems", "-c", str(FIXTURE / "malformed" / "Broken.rb")],
        host,
    )
    assert malformed.returncode != 0
    assert "syntax errors found" in malformed.stderr
    assert _tree_state(host) == before

    invalid = tmp_path / "invalid-project"
    shutil.copytree(FIXTURE / "host", invalid)
    (invalid / "Gemfile").write_text("gemspec(\n", encoding="utf-8")
    invalid_before = _tree_state(invalid)
    rejected = _run(
        [bundle, "check"],
        invalid,
        env=_bundle_environment(invalid, tmp_path / "invalid-bundle-config"),
    )
    assert rejected.returncode != 0
    assert "Gemfile" in rejected.stderr
    assert _tree_state(invalid) == invalid_before


def test_ruby_doctor_strict_available_missing_old_broken_and_optional_states(
    tmp_path: Path,
) -> None:
    host = tmp_path / "real-host"
    shutil.copytree(FIXTURE / "host", host)
    real = _doctor(host, path=os.environ.get("PATH", ""))
    tools = {row["id"]: row for row in real["tools"]}
    assert real["project_markers"]["present"] == ["Gemfile", "Gemfile.lock", "Rakefile"]
    assert tools["ruby"]["status"] == "available"
    assert tools["ruby"]["version"] == "3.4.1"
    assert tools["gem"]["version"] == "3.6.2"
    assert tools["bundler"]["version"] == "2.6.2"
    assert tools["steep"]["required"] is False
    assert tools["steep"]["status"] == "unavailable"
    assert tools["steep"]["reason"] == "not-found"
    assert real["status"] == "limited"
    assert real["status_reasons"] == ["partial-toolchain"]

    local = tmp_path / "local"
    local.mkdir()
    (local / "Gemfile").write_text("# marker\n", encoding="utf-8")
    local_tools = _fake_project_tools(
        local,
        {
            "ruby": "ruby 3.4.2 (fixture)",
            "gem": "3.6.3",
            "bundler": "Bundler version 2.6.3",
            "steep": "Steep 1.10.0",
        },
    )
    system_bin = tmp_path / "system-bin"
    system_bin.mkdir()
    for name, output in {
        "ruby": "ruby 9.0.0", "gem": "9.0.0",
        "bundle": "Bundler version 9.0.0", "steep": "Steep 9.0.0",
    }.items():
        _fake_tool(system_bin / name, output)
    local_payload = _doctor(local, path=str(system_bin))
    assert local_payload["status"] == "available"
    assert {
        row["id"]: (row["path"], row["provenance"])
        for row in local_payload["tools"]
    } == {
        tool_id: (str(path.absolute()), "project-local")
        for tool_id, path in local_tools.items()
    }

    missing = tmp_path / "missing"
    missing.mkdir()
    (missing / "Gemfile").write_text("# marker\n", encoding="utf-8")
    missing_payload = _doctor(missing, path="")
    assert missing_payload["status"] == "unavailable"
    assert missing_payload["status_reasons"] == ["toolchain-unavailable"]
    assert all(row["reason"] == "not-found" for row in missing_payload["tools"])

    old = tmp_path / "old"
    old.mkdir()
    (old / "Gemfile").write_text("# marker\n", encoding="utf-8")
    _fake_project_tools(
        old,
        {
            "ruby": "ruby 3.2.9 (fixture)",
            "gem": "3.4.22",
            "bundler": "Bundler version 2.5.23",
            "steep": "Steep 0.9.0",
        },
    )
    old_payload = _doctor(old, path="")
    assert old_payload["status"] == "too-old"
    assert old_payload["status_reasons"] == ["toolchain-too-old"]
    assert all(row["reason"] == "below-minimum-version" for row in old_payload["tools"])

    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "Gemfile").write_text("# marker\n", encoding="utf-8")
    _fake_project_tools(
        broken,
        {tool_id: "broken" for tool_id in ("ruby", "gem", "bundler", "steep")},
        exit_code=7,
    )
    broken_payload = _doctor(broken, path="")
    assert broken_payload["status"] == "unavailable"
    assert all(
        row["reason"] == "version-command-failed" for row in broken_payload["tools"]
    )

    no_metadata = tmp_path / "no-metadata"
    no_metadata.mkdir()
    _fake_project_tools(
        no_metadata,
        {
            "ruby": "ruby 3.4.2", "gem": "3.6.3",
            "bundler": "Bundler version 2.6.3", "steep": "Steep 1.10.0",
        },
    )
    invalid_metadata = _doctor(no_metadata, path="")
    assert invalid_metadata["status"] == "limited"
    assert invalid_metadata["status_reasons"] == ["project-metadata-unavailable"]


def test_ruby_frozen_cohort_contracts_and_all_22_initial_dispositions() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    contracts = baseline["pilot_contracts"]
    lexical = contracts["lexical"]
    assert lexical["skill"] == "find-comment-drift"
    assert lexical["disposition"] == "ruby-pending-implementation"
    assert lexical["positive_obligation"]["path"] == "host/lib/billing/invoice_service.rb"
    assert {"generated", "vendor", "build", "test", "magic-comments"} <= set(
        lexical["must_not_fire"]
    )
    assert {"ruby -c per file", "copied closure", "source fingerprint"} <= set(
        lexical["native_obligations"]
    )

    semantic = contracts["semantic"]
    assert semantic["skill"] == "map-subsystem"
    assert semantic["disposition"] == "ruby-pending-implementation"
    assert semantic["expected_final_status"] == "partial-without-project-owned-analyzer"
    assert {"require", "const_get", "public_send", "define_method", "class_eval"} <= set(
        semantic["must_not_resolve"]
    )
    assert {"locked bundle check", "native test", "executable smoke"} <= set(
        semantic["native_obligations"]
    )

    mutation = contracts["mutation"]
    assert mutation["skill"] == "move-path"
    assert mutation["disposition"] == "ruby-pending-implementation"
    assert mutation["candidate_move"] == {
        "from": "lib/billing/invoice_registry.rb",
        "to": "lib/invoicing/invoice_registry.rb",
    }
    assert {"dynamic require", "autoload", "reflection", "Rails/Zeitwerk"} <= set(
        mutation["refusal_boundaries"]
    )
    assert {
        "preview", "exact bounded diff", "source fingerprint", "rollback",
        "ruby -c per file", "locked bundle check", "native test", "executable smoke",
    } <= set(mutation["native_obligations"])
    assert baseline["stale_artifact_contract"] == {
        "invalid-or-failed": "remove prior final artifacts before emitting the failure state",
        "clean-or-complete": "atomically replace prior artifacts; never inherit stale findings",
        "same-destination": "valid-to-failed and failed-to-valid transitions are mandatory",
    }
    assert baseline["mutation_performed"] is False

    tool_sources = baseline["semantic_tool_sources"]
    assert tool_sources["runtime_standard_or_default"] == ["Prism", "Ripper"]
    assert tool_sources["toolchain_optional_present"] == ["RBS", "TypeProf"]
    assert {"Steep", "Sorbet", "RuboCop", "Standard Ruby", "Solargraph"} <= set(
        tool_sources["project_owned_optional"]
    )

    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    rows = coverage["skills"]
    assert coverage["decision"] == "expand"
    assert len(rows) == 22
    assert {row["skill"] for row in rows} == EXPECTED_SKILLS
    assert all(row["disposition"] == "ruby-pending-implementation" for row in rows)
    assert all(
        row["evidence_path"]
        and row["native_check"]
        and row["reviewed_revision"]
        and row["limitation"]
        for row in rows
    )
    assert "ruby-unsupported" not in {row["disposition"] for row in rows}
