"""Acceptance tests for versioned toolkit-owned host-state migrations."""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_PATH = REPO_ROOT / "scripts" / "host_migrations.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


hm = _load_module("host_migrations_under_test", MIGRATIONS_PATH)


def _write_manifest(root: Path, payload: dict) -> bytes:
    path = root / ".engineering" / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    (path.parent / ".gitignore").write_text("/local/\n", encoding="utf-8")
    raw = json.dumps(payload, indent=2).encode() + b"\n"
    path.write_bytes(raw)
    return raw


def _write_legacy_registry(root: Path, raw: bytes = b"subsystems:\n  billing: {}\n") -> bytes:
    path = root / ".claude" / "subsystems.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def _files(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def test_plan_is_read_only_and_names_the_exact_move(tmp_path: Path) -> None:
    _write_manifest(tmp_path, {"version": 1, "skills": {"default": "active"}})
    raw = _write_legacy_registry(tmp_path)
    (tmp_path / "user.txt").write_text("preserve me\n", encoding="utf-8")
    before = _files(tmp_path)

    report = hm.plan(tmp_path)

    assert report["status"] == "ready"
    assert report["current_schema"] == 1
    assert report["target_schema"] == 2
    assert report["pending_migrations"] == [hm.SUBSYSTEM_REGISTRY_MIGRATION_ID]
    assert report["operations"] == [
        {
            "action": "move",
            "from": ".claude/subsystems.yaml",
            "to": ".engineering/subsystems.yaml",
            "sha256": hm._sha256(raw),
        },
        {
            "action": "update-manifest",
            "path": ".engineering/manifest.json",
            "from_schema": 1,
            "to_schema": 2,
        },
    ]
    assert report["blockers"] == []
    assert _files(tmp_path) == before


def test_apply_moves_exact_bytes_updates_manifest_and_reapply_is_noop(tmp_path: Path) -> None:
    _write_manifest(tmp_path, {"version": 1, "skills": {"default": "active"}})
    raw = _write_legacy_registry(tmp_path)
    sentinel = tmp_path / ".claude" / "CLAUDE.md"
    sentinel.write_text("user-owned\n", encoding="utf-8")

    applied = hm.apply(tmp_path)

    assert applied["status"] == "applied"
    assert not (tmp_path / ".claude" / "subsystems.yaml").exists()
    assert (tmp_path / ".engineering" / "subsystems.yaml").read_bytes() == raw
    manifest = json.loads((tmp_path / ".engineering" / "manifest.json").read_text())
    assert manifest["version"] == 2
    assert manifest["skills"] == {"default": "active"}
    assert manifest["applied_migrations"] == [hm.SUBSYSTEM_REGISTRY_MIGRATION_ID]
    assert sentinel.read_text() == "user-owned\n"

    before = _files(tmp_path)
    repeated = hm.apply(tmp_path)
    assert repeated["status"] == "current"
    assert repeated["operations"] == []
    assert _files(tmp_path) == before


def test_apply_refuses_collision_and_newer_schema_without_writes(tmp_path: Path) -> None:
    _write_manifest(tmp_path, {"version": 1})
    _write_legacy_registry(tmp_path, b"legacy\n")
    canonical = tmp_path / ".engineering" / "subsystems.yaml"
    canonical.write_bytes(b"canonical\n")
    before = _files(tmp_path)

    collision = hm.apply(tmp_path)

    assert collision["status"] == "blocked"
    assert collision["blockers"][0]["code"] == "canonical-path-occupied"
    assert _files(tmp_path) == before

    _write_manifest(tmp_path, {"version": hm.CURRENT_SCHEMA + 1})
    before = _files(tmp_path)
    newer = hm.apply(tmp_path)
    assert newer["status"] == "newer-than-tool"
    assert newer["blockers"][0]["code"] == "newer-host-schema"
    assert _files(tmp_path) == before


def test_interrupted_apply_resumes_from_the_prepared_journal(
    tmp_path: Path, monkeypatch
) -> None:
    _write_manifest(tmp_path, {"version": 1})
    raw = _write_legacy_registry(tmp_path)
    original = hm._write_manifest
    calls = 0

    def interrupt_once(root: Path, manifest: dict) -> bytes:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise KeyboardInterrupt("simulated process stop after move")
        return original(root, manifest)

    monkeypatch.setattr(hm, "_write_manifest", interrupt_once)
    try:
        hm.apply(tmp_path)
    except KeyboardInterrupt:
        pass
    else:  # pragma: no cover - assertion aid
        raise AssertionError("simulated interruption did not fire")

    assert not (tmp_path / ".claude" / "subsystems.yaml").exists()
    assert (tmp_path / ".engineering" / "subsystems.yaml").read_bytes() == raw
    assert json.loads((tmp_path / ".engineering" / "manifest.json").read_text())["version"] == 1

    resumed = hm.apply(tmp_path)
    assert resumed["status"] == "applied"
    assert resumed["recovered"] is True
    assert json.loads((tmp_path / ".engineering" / "manifest.json").read_text())["version"] == 2


def test_interrupted_after_manifest_write_finalizes_the_journal(
    tmp_path: Path, monkeypatch
) -> None:
    _write_manifest(tmp_path, {"version": 1})
    _write_legacy_registry(tmp_path)
    original = hm._write_journal
    interrupted = False

    def interrupt_applied(root: Path, journal: dict) -> None:
        nonlocal interrupted
        if journal.get("state") == "applied" and not interrupted:
            interrupted = True
            raise KeyboardInterrupt("simulated process stop before journal finalization")
        original(root, journal)

    monkeypatch.setattr(hm, "_write_journal", interrupt_applied)
    try:
        hm.apply(tmp_path)
    except KeyboardInterrupt:
        pass
    else:  # pragma: no cover - assertion aid
        raise AssertionError("simulated interruption did not fire")

    assert json.loads((tmp_path / ".engineering" / "manifest.json").read_text())["version"] == 2
    recovered = hm.apply(tmp_path)
    assert recovered["status"] == "applied"
    assert recovered["recovered"] is True
    assert recovered["operations"] == [
        {
            "action": "finalize-journal",
            "migration_id": hm.SUBSYSTEM_REGISTRY_MIGRATION_ID,
        }
    ]


def test_apply_requires_the_schema_1_local_journal_ignore(tmp_path: Path) -> None:
    _write_manifest(tmp_path, {"version": 1})
    (tmp_path / ".engineering" / ".gitignore").unlink()
    _write_legacy_registry(tmp_path)
    before = _files(tmp_path)

    blocked = hm.apply(tmp_path)

    assert blocked["status"] == "blocked"
    assert {item["code"] for item in blocked["blockers"]} >= {
        "missing-local-ignore"
    }
    assert _files(tmp_path) == before


def test_restore_recovers_exact_prior_manifest_and_path_then_reapply_works(
    tmp_path: Path,
) -> None:
    original_manifest = _write_manifest(
        tmp_path, {"version": 1, "skills": {"inactive": {"x": "reason"}}}
    )
    raw = _write_legacy_registry(tmp_path)
    hm.apply(tmp_path)

    restored = hm.restore(tmp_path, hm.SUBSYSTEM_REGISTRY_MIGRATION_ID)

    assert restored["status"] == "restored"
    assert (tmp_path / ".engineering" / "manifest.json").read_bytes() == original_manifest
    assert (tmp_path / ".claude" / "subsystems.yaml").read_bytes() == raw
    assert not (tmp_path / ".engineering" / "subsystems.yaml").exists()

    reapplied = hm.apply(tmp_path)
    assert reapplied["status"] == "applied"
    assert (tmp_path / ".engineering" / "subsystems.yaml").read_bytes() == raw


def test_copied_stdlib_runner_reaches_final_host_state(tmp_path: Path) -> None:
    library = tmp_path / "library"
    script = library / "scripts" / "host_migrations.py"
    common = library / ".claude" / "skills" / "_common"
    script.parent.mkdir(parents=True)
    common.mkdir(parents=True)
    shutil.copy2(MIGRATIONS_PATH, script)
    shutil.copy2(
        REPO_ROOT / ".claude" / "skills" / "_common" / "engineering_home.py",
        common / "engineering_home.py",
    )
    host = tmp_path / "host"
    _write_manifest(host, {"version": 1})
    raw = _write_legacy_registry(host)

    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(script),
            "--project-root",
            str(host),
            "apply",
        ],
        cwd=host,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "applied"
    assert (host / ".engineering" / "subsystems.yaml").read_bytes() == raw
    assert json.loads((host / ".engineering" / "manifest.json").read_text())["version"] == 2
