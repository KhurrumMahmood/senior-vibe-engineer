from __future__ import annotations

import copy
import builtins
import json
import os
import shlex
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

from sweep.commands import (
    EXIT_CHANGED,
    RatchetResult,
    apply_ratchet,
    render_digest,
    scan_native,
    scan_profile,
)
from sweep.manifest import FindingInput, build_manifest, write_manifest
from sweep.pipeline import build_judgment, build_judgment_input, build_packet
from sweep.profile import load_sweep_profile
from sweep.serialization import canonical_json_bytes
from sweep.schemas import SchemaValidationError


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable).absolute()
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
REVISION = "a" * 40


def _provider() -> dict[str, object]:
    return {
        "schema_version": 1,
        "provider": "ruff",
        "language": "python",
        "provider_kind": "native",
        "scope": {"paths": ["src"], "case_sensitive": True, "roots": ["src"], "exclusions": []},
        "command": {
            "executable": "/tool/ruff",
            "argv": ["check", "--output-format", "json", "--no-cache", "src"],
            "timeout_seconds": 30.0,
            "output_format": "ruff-json",
            "output_byte_limit": 1_048_576,
        },
        "tool_version": "ruff 0.9.9",
        "exit": {"code": 0, "classification": "diagnostics"},
        "raw": {
            "stdout_sha256": EMPTY_SHA256,
            "stderr_sha256": EMPTY_SHA256,
            "stdout_bytes": 0,
            "stderr_bytes": 0,
        },
        "status": "completed",
        "failure": None,
    }


def _finding(index: int, *, count: int = 1, message_size: int = 20) -> FindingInput:
    return FindingInput(
        provider="ruff",
        language="python",
        native_rule_id=f"R{index:03d}",
        rule_semantic_key=f"R{index:03d}:v1",
        path=f"src/file_{index:03d}.py",
        semantic_anchor=f"symbol:item_{index:03d}",
        native_severity="warning",
        severity=2,
        message="m" * message_size,
        summary=f"summary {index} " + "x" * message_size,
        metrics={"count": count},
        observation_index=0,
        line=index + 1,
    )


def _manifest(findings: list[FindingInput], *, revision: str = REVISION) -> dict[str, object]:
    provider = _provider()
    provider["raw"] = {
        "stdout_sha256": EMPTY_SHA256,
        "stderr_sha256": EMPTY_SHA256,
        "stdout_bytes": 0,
        "stderr_bytes": 0,
    }
    return build_manifest(
        capability_registry_version=1,
        paths=["src"],
        case_sensitive=True,
        roots=["src"],
        exclusions=[],
        source={"revision": revision, "dirty": False, "dirty_state_hash": EMPTY_SHA256},
        providers=[provider],
        findings=findings,
    )


def _judgment(manifest: dict[str, object]) -> dict[str, object]:
    return build_judgment(
        manifest,
        judge_identity="fixture-judge",
        judge_version="1.0",
        outcomes=[
            {
                "finding_id": row["id"],
                "outcome": "actionable",
                "reason": "fixture reason",
                "evidence": "fixture:evidence",
            }
            for row in manifest["findings"]
        ],
    )


def _run_cli(*args: str, cwd: Path, path: str | None = None) -> subprocess.CompletedProcess[bytes]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "scripts")
    env["PATH"] = path if path is not None else env.get("PATH", "")
    return subprocess.run(
        [str(PYTHON), "-m", "sweep", *args],
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_im_7_digest_is_deterministic_and_hard_bounded() -> None:
    manifest = _manifest([_finding(index, message_size=2_000) for index in range(80)])
    judgment = _judgment(manifest)

    first = render_digest(manifest, judgment, purpose="agent")
    second = render_digest(
        copy.deepcopy(manifest), copy.deepcopy(judgment), purpose="agent"
    )

    assert first == second
    assert len(first) <= 65_536
    decoded = json.loads(first)
    assert len(decoded["finding_ids"]) == 50
    assert decoded["omitted_actionable"] == 30

    tiny = render_digest(manifest, judgment, purpose="agent", byte_limit=512)
    assert len(tiny) <= 512
    assert json.loads(tiny)["omitted_actionable"] > 0

    tampered = copy.deepcopy(manifest)
    tampered["findings"][0]["summary"] = "changed after hashing"
    with pytest.raises(SchemaValidationError, match="must bind"):
        render_digest(tampered, judgment, purpose="agent")


def test_im_7_digest_cli_matches_library_bytes(tmp_path: Path) -> None:
    manifest = _manifest([_finding(index) for index in range(12)])
    judgment = _judgment(manifest)
    source = tmp_path / "manifest.json"
    judgments = tmp_path / "judgment.json"
    output = tmp_path / "digest.json"
    write_manifest(source, manifest)
    judgments.write_bytes(canonical_json_bytes(judgment))

    result = _run_cli(
        "digest",
        "--manifest",
        str(source),
        "--judgments",
        str(judgments),
        "--purpose",
        "agent",
        "--out",
        str(output),
        "--top",
        "7",
        cwd=tmp_path,
    )

    expected = render_digest(manifest, judgment, purpose="agent", finding_limit=7)
    assert result.returncode == 0
    assert result.stdout == expected
    assert output.read_bytes() == expected

    unjudged = _run_cli(
        "digest",
        "--manifest",
        str(source),
        "--purpose",
        "agent",
        "--out",
        str(output),
        cwd=tmp_path,
    )
    assert unjudged.returncode == 2


def test_im_9_im_10_judgment_and_packet_cli_match_library_artifacts(tmp_path: Path) -> None:
    manifest = _manifest([_finding(1), _finding(2)])
    source = tmp_path / "manifest.json"
    judgment_input_path = tmp_path / "judgment-input.json"
    outcomes_path = tmp_path / "outcomes.json"
    judgment_path = tmp_path / "judgment.json"
    expected_path = tmp_path / "expected.json"
    packet_path = tmp_path / "packet.json"
    write_manifest(source, manifest)

    page_result = _run_cli(
        "judgment-input", "--manifest", str(source), "--offset", "1", "--top", "1",
        "--out", str(judgment_input_path), cwd=tmp_path,
    )
    expected_page = canonical_json_bytes(build_judgment_input(manifest, offset=1, finding_limit=1))
    assert page_result.returncode == 0 and page_result.stdout == expected_page
    assert judgment_input_path.read_bytes() == expected_page

    outcomes = [
        {"finding_id": row["id"], "outcome": "actionable", "reason": "real",
         "evidence": f"fixture:{index}"}
        for index, row in enumerate(manifest["findings"])
    ]
    outcomes_path.write_bytes(canonical_json_bytes(outcomes))
    import_result = _run_cli(
        "judgment-import", "--manifest", str(source), "--outcomes", str(outcomes_path),
        "--judge-identity", "fixture", "--judge-version", "1", "--out", str(judgment_path),
        cwd=tmp_path,
    )
    judgment = build_judgment(
        manifest, judge_identity="fixture", judge_version="1", outcomes=outcomes
    )
    assert import_result.returncode == 0
    assert judgment_path.read_bytes() == canonical_json_bytes(judgment)

    identifier = manifest["findings"][0]["id"]
    path = manifest["findings"][0]["location"]["path"]
    expected_delta = {"fixed": [identifier], "allowed_new": [], "metrics": []}
    expected_path.write_bytes(canonical_json_bytes(expected_delta))
    packet_result = _run_cli(
        "packet", "--manifest", str(source), "--judgments", str(judgment_path),
        "--finding-id", identifier, "--scope", path, "--recipe", "fix it",
        "--verification", ".venv/bin/python -m pytest -q", "--expected-delta",
        str(expected_path), "--token-budget", "8000", "--out", str(packet_path),
        cwd=tmp_path,
    )
    expected_packet = canonical_json_bytes(
        build_packet(
            manifest, judgment, finding_ids=[identifier], scope=[path], recipe="fix it",
            verification=".venv/bin/python -m pytest -q", expected_delta=expected_delta,
            token_budget=8_000,
        )
    )
    assert packet_result.returncode == 0 and packet_result.stdout == expected_packet
    assert packet_path.read_bytes() == expected_packet


def test_im_11_verify_cli_runs_command_derives_scope_rescans_and_emits_evidence(
    tmp_path: Path,
) -> None:
    before = _manifest([_finding(1), _finding(2)])
    after = _manifest([_finding(2)])
    judgment = _judgment(before)
    fixed_id = before["findings"][0]["id"]
    changed_path = before["findings"][0]["location"]["path"]
    packet = build_packet(
        before, judgment, finding_ids=[fixed_id], scope=[changed_path], recipe="fix it",
        verification="/usr/bin/true",
        expected_delta={"fixed": [fixed_id], "allowed_new": [], "metrics": []},
        token_budget=8_000,
    )
    before_path = tmp_path / "before.json"
    after_path = tmp_path / "after.json"
    judgment_path = tmp_path / "judgment.json"
    packet_path = tmp_path / "packet.json"
    output = tmp_path / "evidence.json"
    write_manifest(before_path, before)
    write_manifest(after_path, after)
    judgment_path.write_bytes(canonical_json_bytes(judgment))
    packet_path.write_bytes(canonical_json_bytes(packet))

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=tmp_path, check=True)
    changed = tmp_path / changed_path
    changed.parent.mkdir(parents=True)
    changed.write_text("before\n")
    subprocess.run(["git", "add", changed_path], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=tmp_path, check=True)
    changed.write_text("after\n")

    scanner = tmp_path / "scanner.py"
    scanner.write_text(
        "from pathlib import Path\nimport sys\n"
        "sys.stdout.buffer.write(Path(sys.argv[1]).read_bytes())\n"
    )
    subprocess.run(
        ["git", "add", "before.json", "after.json", "judgment.json", "packet.json", "scanner.py"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(["git", "commit", "-qm", "harness inputs"], cwd=tmp_path, check=True)
    scan_command = shlex.join([str(PYTHON), str(scanner), str(after_path)])
    result = _run_cli(
        "verify", "--packet", str(packet_path), "--before-manifest", str(before_path),
        "--judgments", str(judgment_path), "--root", str(tmp_path),
        "--scan-command", scan_command, "--out", str(output), cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr.decode()
    evidence = json.loads(result.stdout)
    assert output.read_bytes() == result.stdout
    assert evidence["verdict"] == "verified"
    assert evidence["changed_paths"] == [changed_path]
    assert evidence["diff"]["fixed"] == [fixed_id]
    assert evidence["scan"]["argv"] == [str(PYTHON), str(scanner), str(after_path)]


def test_im_7_diff_cli_matches_library_canonical_bytes_from_an_unrelated_cwd(tmp_path: Path) -> None:
    before = _manifest([_finding(1), _finding(2)])
    after = _manifest([_finding(2), _finding(3)])
    before_path = tmp_path / "before.json"
    after_path = tmp_path / "after.json"
    output = tmp_path / "diff.json"
    write_manifest(before_path, before)
    write_manifest(after_path, after)

    from sweep.manifest import build_diff

    expected = canonical_json_bytes(build_diff(before, after))
    result = _run_cli(
        "diff",
        str(before_path),
        str(after_path),
        "--out",
        str(output),
        cwd=tmp_path,
    )

    assert result.returncode == EXIT_CHANGED
    assert output.read_bytes() == expected
    assert result.stdout == expected
    assert b".claude/tasks/sweep-prototype" not in output.read_bytes()


def test_im_7_ratchet_rejects_growth_without_mutating_baseline_and_tightens_improvement(
    tmp_path: Path,
) -> None:
    baseline = _manifest([_finding(1, count=2), _finding(2)])
    growth = _manifest([_finding(1, count=3), _finding(2), _finding(3)])
    baseline_path = tmp_path / "baseline.json"
    write_manifest(baseline_path, baseline)
    original = baseline_path.read_bytes()

    failed = apply_ratchet(baseline, growth, accepts=[])

    assert isinstance(failed, RatchetResult)
    assert failed.violations == (
        f"metric_grew:{growth['findings'][0]['id']}:count:2:3",
        f"new:{growth['findings'][2]['id']}",
    )
    assert failed.tighten is False
    assert baseline_path.read_bytes() == original

    improved = _manifest([_finding(1, count=1)])
    accepted = apply_ratchet(baseline, improved, accepts=[])
    assert accepted.violations == ()
    assert accepted.tighten is True


def test_im_7_ratchet_accept_is_exact_auditable_and_unknown_accept_fails() -> None:
    baseline = _manifest([_finding(1)])
    current = _manifest([_finding(1), _finding(2)], revision="b" * 40)
    new_id = current["findings"][1]["id"]
    accept = {
        "finding_id": new_id,
        "reason": "approved compatibility debt",
        "operator": "release-manager",
        "revision": "b" * 40,
        "timestamp": "2026-07-16T20:00:00+00:00",
    }

    result = apply_ratchet(baseline, current, accepts=[accept])

    assert result.violations == ()
    assert result.tighten is True
    assert result.diff["accepts"] == [accept]
    with pytest.raises(ValueError, match="does not waive a current regression"):
        apply_ratchet(baseline, current, accepts=[{**accept, "finding_id": baseline["findings"][0]["id"]}])


def test_im_7_ratchet_cli_persists_accept_audit_then_tightens_baseline(tmp_path: Path) -> None:
    baseline = _manifest([_finding(1)])
    current = _manifest([_finding(1), _finding(2)], revision="b" * 40)
    new_id = current["findings"][1]["id"]
    accept = {
        "finding_id": new_id,
        "reason": "approved compatibility debt",
        "operator": "release-manager",
        "revision": "b" * 40,
        "timestamp": "2026-07-16T20:00:00+00:00",
    }
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    accept_path = tmp_path / "accepts.json"
    output = tmp_path / "ratchet.json"
    write_manifest(baseline_path, baseline)
    write_manifest(current_path, current)
    accept_path.write_text(json.dumps([accept]), encoding="utf-8")

    result = _run_cli(
        "ratchet",
        "--baseline",
        str(baseline_path),
        "--current",
        str(current_path),
        "--out",
        str(output),
        "--accept-file",
        str(accept_path),
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr.decode()
    assert json.loads(output.read_text(encoding="utf-8"))["accepts"] == [accept]
    assert baseline_path.read_bytes() == current_path.read_bytes()


def test_im_7_partial_or_corrupt_current_manifest_cannot_mutate_baseline(tmp_path: Path) -> None:
    baseline = _manifest([_finding(1)])
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    output = tmp_path / "ratchet.json"
    write_manifest(baseline_path, baseline)
    partial = copy.deepcopy(baseline)
    partial["providers"][0]["status"] = "failed"
    current_path.write_text(json.dumps(partial), encoding="utf-8")
    original = baseline_path.read_bytes()

    result = _run_cli(
        "ratchet",
        "--baseline",
        str(baseline_path),
        "--current",
        str(current_path),
        "--out",
        str(output),
        cwd=tmp_path,
    )

    assert result.returncode == 3
    assert baseline_path.read_bytes() == original
    assert not output.exists()


def test_im_8_scan_cli_uses_explicit_tool_and_is_cwd_path_and_activation_independent(
    tmp_path: Path,
) -> None:
    host = tmp_path / "host"
    host.mkdir()
    tool = tmp_path / "fixed-ruff"
    tool.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then echo 'ruff 0.9.9'; exit 0; fi\n"
        "printf '[]'\n",
        encoding="utf-8",
    )
    tool.chmod(0o755)
    output = tmp_path / "manifest.json"

    library = scan_native(
        root=host,
        languages=("python",),
        scopes=(".",),
        case_sensitive=True,
        source={"revision": REVISION, "dirty": False, "dirty_state_hash": EMPTY_SHA256},
        executables={"ruff": tool},
    )
    result = _run_cli(
        "scan",
        "--root",
        str(host),
        "--out",
        str(output),
        "--language",
        "python",
        "--scope",
        ".",
        "--case-sensitive",
        "--revision",
        REVISION,
        "--clean",
        "--dirty-state-hash",
        EMPTY_SHA256,
        "--tool",
        f"ruff={tool}",
        cwd=tmp_path,
        path="/usr/bin:/bin",
    )

    assert result.returncode == 0, result.stderr.decode()
    assert output.read_bytes() == canonical_json_bytes(library)
    assert result.stdout == output.read_bytes()
    assert library["status"] == "complete"
    assert library["providers"][0]["status"] == "completed"
    assert library["total"] == 0


def test_im_14_profile_scan_cli_runs_one_registry_selected_mixed_battery(
    tmp_path: Path,
) -> None:
    host = tmp_path / "host"
    host.mkdir()
    (host / "module.py").write_text("def small():\n    return 1\n", encoding="utf-8")
    tool = tmp_path / "fixed-ruff"
    tool.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then echo 'ruff 0.9.9'; exit 0; fi\n"
        "printf '[]'\n",
        encoding="utf-8",
    )
    tool.chmod(0o755)
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "languages": ["python"],
                "paths": ["."],
                "roots": ["."],
                "exclusions": [],
                "case_sensitive": True,
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "manifest.json"
    source = {
        "revision": REVISION,
        "dirty": False,
        "dirty_state_hash": EMPTY_SHA256,
    }

    library = scan_profile(
        root=host,
        profile=load_sweep_profile(profile_path),
        source=source,
        executables={"ruff": tool},
    )
    result = _run_cli(
        "scan",
        "--root",
        str(host),
        "--out",
        str(output),
        "--profile",
        str(profile_path),
        "--revision",
        REVISION,
        "--clean",
        "--dirty-state-hash",
        EMPTY_SHA256,
        "--tool",
        f"ruff={tool}",
        cwd=tmp_path,
        path="/usr/bin:/bin",
    )

    assert result.returncode == 0, result.stderr.decode()
    assert output.read_bytes() == canonical_json_bytes(library)
    assert result.stdout == output.read_bytes()
    assert library["status"] == "complete"
    assert [
        (provider["provider"], provider["language"], provider["provider_kind"])
        for provider in library["providers"]
    ] == [
        ("cx", "python", "parser-backed-ecosystem"),
        ("omnibus", "python", "parser-backed-ecosystem"),
        ("ruff", "python", "native"),
    ]
    assert all(provider["status"] == "completed" for provider in library["providers"])


def test_im_8_failed_provider_has_typed_exit_and_publishes_no_manifest(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    tool = tmp_path / "broken-ruff"
    tool.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then echo 'ruff 0.9.9'; exit 0; fi\n"
        "printf 'not-json'\n",
        encoding="utf-8",
    )
    tool.chmod(0o755)
    output = tmp_path / "manifest.json"

    result = _run_cli(
        "scan",
        "--root",
        str(host),
        "--out",
        str(output),
        "--language",
        "python",
        "--case-sensitive",
        "--revision",
        REVISION,
        "--clean",
        "--dirty-state-hash",
        EMPTY_SHA256,
        "--tool",
        f"ruff={tool}",
        cwd=tmp_path,
        path="/usr/bin:/bin",
    )

    assert result.returncode == 4
    assert not output.exists()
    failure = json.loads(result.stderr)
    assert failure["kind"] == "parse_failure"
    assert failure["provider"] == "ruff"


def test_im_9_detection_is_instrumented_against_network_and_model_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("detection attempted a network call")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".", 1)[0] in {"anthropic", "openai"}:
            raise AssertionError("detection attempted a model-provider import")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    host = tmp_path / "host"
    host.mkdir()
    tool = tmp_path / "ruff"
    tool.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then echo 'ruff 0.9.9'; exit 0; fi\n"
        "printf '[]'\n",
        encoding="utf-8",
    )
    tool.chmod(0o755)

    manifest = scan_native(
        root=host,
        languages=("python",),
        scopes=(".",),
        case_sensitive=True,
        source={"revision": REVISION, "dirty": False, "dirty_state_hash": EMPTY_SHA256},
        executables={"ruff": tool},
    )

    assert manifest["status"] == "complete" and manifest["total"] == 0


def test_im_8_help_and_runtime_sources_expose_no_prototype_dependency(tmp_path: Path) -> None:
    help_result = _run_cli("--help", cwd=tmp_path)
    sources = b"".join(path.read_bytes() for path in sorted((ROOT / "scripts" / "sweep").glob("*.py")))

    assert help_result.returncode == 0
    for command in (b"scan", b"digest", b"diff", b"ratchet"):
        assert command in help_result.stdout
    assert b".claude/tasks/sweep-prototype" not in sources

    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    public = subprocess.run(
        [str(PYTHON), "-m", "scripts.sweep", "--help"],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert public.returncode == 0, public.stderr.decode()
    assert b"scan" in public.stdout
