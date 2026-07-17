from __future__ import annotations

import fcntl
import hashlib
import os
from pathlib import Path
import runpy
import socket
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from _lib.distribution_contracts import canonical_json_bytes, canonical_sha256
from _lib.skill_bundle import materialize_install_image, verify_release_bundle
from _lib.skill_installer import (
    JOURNAL_PATH,
    TRANSACTION_PREFIX,
    LifecycleError,
    LifecycleInput,
    NativeDiscoveryAdapter,
    ValidatedMigrationPlan,
    activate,
    deactivate,
    install,
    rollback,
    set_mode,
    uninstall,
    update,
    verify,
)


SURFACE_PATHS = {
    "claude-code": ".claude/skills/{public-name}/SKILL.md",
    "codex": "skills/{public-name}/SKILL.md",
}


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _row(path: str, content: bytes) -> dict[str, Any]:
    return {"path": path, "size": len(content), "sha256": _sha(content)}


def _write(root: Path, relative: str, content: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _contract(surfaces: tuple[str, ...]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "contract_version": 1,
        "surfaces": [
            {
                "surface_id": surface,
                "generated_identity": {
                    "which_shape": SURFACE_PATHS[surface].replace("{public-name}", "which-shape"),
                    "which_skill": SURFACE_PATHS[surface].replace("{public-name}", "which-skill"),
                    "alias_template": SURFACE_PATHS[surface],
                },
                "activation": {
                    "temporary_activation": "unsupported",
                    "terminal_wrapper": None,
                    "startup_cleanup": None,
                },
                "discovery": {"offline_non_model": True},
            }
            for surface in surfaces
        ],
    }


def _image(
    tmp_path: Path,
    version: str,
    *,
    surfaces: tuple[str, ...] = ("claude-code", "codex"),
    portfolio: tuple[str, ...] = ("plan-feature", "which-shape", "which-skill"),
    aliases: dict[str, str] | None = None,
) -> LifecycleInput:
    root = tmp_path / f"image-{version}"
    root.mkdir()
    catalog_rows: list[dict[str, Any]] = []
    canonical_sources: dict[str, str] = {}
    for name in portfolio:
        content = f"---\nname: {name}\n---\n{version}:{name}\n".encode()
        path = f".engineering/catalog/{version}/{name}"
        _write(root, path, content)
        catalog_rows.append(_row(path, content))
        canonical_sources[name] = path

    bootstrap_rows: list[dict[str, Any]] = []
    generated: list[dict[str, Any]] = []
    trees: list[dict[str, Any]] = []
    for surface in surfaces:
        surface_rows: list[dict[str, Any]] = []
        for name in ("which-shape", "which-skill"):
            path = SURFACE_PATHS[surface].replace("{public-name}", name)
            content = (root / canonical_sources[name]).read_bytes()
            _write(root, path, content)
            row = _row(path, content)
            bootstrap_rows.append(row)
            surface_rows.append(row)
            generated.append({"ownership_class": "bootstrap", "surface_id": surface, **row})
        trees.append(
            {
                "surface_id": surface,
                "file_count": len(surface_rows),
                "tree_sha256": canonical_sha256(sorted(surface_rows, key=lambda row: row["path"])),
            }
        )

    journal = canonical_json_bytes(
        {
            "schema_version": 1,
            "state": "clean",
            "operation": None,
            "transaction_id": None,
            "prior_manifest_sha256": None,
            "changes": [],
        }
    )
    journal_path = ".engineering/skill-installer-recovery-v1.json"
    _write(root, journal_path, journal)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "manifest_sha256": "0" * 64,
        "manifest_generation": 1,
        "previous_manifest_sha256": None,
        "bundle_version": version,
        "release_root_sha256": _sha(f"release:{version}".encode()),
        "bundle_index_sha256": _sha(f"bundle:{version}".encode()),
        "surface_activation_contract_sha256": _sha(canonical_json_bytes(_contract(surfaces))),
        "catalog_hash": _sha(f"catalog:{version}".encode()),
        "mode": "router-only",
        "activation_records": [],
        "surface_set": list(surfaces),
        "owned_paths": {
            "catalog_store": catalog_rows,
            "bootstrap_projections": bootstrap_rows,
            "activation_projections": [],
            "full_discovery_projections": [],
            "activation_state": [],
            "recovery_journal": [_row(journal_path, journal)],
            "generated_links": [],
        },
        "generated_files": generated,
        "bootstrap_trees": trees,
        "recovery": {
            "state": "clean",
            "journal_path": journal_path,
            "journal_sha256": _sha(journal),
            "temporary_records": [],
        },
        "cleanup": {"state": "clean", "last_cleaned_generation": 1, "failure_code": None},
        "delegation_policy": {
            "dispatcher_policy_version": 1,
            "project_lane_limit": 1,
            "delegation_depth": 1,
            "max_workflow_packs": 16,
            "max_dispatches_per_pack": 2,
            "deadline_seconds": 1200,
            "total_token_budget": 32768,
            "output_token_budget": 8192,
            "fallback_reasons": [
                "conversation_state_required",
                "user_interaction_required",
                "nondelegable_authority_required",
                "surface_worker_unsupported",
                "user_confirmed_after_worker_failure",
            ],
        },
    }
    manifest["manifest_sha256"] = canonical_sha256(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    )
    manifest_path = ".engineering/installed-manifest-v1.json"
    _write(root, manifest_path, canonical_json_bytes(manifest))
    return LifecycleInput.from_verified(
        root=root,
        manifest=manifest,
        surface_contract=_contract(surfaces),
        canonical_sources=canonical_sources,
        portfolio=portfolio,
        aliases=aliases or {},
    )


class FilesystemAdapter(NativeDiscoveryAdapter):
    offline_non_model = True

    def __init__(self, *, fail: bool = False, allow_links: bool = False) -> None:
        self.fail = fail
        self.allow_links = allow_links

    def discover(self, project_root: Path, surface_id: str) -> set[str]:
        if self.fail:
            return {"wrong"}
        template = SURFACE_PATHS[surface_id]
        prefix, suffix = template.split("{public-name}")
        names: set[str] = set()
        base = project_root / prefix
        if not base.exists():
            return names
        for candidate in base.parent.glob(f"{base.name}*{suffix}") if not prefix.endswith("/") else ():
            del candidate
        # All v1 identities put the public name in the directory before the file.
        discovery_root = project_root / prefix.rstrip("/")
        if discovery_root.exists():
            for path in discovery_root.rglob(Path(suffix).name):
                relative = path.relative_to(project_root).as_posix()
                if relative.startswith(prefix) and relative.endswith(suffix):
                    names.add(relative[len(prefix) : len(relative) - len(suffix)])
        return names

    def proves_generated_links(self, surface_id: str) -> bool:
        del surface_id
        return self.allow_links


def _tree(root: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for path in root.rglob("*"):
        if any(part.startswith(".skill-installer-txn") for part in path.parts):
            continue
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[relative] = f"link:{os.readlink(path)}".encode()
        elif path.is_dir():
            result[relative] = b"directory"
        elif path.is_file():
            result[relative] = path.read_bytes()
    return result


def test_install_verify_idempotence_and_uninstall_restore_host(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write(project, "HOST.txt", b"host sentinel\n")
    before = _tree(project)
    data = _image(tmp_path, "1.0.0")
    adapter = FilesystemAdapter()

    first = install(project, data, adapter=adapter)
    second = install(project, data, adapter=adapter)
    assert second == first
    assert verify(project, adapter=adapter) == first
    assert adapter.discover(project, "claude-code") == {"which-shape", "which-skill"}

    uninstall(project, adapter=adapter)
    uninstall(project, adapter=adapter)
    assert _tree(project) == before


def test_verified_multisurface_bundle_reaches_transactional_host_boundary(
    tmp_path: Path,
) -> None:
    bundle_helpers = runpy.run_path(str(ROOT / "tests/test_skill_bundle.py"))
    bundle_root, digest = bundle_helpers["_build"](tmp_path, "lifecycle-bundle")
    bundle = verify_release_bundle(bundle_root, digest)
    image = tmp_path / "trusted-image"
    manifest = materialize_install_image(
        bundle,
        image,
        recipe_ids=["claude-bootstrap", "codex-bootstrap"],
    )
    rows = [
        row for row in bundle.bundle_index["blobs"] if row["kind"] == "router"
    ]
    prefix = f".engineering/catalog/{bundle.bundle_index_sha256}/"
    data = LifecycleInput.from_verified(
        root=image,
        manifest=manifest,
        surface_contract=bundle.surface_contract,
        canonical_sources={row["id"]: f"{prefix}{row['path']}" for row in rows},
        portfolio=[row["id"] for row in rows],
        aliases={},
    )
    project = tmp_path / "trusted-project"
    project.mkdir()
    adapter = FilesystemAdapter()
    installed = install(project, data, adapter=adapter)
    assert installed["surface_set"] == ["claude-code", "codex"]
    assert verify(project, adapter=adapter)["manifest_sha256"] == installed["manifest_sha256"]


def test_failed_initial_discovery_restores_exact_cold_host(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write(project, "HOST.txt", b"host sentinel\n")
    before = _tree(project)
    with pytest.raises(LifecycleError, match="native discovery mismatch"):
        install(project, _image(tmp_path, "1.0.0"), adapter=FilesystemAdapter(fail=True))
    assert _tree(project) == before


def test_activation_deactivation_and_full_discovery_are_exact(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    adapter = FilesystemAdapter()
    install(project, _image(tmp_path, "1.0.0"), adapter=adapter)

    activated = activate(project, "plan-feature", adapter=adapter)
    assert activated["activation_records"] == [
        {"public_name": "plan-feature", "canonical_target": "plan-feature"}
    ]
    assert adapter.discover(project, "codex") == {
        "plan-feature",
        "which-shape",
        "which-skill",
    }
    assert activate(project, "plan-feature", adapter=adapter) == activated

    full = set_mode(project, "full-discovery", adapter=adapter)
    assert full["mode"] == "full-discovery"
    assert adapter.discover(project, "claude-code") == {
        "plan-feature",
        "which-shape",
        "which-skill",
    }
    routed = set_mode(project, "router-only", adapter=adapter)
    assert routed["activation_records"] == activated["activation_records"]
    assert deactivate(project, "plan-feature", adapter=adapter)["activation_records"] == []
    assert adapter.discover(project, "claude-code") == {"which-shape", "which-skill"}


def test_alias_activation_preserves_public_name(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    adapter = FilesystemAdapter()
    install(
        project,
        _image(tmp_path, "1.0.0", aliases={"plan-feature-v1": "plan-feature"}),
        adapter=adapter,
    )
    manifest = activate(project, "plan-feature-v1", adapter=adapter)
    assert manifest["activation_records"] == [
        {"public_name": "plan-feature-v1", "canonical_target": "plan-feature"}
    ]
    assert "plan-feature-v1" in adapter.discover(project, "claude-code")


def test_update_downgrade_and_rollback_keep_two_generations(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    adapter = FilesystemAdapter()
    v1 = _image(tmp_path, "1.0.0")
    v2 = _image(tmp_path, "2.0.0")
    install(project, v1, adapter=adapter)
    activate(project, "plan-feature", adapter=adapter)

    upgraded = update(project, v2, adapter=adapter)
    assert upgraded["bundle_version"] == "2.0.0"
    assert upgraded["activation_records"][0]["public_name"] == "plan-feature"
    assert upgraded["previous_manifest_sha256"] is not None
    rolled_back = rollback(project, adapter=adapter)
    assert rolled_back["bundle_version"] == "1.0.0"
    assert rolled_back["previous_manifest_sha256"] == upgraded["manifest_sha256"]
    update(project, v2, adapter=adapter)
    with pytest.raises(LifecycleError, match="explicit allow_downgrade"):
        update(project, v1, adapter=adapter)
    downgraded = update(project, v1, adapter=adapter, allow_downgrade=True)
    assert downgraded["bundle_version"] == "1.0.0"


@pytest.mark.parametrize("attack", ["collision", "modified", "symlink", "adapter"])
def test_failed_transaction_restores_exact_host_and_installation(
    tmp_path: Path, attack: str
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    adapter = FilesystemAdapter()
    v1 = _image(tmp_path, "1.0.0")
    install(project, v1, adapter=adapter)
    before = _tree(project)
    v2 = _image(tmp_path, "2.0.0", portfolio=("new-skill", "which-shape", "which-skill"))
    if attack == "collision":
        _write(project, ".engineering/catalog/2.0.0/new-skill", b"host\n")
        expected = _tree(project)
    elif attack == "modified":
        (project / ".claude/skills/which-shape/SKILL.md").write_text("modified\n")
        expected = _tree(project)
    elif attack == "symlink":
        target = project / ".engineering/catalog/2.0.0"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(project)
        expected = _tree(project)
    else:
        expected = before

    with pytest.raises(LifecycleError):
        update(project, v2, adapter=FilesystemAdapter(fail=attack == "adapter"))
    assert _tree(project) == expected


def test_invalid_input_and_migration_plan_fail_before_mutation(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write(project, "sentinel", b"safe")
    before = _tree(project)
    data = _image(tmp_path, "1.0.0")
    data.manifest["owned_paths"]["catalog_store"].append(
        dict(data.manifest["owned_paths"]["catalog_store"][0])
    )
    with pytest.raises(LifecycleError):
        install(project, data, adapter=FilesystemAdapter())
    assert _tree(project) == before

    with pytest.raises(LifecycleError, match="validated migration plan"):
        install(
            project,
            _image(tmp_path, "1.0.1"),
            adapter=FilesystemAdapter(),
            migration_plan=ValidatedMigrationPlan.unverified_for_test(),
        )
    assert _tree(project) == before


def test_known_byte_identical_migration_is_injected_and_atomic(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    legacy = b"legacy toolkit header\n"
    _write(project, ".legacy/skill.md", legacy)
    plan = ValidatedMigrationPlan.from_verified(
        [{"action": "retire", **_row(".legacy/skill.md", legacy)}],
        plan_sha256=_sha(b"validated plan"),
    )
    install(project, _image(tmp_path, "1.0.0"), adapter=FilesystemAdapter(), migration_plan=plan)
    assert not (project / ".legacy/skill.md").exists()
    uninstall(project, adapter=FilesystemAdapter())
    assert not (project / ".legacy/skill.md").exists()


def test_generated_links_are_contained_hashed_and_adapter_proven(tmp_path: Path) -> None:
    data = _image(tmp_path, "1.0.0")
    link_path = ".engineering/linked-plan"
    target = data.canonical_sources["plan-feature"]
    data = data.with_generated_link(link_path, target)
    project = tmp_path / "project"
    project.mkdir()
    with pytest.raises(LifecycleError, match="generated links"):
        install(project, data, adapter=FilesystemAdapter())
    assert _tree(project) == {}
    install(project, data, adapter=FilesystemAdapter(allow_links=True))
    assert (project / link_path).is_symlink()
    verify(project, adapter=FilesystemAdapter(allow_links=True))


def test_denied_network_and_fail_closed_adapter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "project"
    project.mkdir()

    def denied(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", denied)
    install(project, _image(tmp_path, "1.0.0"), adapter=FilesystemAdapter())
    verify(project, adapter=FilesystemAdapter())
    assert (project / JOURNAL_PATH).stat().st_mode & 0o777 == 0o600
    assert (project / ".engineering/skill-installer-state-v1.json").stat().st_mode & 0o777 == 0o600

    bad = FilesystemAdapter()
    bad.offline_non_model = False
    with pytest.raises(LifecycleError, match="offline non-model"):
        verify(project, adapter=bad)


def test_manifest_corruption_and_owned_modification_block_uninstall(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    adapter = FilesystemAdapter()
    install(project, _image(tmp_path, "1.0.0"), adapter=adapter)
    owned = project / ".claude/skills/which-shape/SKILL.md"
    owned.write_text("host modification\n")
    before = _tree(project)
    with pytest.raises(LifecycleError, match="modified owned"):
        uninstall(project, adapter=adapter)
    assert _tree(project) == before


def test_uninstall_discovery_failure_restores_exact_installation(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    adapter = FilesystemAdapter()
    install(project, _image(tmp_path, "1.0.0"), adapter=adapter)
    before = _tree(project)
    with pytest.raises(LifecycleError, match="still exposes"):
        uninstall(project, adapter=FilesystemAdapter(fail=True))
    assert _tree(project) == before
    verify(project, adapter=adapter)


def test_temporary_activation_is_explicitly_unsupported(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    install(project, _image(tmp_path, "1.0.0"), adapter=FilesystemAdapter())
    with pytest.raises(LifecycleError, match="temporary activation unsupported"):
        activate(
            project,
            "plan-feature",
            adapter=FilesystemAdapter(),
            invocation_id="123e4567-e89b-42d3-a456-426614174000",
        )


def test_traversal_corrupt_checksum_and_image_symlink_fail_before_host_mutation(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write(project, "sentinel", b"safe")
    before = _tree(project)

    traversal = _image(tmp_path, "1.0.0")
    traversal.manifest["owned_paths"]["catalog_store"][0]["path"] = "../escape"
    with pytest.raises(LifecycleError):
        install(project, traversal, adapter=FilesystemAdapter())
    assert _tree(project) == before

    with pytest.raises(LifecycleError, match="dot segment"):
        _image(tmp_path, "1.0.3").with_generated_link(
            "./explicit-dot", ".engineering/catalog/1.0.3/plan-feature"
        )

    corrupt = _image(tmp_path, "1.0.1")
    (corrupt.root / corrupt.canonical_sources["plan-feature"]).write_text("tampered\n")
    with pytest.raises(LifecycleError, match="modified owned"):
        install(project, corrupt, adapter=FilesystemAdapter())
    assert _tree(project) == before

    linked = _image(tmp_path, "1.0.2")
    source = linked.root / linked.canonical_sources["plan-feature"]
    source.unlink()
    source.symlink_to(linked.root / linked.canonical_sources["which-shape"])
    with pytest.raises(LifecycleError):
        install(project, linked, adapter=FilesystemAdapter())
    assert _tree(project) == before


def test_project_lock_rejects_concurrent_lifecycle_command(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    descriptor = os.open(project, os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(LifecycleError, match="holds the lock"):
            install(project, _image(tmp_path, "1.0.0"), adapter=FilesystemAdapter())
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
    assert _tree(project) == {}


def test_project_root_symlink_is_rejected_without_target_mutation(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    _write(target, "sentinel", b"safe")
    before = _tree(target)
    linked_root = tmp_path / "linked-project"
    linked_root.symlink_to(target)
    with pytest.raises(LifecycleError, match="project root must not be a symlink"):
        install(linked_root, _image(tmp_path, "1.0.0"), adapter=FilesystemAdapter())
    assert _tree(target) == before


def test_startup_recovery_restores_interrupted_owned_write(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    adapter = FilesystemAdapter()
    manifest = install(project, _image(tmp_path, "1.0.0"), adapter=adapter)
    target_relative = ".claude/skills/which-shape/SKILL.md"
    target = project / target_relative
    original = target.read_bytes()
    journal = project / JOURNAL_PATH
    clean_journal = journal.read_bytes()
    transaction_id = "123e4567-e89b-42d3-a456-426614174000"
    transaction_relative = f"{TRANSACTION_PREFIX}{transaction_id}"
    transaction = project / transaction_relative
    for relative, content in ((target_relative, original), (JOURNAL_PATH, clean_journal)):
        _write(transaction / "backup", relative, content)
    _write(transaction, "owner-v1", b"engineering-skills\n")
    target.write_text("interrupted replacement\n")
    changes = [
        {
            "path": target_relative,
            "existed": True,
            "kind": "file",
            "size": len(original),
            "sha256": _sha(original),
            "link_target": None,
        },
        {
            "path": JOURNAL_PATH,
            "existed": True,
            "kind": "file",
            "size": len(clean_journal),
            "sha256": _sha(clean_journal),
            "link_target": None,
        },
    ]
    interrupted = {
        "schema_version": 1,
        "state": "committing",
        "operation": "update",
        "transaction_id": transaction_id,
        "prior_manifest_sha256": manifest["manifest_sha256"],
        "transaction_path": transaction_relative,
        "changes": changes,
    }
    journal.write_bytes(canonical_json_bytes(interrupted))

    assert verify(project, adapter=adapter)["manifest_sha256"] == manifest["manifest_sha256"]
    assert target.read_bytes() == original
    assert not transaction.exists()


def test_stale_activation_stops_update_and_only_one_previous_is_retained(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    adapter = FilesystemAdapter()
    v1 = _image(tmp_path, "1.0.0")
    install(project, v1, adapter=adapter)
    activate(project, "plan-feature", adapter=adapter)
    before = _tree(project)
    stale = _image(
        tmp_path,
        "2.0.0",
        portfolio=("other-skill", "which-shape", "which-skill"),
    )
    with pytest.raises(LifecycleError, match="invalidates activation"):
        update(project, stale, adapter=adapter)
    assert _tree(project) == before

    deactivate(project, "plan-feature", adapter=adapter)
    v2 = _image(tmp_path, "2.0.1")
    update(project, v2, adapter=adapter)
    v3 = _image(tmp_path, "3.0.0")
    current = update(project, v3, adapter=adapter)
    previous_roots = {
        Path(row["path"]).parts[2]
        for row in current["owned_paths"]["catalog_store"]
        if row["path"].startswith(".engineering/skill-installer-previous/")
    }
    assert len(previous_roots) == 1
