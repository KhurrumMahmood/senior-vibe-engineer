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


def _write_legacy_maps(root: Path) -> dict[str, bytes]:
    directory = root / ".claude" / "docs" / "subsystems"
    directory.mkdir(parents=True, exist_ok=True)
    payloads = {
        "billing.md": b"# Billing\n\nExact project map.\n",
        "nested/worker.md": b"# Worker\n",
    }
    for relative, raw in payloads.items():
        path = directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return payloads


def _files(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def test_plan_is_read_only_and_names_the_exact_move(tmp_path: Path) -> None:
    _write_manifest(tmp_path, {"version": 1, "skills": {"default": "active"}})
    raw = _write_legacy_registry(tmp_path)
    _write_legacy_maps(tmp_path)
    (tmp_path / "user.txt").write_text("preserve me\n", encoding="utf-8")
    before = _files(tmp_path)

    report = hm.plan(tmp_path)

    assert report["status"] == "ready"
    assert report["current_schema"] == 1
    assert report["target_schema"] == 3
    assert report["pending_migrations"] == [
        hm.SUBSYSTEM_REGISTRY_MIGRATION_ID,
        hm.SUBSYSTEM_MAPS_MIGRATION_ID,
    ]
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
        {
            "action": "move",
            "from": ".claude/docs/subsystems",
            "to": ".engineering/docs/subsystems",
            "sha256": hm._content_digest(
                tmp_path / ".claude" / "docs" / "subsystems", "directory"
            ),
        },
        {
            "action": "update-manifest",
            "path": ".engineering/manifest.json",
            "from_schema": 2,
            "to_schema": 3,
        },
    ]
    assert report["blockers"] == []
    assert _files(tmp_path) == before


def test_apply_moves_exact_bytes_updates_manifest_and_reapply_is_noop(tmp_path: Path) -> None:
    _write_manifest(tmp_path, {"version": 1, "skills": {"default": "active"}})
    raw = _write_legacy_registry(tmp_path)
    maps = _write_legacy_maps(tmp_path)
    sentinel = tmp_path / ".claude" / "CLAUDE.md"
    sentinel.write_text("user-owned\n", encoding="utf-8")

    applied = hm.apply(tmp_path)

    assert applied["status"] == "applied"
    assert not (tmp_path / ".claude" / "subsystems.yaml").exists()
    assert (tmp_path / ".engineering" / "subsystems.yaml").read_bytes() == raw
    manifest = json.loads((tmp_path / ".engineering" / "manifest.json").read_text())
    assert manifest["version"] == 3
    assert manifest["skills"] == {"default": "active"}
    assert manifest["applied_migrations"] == [
        hm.SUBSYSTEM_REGISTRY_MIGRATION_ID,
        hm.SUBSYSTEM_MAPS_MIGRATION_ID,
    ]
    assert {
        str(path.relative_to(tmp_path / ".engineering/docs/subsystems")): path.read_bytes()
        for path in sorted((tmp_path / ".engineering/docs/subsystems").rglob("*.md"))
    } == maps
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
    assert json.loads((tmp_path / ".engineering" / "manifest.json").read_text())["version"] == 3


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
    assert recovered["operations"][:1] == [
        {
            "action": "finalize-journal",
            "migration_id": hm.SUBSYSTEM_REGISTRY_MIGRATION_ID,
        }
    ]
    assert recovered["operations"][-1] == {
        "action": "update-manifest",
        "path": ".engineering/manifest.json",
        "from_schema": 2,
        "to_schema": 3,
    }


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
    maps = _write_legacy_maps(tmp_path)
    hm.apply(tmp_path)

    maps_restored = hm.restore(tmp_path, hm.SUBSYSTEM_MAPS_MIGRATION_ID)

    assert maps_restored["status"] == "restored"
    assert json.loads((tmp_path / ".engineering" / "manifest.json").read_text())["version"] == 2
    assert {
        str(path.relative_to(tmp_path / ".claude/docs/subsystems")): path.read_bytes()
        for path in sorted((tmp_path / ".claude/docs/subsystems").rglob("*.md"))
    } == maps
    assert not (tmp_path / ".engineering/docs/subsystems").exists()

    restored = hm.restore(tmp_path, hm.SUBSYSTEM_REGISTRY_MIGRATION_ID)

    assert restored["status"] == "restored"
    assert (tmp_path / ".engineering" / "manifest.json").read_bytes() == original_manifest
    assert (tmp_path / ".claude" / "subsystems.yaml").read_bytes() == raw
    assert not (tmp_path / ".engineering" / "subsystems.yaml").exists()

    reapplied = hm.apply(tmp_path)
    assert reapplied["status"] == "applied"
    assert (tmp_path / ".engineering" / "subsystems.yaml").read_bytes() == raw
    assert (tmp_path / ".engineering/docs/subsystems/billing.md").read_bytes() == maps[
        "billing.md"
    ]


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
    maps = _write_legacy_maps(host)

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
    assert (host / ".engineering/docs/subsystems/billing.md").read_bytes() == maps[
        "billing.md"
    ]
    assert json.loads((host / ".engineering" / "manifest.json").read_text())["version"] == 3


def test_schema_2_host_applies_only_the_map_move_and_preserves_modes(
    tmp_path: Path,
) -> None:
    _write_manifest(
        tmp_path,
        {
            "version": 2,
            "applied_migrations": [hm.SUBSYSTEM_REGISTRY_MIGRATION_ID],
            "skills": {"default": "active"},
        },
    )
    maps = _write_legacy_maps(tmp_path)
    source = tmp_path / ".claude/docs/subsystems/billing.md"
    source.chmod(0o640)
    before = _files(tmp_path)

    preview = hm.plan(tmp_path)

    assert preview["status"] == "ready"
    assert preview["pending_migrations"] == [hm.SUBSYSTEM_MAPS_MIGRATION_ID]
    assert preview["operations"][0]["action"] == "move"
    assert preview["operations"][1] == {
        "action": "update-manifest",
        "path": ".engineering/manifest.json",
        "from_schema": 2,
        "to_schema": 3,
    }
    assert _files(tmp_path) == before

    applied = hm.apply(tmp_path)

    assert applied["status"] == "applied"
    assert not (tmp_path / ".claude/docs/subsystems").exists()
    destination = tmp_path / ".engineering/docs/subsystems/billing.md"
    assert destination.read_bytes() == maps["billing.md"]
    assert destination.stat().st_mode & 0o777 == 0o640
    manifest = json.loads((tmp_path / ".engineering/manifest.json").read_text())
    assert manifest["version"] == 3
    assert manifest["skills"] == {"default": "active"}
    assert manifest["applied_migrations"] == list(hm.MIGRATION_IDS)


def test_schema_3_replay_is_a_byte_for_byte_noop(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        {"version": 3, "applied_migrations": list(hm.MIGRATION_IDS)},
    )
    before = _files(tmp_path)

    preview = hm.plan(tmp_path)
    repeated = hm.apply(tmp_path)

    assert preview["status"] == "current"
    assert preview["pending_migrations"] == []
    assert preview["operations"] == []
    assert repeated["status"] == "current"
    assert _files(tmp_path) == before


def test_map_move_refuses_destination_collision_and_nested_symlink(
    tmp_path: Path,
) -> None:
    _write_manifest(
        tmp_path,
        {"version": 2, "applied_migrations": [hm.SUBSYSTEM_REGISTRY_MIGRATION_ID]},
    )
    _write_legacy_maps(tmp_path)
    destination = tmp_path / ".engineering/docs/subsystems"
    destination.mkdir(parents=True)
    (destination / "user.md").write_text("do not overwrite\n", encoding="utf-8")
    before = _files(tmp_path)

    collision = hm.apply(tmp_path)

    assert collision["status"] == "blocked"
    assert "canonical-path-occupied" in {
        item["code"] for item in collision["blockers"]
    }
    assert _files(tmp_path) == before

    for path in sorted(destination.rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    destination.rmdir()
    link = tmp_path / ".claude/docs/subsystems/external.md"
    link.symlink_to(tmp_path / "outside.md")
    before = _files(tmp_path)

    unsafe = hm.apply(tmp_path)

    assert unsafe["status"] == "blocked"
    assert "directory contains a symlink" in "\n".join(
        item["detail"] for item in unsafe["blockers"]
    )
    assert _files(tmp_path) == before


def test_schema_2_interruption_before_manifest_write_resumes(tmp_path: Path, monkeypatch) -> None:
    _write_manifest(
        tmp_path,
        {"version": 2, "applied_migrations": [hm.SUBSYSTEM_REGISTRY_MIGRATION_ID]},
    )
    maps = _write_legacy_maps(tmp_path)
    original = hm._write_manifest
    interrupted = False

    def stop_before_marker(root: Path, manifest: dict) -> bytes:
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            raise KeyboardInterrupt("stop before schema-3 marker")
        return original(root, manifest)

    monkeypatch.setattr(hm, "_write_manifest", stop_before_marker)
    try:
        hm.apply(tmp_path)
    except KeyboardInterrupt:
        pass
    else:  # pragma: no cover - assertion aid
        raise AssertionError("simulated interruption did not fire")

    assert json.loads((tmp_path / ".engineering/manifest.json").read_text())["version"] == 2
    assert (tmp_path / ".engineering/docs/subsystems/billing.md").read_bytes() == maps[
        "billing.md"
    ]
    resumed = hm.apply(tmp_path)
    assert resumed["status"] == "applied"
    assert resumed["recovered"] is True


def test_schema_2_interruption_after_manifest_write_finalizes(tmp_path: Path, monkeypatch) -> None:
    _write_manifest(
        tmp_path,
        {"version": 2, "applied_migrations": [hm.SUBSYSTEM_REGISTRY_MIGRATION_ID]},
    )
    _write_legacy_maps(tmp_path)
    original = hm._write_journal
    interrupted = False

    def stop_after_marker(root: Path, journal: dict) -> None:
        nonlocal interrupted
        if (
            journal.get("migration_id") == hm.SUBSYSTEM_MAPS_MIGRATION_ID
            and journal.get("state") == "applied"
            and not interrupted
        ):
            interrupted = True
            raise KeyboardInterrupt("stop after schema-3 marker")
        original(root, journal)

    monkeypatch.setattr(hm, "_write_journal", stop_after_marker)
    try:
        hm.apply(tmp_path)
    except KeyboardInterrupt:
        pass
    else:  # pragma: no cover - assertion aid
        raise AssertionError("simulated interruption did not fire")

    assert json.loads((tmp_path / ".engineering/manifest.json").read_text())["version"] == 3
    resumed = hm.apply(tmp_path)
    assert resumed["status"] == "applied"
    assert resumed["recovered"] is True
    assert resumed["operations"] == [
        {
            "action": "finalize-journal",
            "migration_id": hm.SUBSYSTEM_MAPS_MIGRATION_ID,
        }
    ]


def test_schema_2_tool_refuses_schema_3_host_without_writes(tmp_path: Path) -> None:
    library = tmp_path / "old-library"
    script = library / "scripts" / "host_migrations.py"
    common = library / ".claude" / "skills" / "_common"
    script.parent.mkdir(parents=True)
    common.mkdir(parents=True)
    shutil.copy2(MIGRATIONS_PATH, script)
    helper = (REPO_ROOT / ".claude/skills/_common/engineering_home.py").read_text(
        encoding="utf-8"
    )
    (common / "engineering_home.py").write_text(
        helper.replace("MANIFEST_VERSION = 3", "MANIFEST_VERSION = 2"),
        encoding="utf-8",
    )
    host = tmp_path / "host"
    _write_manifest(host, {"version": 3, "applied_migrations": list(hm.MIGRATION_IDS)})
    before = _files(host)

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

    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "newer-than-tool"
    assert _files(host) == before


def test_manifest_rejects_unknown_duplicate_and_out_of_order_records(
    tmp_path: Path,
) -> None:
    cases = (
        (
            "unknown",
            [*hm.MIGRATION_IDS, "9999-unknown"],
            "unknown-application-record",
        ),
        (
            "duplicate",
            [*hm.MIGRATION_IDS, hm.SUBSYSTEM_MAPS_MIGRATION_ID],
            "duplicate-application-record",
        ),
        (
            "out-of-order",
            list(reversed(hm.MIGRATION_IDS)),
            "out-of-order-application-record",
        ),
    )
    for name, records, code in cases:
        host = tmp_path / name
        _write_manifest(host, {"version": 3, "applied_migrations": records})
        before = _files(host)

        report = hm.apply(host)

        assert report["status"] == "blocked"
        assert code in {item["code"] for item in report["blockers"]}
        assert _files(host) == before


def test_map_restore_refuses_changed_canonical_content_and_occupied_legacy_path(
    tmp_path: Path,
) -> None:
    changed = tmp_path / "changed"
    _write_manifest(
        changed,
        {"version": 2, "applied_migrations": [hm.SUBSYSTEM_REGISTRY_MIGRATION_ID]},
    )
    _write_legacy_maps(changed)
    assert hm.apply(changed)["status"] == "applied"
    canonical = changed / ".engineering/docs/subsystems/billing.md"
    canonical.write_text("changed after migration\n", encoding="utf-8")
    before = _files(changed)

    refused_change = hm.restore(changed, hm.SUBSYSTEM_MAPS_MIGRATION_ID)

    assert refused_change["status"] == "blocked"
    assert refused_change["blockers"] == [
        {
            "code": "canonical-content-changed",
            "detail": ".engineering/docs/subsystems",
        }
    ]
    assert _files(changed) == before

    occupied = tmp_path / "occupied"
    _write_manifest(
        occupied,
        {"version": 2, "applied_migrations": [hm.SUBSYSTEM_REGISTRY_MIGRATION_ID]},
    )
    _write_legacy_maps(occupied)
    assert hm.apply(occupied)["status"] == "applied"
    legacy = occupied / ".claude/docs/subsystems"
    legacy.mkdir(parents=True)
    (legacy / "user.md").write_text("user-owned\n", encoding="utf-8")
    before = _files(occupied)

    refused_occupied = hm.restore(occupied, hm.SUBSYSTEM_MAPS_MIGRATION_ID)

    assert refused_occupied["status"] == "blocked"
    assert refused_occupied["blockers"] == [
        {
            "code": "legacy-path-occupied",
            "detail": ".claude/docs/subsystems",
        }
    ]
    assert _files(occupied) == before
