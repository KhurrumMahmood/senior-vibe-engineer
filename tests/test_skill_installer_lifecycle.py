from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import socket
import subprocess
import sys
from typing import Any
import uuid

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from _lib.distribution_contracts import CONTRACT_ROOT, canonical_json_bytes, canonical_sha256
from _lib.skill_bundle import BlobSource, BundleTrustError, build_release_bundle
from _lib import skill_installer as lifecycle
from _lib.skill_installer import (
    JOURNAL_PATH,
    MANIFEST_PATH,
    STATE_PATH,
    TRANSACTION_PREFIX,
    BundleInstallRequest,
    LifecycleError,
    activate,
    deactivate,
    install,
    preview_migration,
    rollback,
    set_mode,
    uninstall,
    update,
    verify,
)


SURFACE_TEMPLATES = {
    "claude-code": ".claude/skills/{public-name}/SKILL.md",
    "codex": "skills/{public-name}/SKILL.md",
}


class FilesystemDiscovery:
    """Test-only semantic stand-in; production intentionally ships no v1 adapter."""

    def __init__(self) -> None:
        self.fail = False

    def discover(self, project_root: Path, surface_id: str) -> lifecycle._DiscoverySnapshot:
        template = SURFACE_TEMPLATES[surface_id]
        prefix, suffix = template.split("{public-name}")
        discovered: set[str] = set()
        for path in project_root.rglob(Path(suffix).name):
            relative = path.relative_to(project_root).as_posix()
            if relative.startswith(prefix) and relative.endswith(suffix):
                name = relative[len(prefix) : len(relative) - len(suffix)]
                if "/" not in name:
                    discovered.add(name)
        toolkit: set[str] = set()
        manifest_path = project_root / MANIFEST_PATH
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_bytes())
            for row in manifest["generated_files"]:
                if row["surface_id"] != surface_id:
                    continue
                relative = row["path"]
                if (
                    relative.startswith(prefix)
                    and relative.endswith(suffix)
                    and (project_root / relative).is_file()
                ):
                    name = relative[len(prefix) : len(relative) - len(suffix)]
                    if "/" not in name:
                        toolkit.add(name)
        if self.fail:
            toolkit = {"wrong"}
        return lifecycle._DiscoverySnapshot(
            toolkit_owned=frozenset(toolkit),
            host_owned=frozenset(discovered - toolkit),
        )

    def proves_generated_links(self, surface_id: str) -> bool:
        del surface_id
        return False


class FakeGeminiProcess:
    """Native-process stand-in that observes the real staged Gemini tree."""

    def __init__(self) -> None:
        self.version = "0.45.0"
        self.omit: set[str] = set()
        self.commands: list[tuple[str, ...]] = []
        self.isolation_roots: list[Path] = []

    def run(
        self,
        command: list[str],
        cwd: Path,
        env: dict[str, str],
        **bounds: object,
    ) -> lifecycle._NativeCommandResult:
        assert bounds == {
            "timeout_seconds": lifecycle._NATIVE_COMMAND_TIMEOUT_SECONDS,
            "output_limit_bytes": lifecycle._NATIVE_OUTPUT_LIMIT_BYTES,
        } or bounds == {}
        arguments = tuple(command[1:])
        assert arguments in {("--version",), ("skills", "list")}
        assert not {"install", "model", "npm", "npx", "package"}.intersection(command)
        assert set(env) == {
            "HOME",
            "LANG",
            "LC_ALL",
            "NO_COLOR",
            "PATH",
            "TMPDIR",
            "XDG_CACHE_HOME",
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "XDG_STATE_HOME",
        }
        isolation = Path(env["HOME"]).parent
        assert Path(env["TMPDIR"]).parent == isolation
        assert Path(env["XDG_CONFIG_HOME"]).parent == isolation
        assert (Path(env["HOME"]) / ".gemini/settings.json").read_bytes() == (
            b'{"privacy":{"usageStatisticsEnabled":false},'
            b'"security":{"folderTrust":{"enabled":false}},'
            b'"telemetry":{"enabled":false}}\n'
        )
        self.commands.append(tuple(command))
        self.isolation_roots.append(isolation)
        if arguments == ("--version",):
            return lifecycle._NativeCommandResult(0, f"{self.version}\n".encode(), b"")
        rows = []
        for path in sorted(cwd.glob(".gemini/skills/*/SKILL.md")):
            name = path.parent.name
            if name in self.omit:
                continue
            rows.append(
                f"{name} [Enabled]\n"
                "  Description: deterministic fake process\n"
                f"  Location:    {path.resolve()}\n\n"
            )
        stdout = (
            "Discovered Agent Skills:\n\n" + "".join(rows)
            if rows
            else "No skills discovered.\n"
        )
        return lifecycle._NativeCommandResult(0, stdout.encode(), b"")


@pytest.fixture
def discovery(monkeypatch: pytest.MonkeyPatch) -> FilesystemDiscovery:
    adapter = FilesystemDiscovery()
    monkeypatch.setattr(
        lifecycle, "_native_adapter", lambda contract, surface_set: adapter
    )
    return adapter


@pytest.fixture
def native_gemini(monkeypatch: pytest.MonkeyPatch) -> FakeGeminiProcess:
    process = FakeGeminiProcess()
    monkeypatch.setattr(lifecycle.shutil, "which", lambda name: "/runtime/gemini")
    monkeypatch.setattr(lifecycle, "_run_native_command", process.run)
    return process


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _bundle(
    tmp_path: Path,
    name: str,
    *,
    version: str = "1.0.0",
    include_plan: bool = True,
    plan_content: bytes = b"---\nname: plan-feature\ndescription: Plan a feature.\n---\nPlan v1.\n",
    legacy_files: dict[str, tuple[bytes, str]] | None = None,
    gemini_only: bool = False,
) -> BundleInstallRequest:
    helpers = runpy.run_path(str(ROOT / "tests/test_skill_bundle.py"))
    source = tmp_path / f"{name}-source"
    source.mkdir()
    blobs = helpers["_prepare_source"](source)
    if include_plan:
        (source / "plan-feature.md").write_bytes(plan_content)
        blobs.append(BlobSource("procedure", "plan-feature", "plan-feature.md", "text/markdown"))
    recipe_ids = ("claude-bootstrap", "codex-bootstrap")
    if gemini_only:
        gemini_recipe = {
            "schema_version": 1,
            "surface_id": "gemini",
            "manifest_locator": MANIFEST_PATH,
            "bootstrap_metadata_path": ".engineering/bootstrap/gemini/bootstrap-v1.json",
            "routers": [
                {
                    "canonical_name": "which-shape",
                    "blob_id": "which-shape",
                    "path": ".gemini/skills/which-shape/SKILL.md",
                },
                {
                    "canonical_name": "which-skill",
                    "blob_id": "which-skill",
                    "path": ".gemini/skills/which-skill/SKILL.md",
                },
            ],
            "runtime_files": [
                {
                    "blob_id": "router-runtime",
                    "path": ".engineering/bootstrap/gemini/runtime.py",
                }
            ],
        }
        (source / "gemini-recipe.json").write_bytes(canonical_json_bytes(gemini_recipe))
        blobs.append(
            BlobSource(
                "projection-recipe",
                "gemini-bootstrap",
                "gemini-recipe.json",
                "application/json",
            )
        )
        recipe_ids = ("gemini-bootstrap",)
    contract_root = CONTRACT_ROOT
    if legacy_files is not None:
        contract_root = tmp_path / f"{name}-contracts"
        shutil.copytree(CONTRACT_ROOT, contract_root)
        rows = [
            {"path": path, "size": len(content), "sha256": _sha(content), "role": role}
            for path, (content, role) in sorted(legacy_files.items())
        ]
        layout = {
            "layout_id": "legacy-retire",
            "manifest_id": "legacy-retire-manifest",
            "version_range": {"lower": "0.9.0", "upper": "0.9.0"},
            "release_root_sha256": "a" * 64,
            "tree_sha256": canonical_sha256(
                [{key: row[key] for key in ("path", "size", "sha256")} for row in rows]
            ),
            "files": rows,
            "action": "retire",
        }
        (contract_root / "legacy-layouts-v1.json").write_bytes(
            canonical_json_bytes({"schema_version": 1, "layouts": [layout]})
        )
    output = tmp_path / name
    digest = build_release_bundle(
        source,
        output,
        bundle_version=version,
        blobs=blobs,
        installer="installer.py",
        surface_activation_contract="surface-contract.json",
        contract_root=contract_root,
    )
    return BundleInstallRequest(output, digest, recipe_ids)


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): (
            f"link:{os.readlink(path)}".encode() if path.is_symlink() else path.read_bytes()
        )
        for path in root.rglob("*")
        if (path.is_file() or path.is_symlink())
        and not any(part.startswith(".skill-installer-txn-") for part in path.parts)
    }


def _state(project: Path) -> dict[str, Any]:
    return json.loads((project / STATE_PATH).read_bytes())


# spec:portable-skill-layer-distribution::IM-15
def test_production_rejects_abstract_discovery_without_mutation(tmp_path: Path) -> None:
    request = _bundle(tmp_path, "unsupported")
    project = tmp_path / "project"

    with pytest.raises(LifecycleError, match="claude-code, codex") as exc_info:
        install(project, request)

    assert "augment" not in str(exc_info.value)
    assert not (project / MANIFEST_PATH).exists()


@pytest.mark.parametrize(
    "surface_set",
    [
        ["claude-code"],
        ["codex"],
        ["augment"],
        ["cursor"],
        ["gemini", "claude-code"],
    ],
)
def test_non_gemini_or_mixed_native_surface_sets_remain_unsupported(
    surface_set: list[str],
) -> None:
    contract = runpy.run_path(str(ROOT / "tests/test_skill_bundle.py"))[
        "_surface_contract"
    ]()

    with pytest.raises(LifecycleError, match="unsupported for requested surface set"):
        lifecycle._native_adapter(contract, surface_set)


def test_gemini_native_lifecycle_preserves_host_set_and_is_idempotent(
    tmp_path: Path, native_gemini: FakeGeminiProcess
) -> None:
    request = _bundle(tmp_path, "gemini-native", gemini_only=True)
    project = tmp_path / "project"
    host = project / ".gemini/skills/host-skill/SKILL.md"
    host.parent.mkdir(parents=True)
    host.write_text(
        "---\nname: host-skill\ndescription: Host-owned skill.\n---\nHost.\n"
    )

    installed = install(project, request)
    repeated_install = install(project, request)
    assert repeated_install["manifest_sha256"] == installed["manifest_sha256"]
    assert installed["surface_set"] == ["gemini"]
    assert verify(project)["mode"] == "router-only"
    assert lifecycle._installed_adapter(project).proves_generated_links("gemini") is False

    activated = activate(project, "plan-feature")
    repeated_activation = activate(project, "plan-feature")
    assert repeated_activation["manifest_sha256"] == activated["manifest_sha256"]
    assert activated["activation_records"] == [
        {"public_name": "plan-feature", "canonical_target": "plan-feature"}
    ]

    full = set_mode(project, "full-discovery")
    assert set_mode(project, "full-discovery")["manifest_sha256"] == full["manifest_sha256"]
    assert full["mode"] == "full-discovery"
    router = set_mode(project, "router-only")
    assert router["mode"] == "router-only"
    deactivated = deactivate(project, "plan-feature")
    assert deactivate(project, "plan-feature")["manifest_sha256"] == deactivated[
        "manifest_sha256"
    ]
    assert deactivated["activation_records"] == []

    uninstall(project)
    uninstall(project)
    assert host.is_file()
    assert host.read_text().endswith("Host.\n")
    assert not (project / MANIFEST_PATH).exists()
    assert {tuple(command[1:]) for command in native_gemini.commands} == {
        ("--version",),
        ("skills", "list"),
    }
    assert all(not root.exists() for root in native_gemini.isolation_roots)


def test_gemini_native_discovery_mismatch_rolls_back_exact_activation(
    tmp_path: Path, native_gemini: FakeGeminiProcess
) -> None:
    request = _bundle(tmp_path, "gemini-mismatch", gemini_only=True)
    project = tmp_path / "project"
    install(project, request)
    before = _files(project)
    native_gemini.omit.add("plan-feature")

    with pytest.raises(LifecycleError, match="native discovery mismatch"):
        activate(project, "plan-feature")

    native_gemini.omit.clear()
    assert _files(project) == before
    assert verify(project)["activation_records"] == []


def test_gemini_native_adapter_rejects_missing_version_and_contract_before_mutation(
    tmp_path: Path,
    native_gemini: FakeGeminiProcess,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _bundle(tmp_path, "gemini-preflight", gemini_only=True)

    monkeypatch.setattr(lifecycle.shutil, "which", lambda name: None)
    missing_project = tmp_path / "missing-project"
    with pytest.raises(LifecycleError, match="executable is unavailable"):
        install(missing_project, request)
    assert not missing_project.exists()

    monkeypatch.setattr(lifecycle.shutil, "which", lambda name: "/runtime/gemini")
    native_gemini.version = "0.45.1"
    wrong_project = tmp_path / "wrong-project"
    with pytest.raises(LifecycleError, match="exact version 0.45.0"):
        install(wrong_project, request)
    assert not wrong_project.exists()

    contract = runpy.run_path(str(ROOT / "tests/test_skill_bundle.py"))[
        "_surface_contract"
    ]()
    gemini = next(row for row in contract["surfaces"] if row["surface_id"] == "gemini")
    gemini["discovery"]["parser_id"] = "permissive-parser"
    before_commands = list(native_gemini.commands)
    with pytest.raises(LifecycleError, match="contract is not exact v1"):
        lifecycle._native_adapter(contract, ["gemini"])
    assert native_gemini.commands == before_commands


def _exact_local_gemini() -> str:
    executable = shutil.which("gemini")
    if executable is None:
        pytest.skip("exact pinned Gemini binary is not installed")
    result = subprocess.run(
        [executable, "--version"],
        capture_output=True,
        check=False,
        timeout=10,
    )
    if result.returncode != 0 or result.stderr or result.stdout.strip() != b"0.45.0":
        pytest.skip("local Gemini binary is not exact pinned 0.45.0")
    return executable


def test_exact_pinned_gemini_runs_real_native_lifecycle(tmp_path: Path) -> None:
    _exact_local_gemini()
    request = _bundle(tmp_path, "gemini-live", gemini_only=True)
    project = tmp_path / "project"
    host = project / ".gemini/skills/host-skill/SKILL.md"
    host.parent.mkdir(parents=True)
    host.write_text(
        "---\nname: host-skill\ndescription: Host-owned native skill.\n---\nHost.\n"
    )

    assert install(project, request)["mode"] == "router-only"
    assert verify(project)["surface_set"] == ["gemini"]
    assert activate(project, "plan-feature")["activation_records"] == [
        {"public_name": "plan-feature", "canonical_target": "plan-feature"}
    ]
    assert set_mode(project, "full-discovery")["mode"] == "full-discovery"
    assert set_mode(project, "router-only")["mode"] == "router-only"
    assert deactivate(project, "plan-feature")["activation_records"] == []
    uninstall(project)

    assert host.is_file()
    assert not (project / MANIFEST_PATH).exists()


def test_install_reverifies_external_root_and_preserves_host_discovery(
    tmp_path: Path, discovery: FilesystemDiscovery
) -> None:
    request = _bundle(tmp_path, "install")
    project = tmp_path / "project"
    host = project / ".claude/skills/host-skill/SKILL.md"
    host.parent.mkdir(parents=True)
    host.write_text("host\n")

    manifest = install(project, request)

    assert manifest["surface_set"] == ["claude-code", "codex"]
    assert verify(project) == manifest
    assert host.read_text() == "host\n"
    assert discovery.discover(project, "claude-code").host_owned == {"host-skill"}
    assert _state(project)["trust"]["release_root_sha256"] == request.release_root_sha256


def test_tampered_bundle_is_rejected_before_host_mutation(
    tmp_path: Path, discovery: FilesystemDiscovery
) -> None:
    del discovery
    request = _bundle(tmp_path, "tampered")
    blob = next((request.bundle_root / "blobs").rglob("plan-feature"))
    blob.write_bytes(b"tampered")
    project = tmp_path / "project"

    with pytest.raises(BundleTrustError):
        install(project, request)

    assert not (project / MANIFEST_PATH).exists()


def test_update_revalidates_applicability_and_binding_hashes(
    tmp_path: Path, discovery: FilesystemDiscovery
) -> None:
    first = _bundle(tmp_path, "first", version="1.0.0")
    changed = _bundle(
        tmp_path,
        "changed",
        version="2.0.0",
        plan_content=b"---\nname: plan-feature\ndescription: Plan a feature.\n---\nPlan v2.\n",
    )
    missing = _bundle(tmp_path, "missing", version="3.0.0", include_plan=False)
    project = tmp_path / "project"
    install(project, first)
    activate(project, "plan-feature")
    old_selection = _state(project)["trust"]["selection_sha256"]

    updated = update(project, changed)
    assert updated["activation_records"] == [
        {"public_name": "plan-feature", "canonical_target": "plan-feature"}
    ]
    assert _state(project)["trust"]["selection_sha256"] != old_selection
    before = _files(project)
    with pytest.raises(LifecycleError, match="invalidates activation records"):
        update(project, missing)
    assert _files(project) == before


def test_failed_native_proof_restores_exact_prior_tree(
    tmp_path: Path, discovery: FilesystemDiscovery
) -> None:
    first = _bundle(tmp_path, "first", version="1.0.0")
    second = _bundle(tmp_path, "second", version="2.0.0")
    project = tmp_path / "project"
    install(project, first)
    before = _files(project)
    discovery.fail = True

    with pytest.raises(LifecycleError, match="native discovery mismatch"):
        update(project, second)

    discovery.fail = False
    assert _files(project) == before
    assert verify(project)["bundle_version"] == "1.0.0"


def test_marker_only_orphan_never_authorizes_recursive_deletion(
    tmp_path: Path, discovery: FilesystemDiscovery
) -> None:
    request = _bundle(tmp_path, "orphan-attack")
    project = tmp_path / "project"
    orphan = project / f"{TRANSACTION_PREFIX}{uuid.uuid4()}"
    orphan.mkdir(parents=True)
    (orphan / "owner-v1").write_bytes(b"engineering-skills\n")
    host = orphan / "HOST.txt"
    host.write_bytes(b"host-owned\n")

    with pytest.raises(LifecycleError, match="manual quarantine"):
        install(project, request)

    assert host.read_bytes() == b"host-owned\n"
    assert orphan.is_dir()
    assert not (project / MANIFEST_PATH).exists()


def test_bound_startup_journal_restores_legitimate_interrupted_transaction(
    tmp_path: Path, discovery: FilesystemDiscovery
) -> None:
    request = _bundle(tmp_path, "legitimate-recovery")
    project = tmp_path / "project"
    manifest = install(project, request)
    target_relative = ".claude/skills/which-shape/SKILL.md"
    target = project / target_relative
    target_bytes = target.read_bytes()
    clean_journal = (project / JOURNAL_PATH).read_bytes()
    transaction_id = str(uuid.uuid4())
    transaction_relative = f"{TRANSACTION_PREFIX}{transaction_id}"
    transaction = project / transaction_relative
    (transaction / "backup" / Path(MANIFEST_PATH).parent).mkdir(parents=True)
    (transaction / "owner-v1").write_bytes(b"engineering-skills\n")
    shutil.copy2(project / MANIFEST_PATH, transaction / "backup" / MANIFEST_PATH)
    shutil.copy2(project / STATE_PATH, transaction / "backup" / STATE_PATH)
    for relative, content in (
        (target_relative, target_bytes),
        (JOURNAL_PATH, clean_journal),
    ):
        backup = transaction / "backup" / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(content)
    changes = [
        {
            "path": relative,
            "existed": True,
            "kind": "file",
            "size": len(content),
            "sha256": _sha(content),
            "link_target": None,
        }
        for relative, content in sorted(
            ((target_relative, target_bytes), (JOURNAL_PATH, clean_journal))
        )
    ]
    journal = {
        "schema_version": 1,
        "state": "committing",
        "operation": "update",
        "transaction_id": transaction_id,
        "prior_manifest_sha256": manifest["manifest_sha256"],
        "desired_manifest_sha256": None,
        "transaction_path": transaction_relative,
        "changes": changes,
    }
    target.unlink()
    (project / JOURNAL_PATH).write_bytes(canonical_json_bytes(journal))

    assert verify(project)["manifest_sha256"] == manifest["manifest_sha256"]
    assert target.read_bytes() == target_bytes
    assert (project / JOURNAL_PATH).read_bytes() == clean_journal
    assert not transaction.exists()


def test_forged_canonical_journal_cannot_delete_host_file(
    tmp_path: Path, discovery: FilesystemDiscovery
) -> None:
    request = _bundle(tmp_path, "forged")
    project = tmp_path / "project"
    install(project, request)
    host = project / "HOST.txt"
    host.write_bytes(b"host")
    manifest = json.loads((project / MANIFEST_PATH).read_bytes())
    transaction_id = str(uuid.uuid4())
    transaction = project / f"{TRANSACTION_PREFIX}{transaction_id}"
    (transaction / "backup" / Path(MANIFEST_PATH).parent).mkdir(parents=True)
    (transaction / "owner-v1").write_bytes(b"engineering-skills\n")
    shutil.copy2(project / MANIFEST_PATH, transaction / "backup" / MANIFEST_PATH)
    shutil.copy2(project / STATE_PATH, transaction / "backup" / STATE_PATH)
    journal = {
        "schema_version": 1,
        "state": "committing",
        "operation": "update",
        "transaction_id": transaction_id,
        "prior_manifest_sha256": manifest["manifest_sha256"],
        "desired_manifest_sha256": None,
        "transaction_path": f"{TRANSACTION_PREFIX}{transaction_id}",
        "changes": [
            {
                "path": "HOST.txt",
                "existed": True,
                "kind": "file",
                "size": 4,
                "sha256": _sha(b"host"),
                "link_target": None,
            }
        ],
    }
    (project / JOURNAL_PATH).write_bytes(canonical_json_bytes(journal))

    with pytest.raises(LifecycleError, match="startup recovery failed closed"):
        verify(project)

    assert host.read_bytes() == b"host"


def test_repeated_rollback_is_idempotent(tmp_path: Path, discovery: FilesystemDiscovery) -> None:
    first = _bundle(tmp_path, "first", version="1.0.0")
    second = _bundle(tmp_path, "second", version="2.0.0")
    project = tmp_path / "project"
    install(project, first)
    update(project, second)

    once = rollback(project)
    once_files = _files(project)
    twice = rollback(project)

    assert twice["manifest_sha256"] == once["manifest_sha256"]
    assert _files(project) == once_files
    assert _state(project)["rollback_applied_from"] is not None


def test_uninstall_prunes_only_recorded_toolkit_directories(
    tmp_path: Path, discovery: FilesystemDiscovery
) -> None:
    request = _bundle(tmp_path, "uninstall")
    project = tmp_path / "project"
    host_empty = project / "host-empty"
    host_empty.mkdir(parents=True)
    install(project, request)

    uninstall(project)

    assert host_empty.is_dir()
    assert not (project / MANIFEST_PATH).exists()
    assert not (project / ".claude/skills/which-shape").exists()


def test_exact_legacy_preview_requires_opt_in_and_retires_only_known_rows(
    tmp_path: Path, discovery: FilesystemDiscovery
) -> None:
    legacy = {
        ".legacy/content": (b"content\n", "content"),
        ".legacy/owner-v1": (b"owner\n", "ownership-marker"),
    }
    request = _bundle(tmp_path, "legacy", legacy_files=legacy)
    project = tmp_path / "project"
    for path, (content, _role) in legacy.items():
        target = project / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    (project / ".legacy/HOST.txt").write_text("host\n")

    preview = preview_migration(project, request)
    assert preview["available"] is True
    assert {row["path"] for row in preview["entries"]} == set(legacy)
    with pytest.raises(LifecycleError, match="explicit apply_migration"):
        install(project, request)
    install(project, request, apply_migration=True)

    assert not any((project / path).exists() for path in legacy)
    assert (project / ".legacy/HOST.txt").read_text() == "host\n"


def test_modified_known_legacy_marker_stops_without_inference(
    tmp_path: Path, discovery: FilesystemDiscovery
) -> None:
    del discovery
    legacy = {".legacy/owner-v1": (b"owner\n", "ownership-marker")}
    request = _bundle(tmp_path, "legacy-modified", legacy_files=legacy)
    project = tmp_path / "project"
    marker = project / ".legacy/owner-v1"
    marker.parent.mkdir(parents=True)
    marker.write_bytes(b"modified\n")

    with pytest.raises(LifecycleError, match="ownership marker is modified"):
        preview_migration(project, request)


def test_empty_production_legacy_authority_reports_no_known_layout(tmp_path: Path) -> None:
    request = _bundle(tmp_path, "no-legacy")
    project = tmp_path / "project"
    project.mkdir()

    preview = preview_migration(project, request)

    assert preview["available"] is False
    assert preview["reason"] == "no_known_layout"
    assert preview["entries"] == []


def test_lifecycle_is_offline_and_denies_network(
    tmp_path: Path, discovery: FilesystemDiscovery, monkeypatch: pytest.MonkeyPatch
) -> None:
    del discovery
    request = _bundle(tmp_path, "offline")
    project = tmp_path / "project"

    def denied(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "socket", denied)
    install(project, request)
    assert verify(project)["release_root_sha256"] == request.release_root_sha256


def test_request_rejects_self_attested_or_duplicate_recipe_input(tmp_path: Path) -> None:
    with pytest.raises(LifecycleError, match="SHA-256"):
        BundleInstallRequest(tmp_path, "not-a-digest", ("claude-bootstrap",))
    with pytest.raises(LifecycleError, match="unique"):
        BundleInstallRequest(tmp_path, "0" * 64, ("claude-bootstrap", "claude-bootstrap"))


def test_cli_exposes_no_dynamic_adapter_factory(tmp_path: Path) -> None:
    cli = runpy.run_path(str(SCRIPTS / "skill_installer.py"))
    with pytest.raises(SystemExit):
        cli["main"](
            [
                "--project-root",
                str(tmp_path),
                "--adapter",
                "attacker.module:factory",
                "verify",
            ]
        )
    assert "importlib" not in (SCRIPTS / "skill_installer.py").read_text()
