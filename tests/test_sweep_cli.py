from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from sweep.commands import (
    EXIT_CHANGED,
    RatchetResult,
    apply_ratchet,
    render_digest,
    scan_native,
)
from sweep.manifest import FindingInput, build_manifest, write_manifest
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
        "command": {
            "executable": "/tool/ruff",
            "argv": ["check", "--output-format", "json", "--no-cache", "."],
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

    first = render_digest(manifest)
    second = render_digest(copy.deepcopy(manifest))

    assert first == second
    assert len(first) <= 65_536
    assert first.count(b"\n- `f2_") == 50
    assert b"30 more findings omitted" in first
    assert b"full findings stay in the manifest" in first

    tiny = render_digest(manifest, byte_limit=512)
    assert len(tiny) <= 512
    assert b"more findings omitted" in tiny

    tampered = copy.deepcopy(manifest)
    tampered["findings"][0]["summary"] = "changed after hashing"
    with pytest.raises(SchemaValidationError, match="must bind"):
        render_digest(tampered)


def test_im_7_digest_cli_matches_library_bytes(tmp_path: Path) -> None:
    manifest = _manifest([_finding(index) for index in range(12)])
    source = tmp_path / "manifest.json"
    output = tmp_path / "digest.md"
    write_manifest(source, manifest)

    result = _run_cli(
        "digest",
        str(source),
        "--out",
        str(output),
        "--finding-limit",
        "7",
        cwd=tmp_path,
    )

    expected = render_digest(manifest, finding_limit=7)
    assert result.returncode == 0
    assert result.stdout == expected
    assert output.read_bytes() == expected


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
