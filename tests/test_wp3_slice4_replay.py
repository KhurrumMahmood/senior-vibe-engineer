from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
REPLAY = REPO_ROOT / "scripts" / "wp3_slice4_replay.py"
BINDING_EVIDENCE = REPO_ROOT / "scripts" / "wp3_binding_selection_evidence.py"


def _load_replay():
    spec = importlib.util.spec_from_file_location("wp3_slice4_replay", REPLAY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _commit(repo: Path, path: str, content: str, message: str) -> tuple[str, str]:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-m", message)
    revision = _git(repo, "rev-parse", "HEAD")
    return revision, _git(repo, "rev-parse", f"{revision}^{{tree}}")


def _repo(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Replay Test")
    _git(repo, "config", "user.email", "replay@example.invalid")
    revision, tree = _commit(repo, "implementation.py", "VALUE = 1\n", "implementation")
    return repo, revision, tree


def _minimal_manifest(module, path: Path, revision: str, tree: str) -> dict:
    payload = {
        "allowed_evidence_paths": list(module.EVIDENCE_PATHS),
        "artifact_root": str(path.parent / "artifacts"),
        "commands": [],
        "generated_replay_artifacts": [],
        "principal_sources": [],
        "profile": "replay-only",
        "python": str(Path(sys.executable).absolute()),
        "reviewed_revision": revision,
        "reviewed_tree": tree,
        "schema_version": 1,
        "scope_written_at": module.FIXED_SCOPE_CLOCK,
        "verification": {"pytest_collected": 0},
    }
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    module._write_checksum(path)
    return payload


def test_commands_use_explicit_shared_interpreter_without_local_venv(tmp_path):
    module = _load_replay()
    assert not (REPO_ROOT / ".venv").exists()

    commands = module._commands(
        tmp_path, python=sys.executable, include_verification=True
    )

    expected = str(Path(sys.executable).absolute())
    assert commands
    assert all(argv[0] == expected for _command_id, argv in commands)
    assert all(".venv/bin/python" not in argv for _command_id, argv in commands)


def test_verify_rejects_fabricated_revision_and_tree(tmp_path, monkeypatch):
    module = _load_replay()
    repo, revision, tree = _repo(tmp_path)
    manifest = tmp_path / "manifest.json"
    payload = _minimal_manifest(module, manifest, revision, tree)
    monkeypatch.setattr(module, "_commands", lambda *args, **kwargs: [])
    monkeypatch.setattr(module, "_artifacts", lambda *args, **kwargs: [])
    monkeypatch.setattr(module, "_principal_sources", lambda *args, **kwargs: [])
    monkeypatch.setattr(module, "_pytest_collected", lambda *args, **kwargs: 0)
    module.verify(manifest, python=sys.executable, repo_root=repo)

    payload["reviewed_revision"] = "f" * 40
    manifest.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    module._write_checksum(manifest)
    with pytest.raises(ValueError, match="reviewed revision does not exist"):
        module.verify(manifest, python=sys.executable, repo_root=repo)

    payload["reviewed_revision"] = revision
    payload["reviewed_tree"] = "e" * 40
    manifest.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    module._write_checksum(manifest)
    with pytest.raises(ValueError, match="reviewed tree does not match"):
        module.verify(manifest, python=sys.executable, repo_root=repo)


def test_verify_allows_only_evidence_commits_after_implementation(
    tmp_path, monkeypatch
):
    module = _load_replay()
    repo, revision, tree = _repo(tmp_path)
    manifest = tmp_path / "manifest.json"
    _minimal_manifest(module, manifest, revision, tree)
    monkeypatch.setattr(module, "_commands", lambda *args, **kwargs: [])
    monkeypatch.setattr(module, "_artifacts", lambda *args, **kwargs: [])
    monkeypatch.setattr(module, "_principal_sources", lambda *args, **kwargs: [])
    monkeypatch.setattr(module, "_pytest_collected", lambda *args, **kwargs: 0)
    _commit(
        repo,
        module.EVIDENCE_PATHS[0],
        "deterministic evidence\n",
        "evidence",
    )
    module.verify(manifest, python=sys.executable, repo_root=repo)

    _commit(repo, "implementation.py", "VALUE = 2\n", "unrelated code")
    with pytest.raises(ValueError, match="post-implementation non-evidence path"):
        module.verify(manifest, python=sys.executable, repo_root=repo)


def test_binding_selection_evidence_is_deterministic_and_complete(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    for output in (first, second):
        result = subprocess.run(
            [sys.executable, str(BINDING_EVIDENCE), "--output", str(output)],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    assert first.read_bytes() == second.read_bytes()
    payload = json.loads(first.read_text(encoding="utf-8"))
    successful = payload["successful_selection"]
    assert successful["profile_sha256"]
    assert successful["roots"][0]["core_sha256"]
    assert successful["roots"][0]["binding_sha256"]
    assert successful["roots"][0]["rendered_sha256"]
    assert set(payload["negative_outcomes"]) == {
        "ambiguity",
        "incompatibility",
        "zero_match",
    }
    assert all(item["rejected"] for item in payload["negative_outcomes"].values())
    assert payload["root_isolation"]["cross_root_binding_leak"] is False
    assert payload["order_independence"]["equal"] is True
    assert str(tmp_path) not in first.read_text(encoding="utf-8")


def test_full_manifest_replay_is_byte_identical_and_rejects_tampering(
    tmp_path, monkeypatch
):
    module = _load_replay()
    python = str(Path(sys.executable).absolute())
    monkeypatch.setattr(
        module,
        "_verification_commands",
        lambda selected_python: [
            ("verification-sentinel", [selected_python, "-c", "pass"])
        ],
    )
    monkeypatch.setattr(module, "_validate_git_binding", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "_principal_sources", lambda *args, **kwargs: [])
    monkeypatch.setattr(module, "_pytest_collected", lambda *args, **kwargs: 1)
    output_root = tmp_path / "replay"
    manifest = tmp_path / "manifest.json"
    evidence_report = tmp_path / "evidence.md"

    first = module.record(
        output_root,
        manifest,
        reviewed_revision="0" * 40,
        reviewed_tree="1" * 40,
        include_verification=True,
        python=python,
        evidence_report_path=evidence_report,
    )
    assert first["profile"] == "full-verification-and-replay"
    assert first["python"] == python
    first_bytes = manifest.read_bytes()
    first_report = evidence_report.read_bytes()

    module.verify(manifest, python=python)
    module.record(
        output_root,
        manifest,
        reviewed_revision="0" * 40,
        reviewed_tree="1" * 40,
        include_verification=True,
        python=python,
        evidence_report_path=evidence_report,
    )
    assert manifest.read_bytes() == first_bytes
    assert evidence_report.read_bytes() == first_report

    binding_artifact = output_root / "binding-selection" / "evidence.json"
    binding_artifact.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact hashes differ before replay"):
        module.verify(manifest, python=python)

    module.record(
        output_root,
        manifest,
        reviewed_revision="0" * 40,
        reviewed_tree="1" * 40,
        include_verification=True,
        python=python,
        evidence_report_path=evidence_report,
    )
    binding_artifact.unlink()
    with pytest.raises(ValueError, match="artifact set differs from the canonical set"):
        module.verify(manifest, python=python)
