from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from _lib.distribution_contracts import canonical_json_bytes, canonical_sha256
from _lib.skill_bundle import (
    BUNDLE_INDEX_NAME,
    INSTALLED_MANIFEST_PATH,
    RELEASE_ROOT_NAME,
    BlobSource,
    BundleTrustError,
    build_release_bundle,
    materialize_install_image,
    recipe_from_json,
    validate_relative_path,
    verify_install_image,
    verify_release_bundle,
)


ROOT = Path(__file__).resolve().parents[1]


def _surface_contract() -> dict[str, Any]:
    versions = {
        "claude-code": "2.1.211",
        "codex": "0.144.1",
        "augment": "imported-rules-v1",
        "cursor": "project-rules-v1",
        "gemini": "0.45.0",
    }
    public = {
        "claude-code": ("/which-shape", "/which-skill", "/{public-name}"),
        "codex": (
            "$engineering-skills:which-shape",
            "$engineering-skills:which-skill",
            "$engineering-skills:{public-name}",
        ),
        "augment": (
            "use skill which-shape",
            "use skill which-skill",
            "use skill {public-name}",
        ),
        "cursor": (
            "use skill which-shape",
            "use skill which-skill",
            "use skill {public-name}",
        ),
        "gemini": (
            "use skill which-shape",
            "use skill which-skill",
            "use skill {public-name}",
        ),
    }
    generated = {
        "claude-code": (
            ".claude/skills/which-shape/SKILL.md",
            ".claude/skills/which-skill/SKILL.md",
            ".claude/skills/{public-name}/SKILL.md",
        ),
        "codex": (
            "skills/which-shape/SKILL.md",
            "skills/which-skill/SKILL.md",
            "skills/{public-name}/SKILL.md",
        ),
        "augment": (
            ".augment/rules/imported/which-shape/SKILL.md",
            ".augment/rules/imported/which-skill/SKILL.md",
            ".augment/rules/imported/{public-name}/SKILL.md",
        ),
        "cursor": (
            ".cursor/rules/which-shape/SKILL.mdc",
            ".cursor/rules/which-skill/SKILL.mdc",
            ".cursor/rules/{public-name}/SKILL.mdc",
        ),
        "gemini": (
            ".gemini/skills/which-shape/SKILL.md",
            ".gemini/skills/which-skill/SKILL.md",
            ".gemini/skills/{public-name}/SKILL.md",
        ),
    }
    surfaces = []
    for surface_id, version in versions.items():
        public_shape, public_skill, public_alias = public[surface_id]
        generated_shape, generated_skill, generated_alias = generated[surface_id]
        surfaces.append(
            {
                "surface_id": surface_id,
                "runtime_version": {"lower": version, "upper": version},
                "projection_format": f"{surface_id}-projection-v1",
                "public_identity": {
                    "which_shape": public_shape,
                    "which_skill": public_skill,
                    "alias_template": public_alias,
                },
                "generated_identity": {
                    "which_shape": generated_shape,
                    "which_skill": generated_skill,
                    "alias_template": generated_alias,
                },
                "discovery": {
                    "command": [surface_id, "list"],
                    "parser_id": f"{surface_id}-list-v1",
                    "offline_non_model": True,
                },
                "activation": {
                    "operation": f"{surface_id}-activation-v1",
                    "temporary_activation": "unsupported",
                    "terminal_wrapper": None,
                    "startup_cleanup": None,
                },
                "worker": {
                    "fresh_worker": "unsupported",
                    "launcher": None,
                    "version_range": None,
                    "selected_procedure_injection": None,
                    "cancellation": None,
                    "result": None,
                    "zero_conversation_turns_proof": None,
                    "budget_enforcement": None,
                },
            }
        )
    return {"schema_version": 1, "contract_version": 1, "surfaces": surfaces}


def _prepare_source(root: Path) -> list[BlobSource]:
    files = {
        "catalog.json": b'{"schema_version":1,"skills":[]}',
        "registry.json": b'{"contract_version":1,"schema_version":1}',
        "profile.json": b'{"schema_version":1}',
        "which-shape.md": b"---\nname: which-shape\n---\nComplete shape router.\n",
        "which-skill.md": b"---\nname: which-skill\n---\nComplete skill router.\n",
        "runtime.py": b"def verify_locator():\n    return True\n",
        "installer.py": b"raise SystemExit('fixture installer')\n",
    }
    for path, content in files.items():
        (root / path).write_bytes(content)
    (root / "surface-contract.json").write_bytes(
        canonical_json_bytes(_surface_contract())
    )
    recipe = {
        "schema_version": 1,
        "surface_id": "claude-code",
        "manifest_locator": INSTALLED_MANIFEST_PATH,
        "bootstrap_metadata_path": ".engineering/bootstrap/claude-code/bootstrap-v1.json",
        "routers": [
            {
                "canonical_name": "which-shape",
                "blob_id": "which-shape",
                "path": ".claude/skills/which-shape/SKILL.md",
            },
            {
                "canonical_name": "which-skill",
                "blob_id": "which-skill",
                "path": ".claude/skills/which-skill/SKILL.md",
            },
        ],
        "runtime_files": [
            {
                "blob_id": "router-runtime",
                "path": ".engineering/bootstrap/claude-code/runtime.py",
            }
        ],
    }
    (root / "recipe.json").write_bytes(canonical_json_bytes(recipe))
    codex_recipe = {
        **recipe,
        "surface_id": "codex",
        "bootstrap_metadata_path": ".engineering/bootstrap/codex/bootstrap-v1.json",
        "routers": [
            {**recipe["routers"][0], "path": "skills/which-shape/SKILL.md"},
            {**recipe["routers"][1], "path": "skills/which-skill/SKILL.md"},
        ],
        "runtime_files": [
            {
                "blob_id": "router-runtime",
                "path": ".engineering/bootstrap/codex/runtime.py",
            }
        ],
    }
    (root / "codex-recipe.json").write_bytes(canonical_json_bytes(codex_recipe))
    return [
        BlobSource("catalog", "catalog", "catalog.json", "application/json"),
        BlobSource("registry", "registry", "registry.json", "application/json"),
        BlobSource("profile", "required-profile", "profile.json", "application/json"),
        BlobSource("router", "which-shape", "which-shape.md", "text/markdown"),
        BlobSource("router", "which-skill", "which-skill.md", "text/markdown"),
        BlobSource("asset", "router-runtime", "runtime.py", "text/x-python"),
        BlobSource(
            "projection-recipe",
            "claude-bootstrap",
            "recipe.json",
            "application/json",
        ),
        BlobSource(
            "projection-recipe",
            "codex-bootstrap",
            "codex-recipe.json",
            "application/json",
        ),
    ]


def _build(tmp_path: Path, name: str = "bundle") -> tuple[Path, str]:
    source = tmp_path / f"{name}-source"
    source.mkdir()
    blobs = _prepare_source(source)
    output = tmp_path / name
    digest = build_release_bundle(
        source,
        output,
        bundle_version="1.0.0",
        blobs=blobs,
        installer="installer.py",
        surface_activation_contract="surface-contract.json",
    )
    return output, digest


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _reroot_release(bundle: Path) -> str:
    release_path = bundle / RELEASE_ROOT_NAME
    release = json.loads(release_path.read_bytes())
    bundle_bytes = (bundle / BUNDLE_INDEX_NAME).read_bytes()
    release["bundle_index"] = {
        "path": BUNDLE_INDEX_NAME,
        "size": len(bundle_bytes),
        "sha256": hashlib.sha256(bundle_bytes).hexdigest(),
    }
    release_bytes = canonical_json_bytes(release)
    release_path.write_bytes(release_bytes)
    return hashlib.sha256(release_bytes).hexdigest()


# spec:portable-skill-layer-distribution::IM-14
def test_release_to_installed_image_is_acyclic_complete_and_deterministic(
    tmp_path: Path,
) -> None:
    bundle_a, digest_a = _build(tmp_path, "bundle-a")
    bundle_b, digest_b = _build(tmp_path, "bundle-b")

    assert digest_a == digest_b
    assert _tree_bytes(bundle_a) == _tree_bytes(bundle_b)
    verified = verify_release_bundle(bundle_a, digest_a)
    image_a = tmp_path / "image-a"
    image_b = tmp_path / "image-b"
    manifest_a = materialize_install_image(
        verified, image_a, recipe_id="claude-bootstrap"
    )
    manifest_b = materialize_install_image(
        verify_release_bundle(bundle_b, digest_b),
        image_b,
        recipe_id="claude-bootstrap",
    )

    assert manifest_a == manifest_b
    assert _tree_bytes(image_a) == _tree_bytes(image_b)
    assert manifest_a["mode"] == "router-only"
    assert manifest_a["activation_records"] == []
    assert manifest_a["manifest_sha256"] == canonical_sha256(
        {
            key: value
            for key, value in manifest_a.items()
            if key != "manifest_sha256"
        }
    )
    bootstrap_paths = {
        row["path"] for row in manifest_a["owned_paths"]["bootstrap_projections"]
    }
    assert bootstrap_paths == {
        ".claude/skills/which-shape/SKILL.md",
        ".claude/skills/which-skill/SKILL.md",
        ".engineering/bootstrap/claude-code/bootstrap-v1.json",
        ".engineering/bootstrap/claude-code/runtime.py",
    }
    metadata = json.loads(
        image_a.joinpath(
            ".engineering/bootstrap/claude-code/bootstrap-v1.json"
        ).read_bytes()
    )
    assert metadata["schema_version"] == 1
    assert metadata["manifest_locator"] == INSTALLED_MANIFEST_PATH
    assert metadata["release_root_sha256"] == digest_a
    assert metadata["bundle_index_sha256"] == verified.bundle_index_sha256
    assert [row["canonical_name"] for row in metadata["routers"]] == [
        "which-shape",
        "which-skill",
    ]
    assert manifest_a["manifest_sha256"].encode() not in b"".join(
        image_a.joinpath(path).read_bytes() for path in bootstrap_paths
    )
    assert all(
        row["path"].startswith(
            f".engineering/catalog/{verified.bundle_index_sha256}/blobs/sha256/"
        )
        for row in manifest_a["owned_paths"]["catalog_store"]
    )
    verify_install_image(verified, image_a, recipe_id="claude-bootstrap")


def test_one_self_hashed_manifest_binds_complete_multi_surface_set(
    tmp_path: Path,
) -> None:
    bundle, digest = _build(tmp_path)
    verified = verify_release_bundle(bundle, digest)
    image = tmp_path / "multi-surface-image"
    manifest = materialize_install_image(
        verified,
        image,
        recipe_ids=["claude-bootstrap", "codex-bootstrap"],
    )

    assert manifest["surface_set"] == ["claude-code", "codex"]
    assert [row["surface_id"] for row in manifest["bootstrap_trees"]] == [
        "claude-code",
        "codex",
    ]
    assert {row["surface_id"] for row in manifest["generated_files"]} == {
        "claude-code",
        "codex",
    }
    assert manifest["manifest_sha256"] == canonical_sha256(
        {
            key: value
            for key, value in manifest.items()
            if key != "manifest_sha256"
        }
    )
    verify_install_image(
        verified,
        image,
        recipe_ids=["claude-bootstrap", "codex-bootstrap"],
    )
    with pytest.raises(BundleTrustError, match="surface set differs"):
        verify_install_image(verified, image, recipe_id="claude-bootstrap")


def test_external_root_raw_blob_and_noncanonical_release_tampering_fail(
    tmp_path: Path,
) -> None:
    bundle, digest = _build(tmp_path)
    with pytest.raises(BundleTrustError, match="out-of-band"):
        verify_release_bundle(bundle, "0" * 64)

    verified = verify_release_bundle(bundle, digest)
    blob = next(iter(verified.bundle_index["blobs"]))
    (bundle / blob["path"]).write_bytes(b"tampered")
    with pytest.raises(BundleTrustError, match="raw size or SHA-256"):
        verify_release_bundle(bundle, digest)

    bundle, _ = _build(tmp_path, "noncanonical")
    release_path = bundle / RELEASE_ROOT_NAME
    release_path.write_bytes(json.dumps(json.loads(release_path.read_bytes()), indent=2).encode())
    attacked_digest = hashlib.sha256(release_path.read_bytes()).hexdigest()
    with pytest.raises(BundleTrustError, match="canonical JCS"):
        verify_release_bundle(bundle, attacked_digest)


@pytest.mark.parametrize("attacked_path", ("../escape", "blobs/sha256/" + "a" * 64 + "/installed-manifest-v1.json"))
def test_bundle_rejects_traversal_and_backward_manifest_edges(
    tmp_path: Path, attacked_path: str
) -> None:
    bundle, digest = _build(tmp_path)
    verified = verify_release_bundle(bundle, digest)
    index_path = bundle / BUNDLE_INDEX_NAME
    index = copy.deepcopy(verified.bundle_index)
    row = index["blobs"][0]
    source = bundle / row["path"]
    if not attacked_path.startswith(".."):
        target = bundle / attacked_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        row["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        row["size"] = len(target.read_bytes())
    row["path"] = attacked_path
    tree = [
        {key: item[key] for key in ("path", "size", "sha256")}
        for item in index["blobs"]
    ]
    index["tree_sha256"] = canonical_sha256(
        sorted(tree, key=lambda item: item["path"].encode())
    )
    index_path.write_bytes(canonical_json_bytes(index))
    attacked_digest = _reroot_release(bundle)

    with pytest.raises(
        BundleTrustError,
        match="does not match pattern|backward or self edge",
    ):
        verify_release_bundle(bundle, attacked_digest)


def test_bundle_and_installed_verifiers_reject_symlinks(tmp_path: Path) -> None:
    bundle, digest = _build(tmp_path)
    verified = verify_release_bundle(bundle, digest)
    row = verified.bundle_index["blobs"][0]
    path = bundle / row["path"]
    original = path.read_bytes()
    path.unlink()
    outside = tmp_path / "outside"
    outside.write_bytes(original)
    path.symlink_to(outside)

    with pytest.raises(BundleTrustError, match="symlink"):
        verify_release_bundle(bundle, digest)

    bundle, digest = _build(tmp_path, "image-symlink")
    verified = verify_release_bundle(bundle, digest)
    image = tmp_path / "image"
    manifest = materialize_install_image(
        verified, image, recipe_id="claude-bootstrap"
    )
    bootstrap = image / manifest["owned_paths"]["bootstrap_projections"][0]["path"]
    content = bootstrap.read_bytes()
    bootstrap.unlink()
    outside = tmp_path / "outside-bootstrap"
    outside.write_bytes(content)
    bootstrap.symlink_to(outside)
    with pytest.raises(BundleTrustError, match="symlink"):
        verify_install_image(verified, image, recipe_id="claude-bootstrap")

    bundle, digest = _build(tmp_path, "root-symlink")
    root_link = tmp_path / "bundle-link"
    root_link.symlink_to(bundle, target_is_directory=True)
    with pytest.raises(BundleTrustError, match="root must not be a symlink"):
        verify_release_bundle(root_link, digest)


@pytest.mark.parametrize(
    "path",
    (
        "a//b",
        "a/",
        "/a",
        "a/../b",
        "a/./b",
        ".engineering/bootstrap/claude-code/./runtime.py",
        "cafe\u0301",
    ),
)
def test_relative_path_rejects_normalizing_or_escaping_forms(path: str) -> None:
    with pytest.raises(BundleTrustError):
        validate_relative_path(path)


def test_recovery_tamper_and_undeclared_image_file_fail(tmp_path: Path) -> None:
    bundle, digest = _build(tmp_path)
    verified = verify_release_bundle(bundle, digest)
    image = tmp_path / "image"
    manifest = materialize_install_image(
        verified, image, recipe_id="claude-bootstrap"
    )
    recovery_path = image / manifest["recovery"]["journal_path"]
    attacked_recovery = canonical_json_bytes(
        {"schema_version": 1, "state": "clean", "temporary_records": [], "note": "forged"}
    )
    recovery_path.write_bytes(attacked_recovery)
    recovery_row = manifest["owned_paths"]["recovery_journal"][0]
    recovery_row.update(
        {
            "size": len(attacked_recovery),
            "sha256": hashlib.sha256(attacked_recovery).hexdigest(),
        }
    )
    manifest["recovery"]["journal_sha256"] = recovery_row["sha256"]
    manifest["manifest_sha256"] = canonical_sha256(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    )
    image.joinpath(INSTALLED_MANIFEST_PATH).write_bytes(canonical_json_bytes(manifest))
    with pytest.raises(BundleTrustError, match="recovery journal bytes differ"):
        verify_install_image(verified, image, recipe_id="claude-bootstrap")

    image = tmp_path / "extra-image"
    materialize_install_image(verified, image, recipe_id="claude-bootstrap")
    (image / "undeclared.txt").write_text("hostile extra", encoding="utf-8")
    with pytest.raises(BundleTrustError, match="exact manifest-owned set"):
        verify_install_image(verified, image, recipe_id="claude-bootstrap")


def test_cli_recipe_rejects_duplicate_keys_and_noncanonical_bytes(tmp_path: Path) -> None:
    recipe = tmp_path / "release-recipe.json"
    recipe.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    with pytest.raises(BundleTrustError, match="duplicate JSON key"):
        recipe_from_json(recipe)

    recipe.write_text('{"blobs": [], "schema_version": 1}\n', encoding="utf-8")
    with pytest.raises(BundleTrustError, match="canonical JCS"):
        recipe_from_json(recipe)


def test_projection_runtime_cannot_add_a_third_ambient_header(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    blobs = _prepare_source(source)
    recipe = json.loads((source / "recipe.json").read_bytes())
    recipe["runtime_files"][0]["path"] = ".claude/skills/third/SKILL.md"
    (source / "recipe.json").write_bytes(canonical_json_bytes(recipe))

    with pytest.raises(BundleTrustError, match="ambient skill header"):
        build_release_bundle(
            source,
            tmp_path / "bundle",
            bundle_version="1.0.0",
            blobs=blobs,
            installer="installer.py",
            surface_activation_contract="surface-contract.json",
        )


def test_release_build_rejects_explicit_dot_segment_in_projection_path(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    blobs = _prepare_source(source)
    recipe = json.loads((source / "recipe.json").read_bytes())
    recipe["runtime_files"][0]["path"] = (
        ".engineering/bootstrap/claude-code/./runtime.py"
    )
    (source / "recipe.json").write_bytes(canonical_json_bytes(recipe))

    with pytest.raises(BundleTrustError, match="dot segment"):
        build_release_bundle(
            source,
            tmp_path / "bundle",
            bundle_version="1.0.0",
            blobs=blobs,
            installer="installer.py",
            surface_activation_contract="surface-contract.json",
        )


def test_reference_table_tamper_fails_after_attacker_reroots_release(
    tmp_path: Path,
) -> None:
    bundle, _ = _build(tmp_path)
    alias_path = bundle / "tables/aliases-v1.json"
    alias_path.write_bytes(alias_path.read_bytes() + b"\n")
    release = json.loads((bundle / RELEASE_ROOT_NAME).read_bytes())
    row = next(item for item in release["tables"] if item["table_id"] == "aliases-v1")
    row.update(
        {
            "size": alias_path.stat().st_size,
            "sha256": hashlib.sha256(alias_path.read_bytes()).hexdigest(),
        }
    )
    release_bytes = canonical_json_bytes(release)
    (bundle / RELEASE_ROOT_NAME).write_bytes(release_bytes)

    with pytest.raises(BundleTrustError, match="not RFC-8785 canonical"):
        verify_release_bundle(bundle, hashlib.sha256(release_bytes).hexdigest())


def test_cli_verifies_exact_release_and_image_without_network(tmp_path: Path) -> None:
    bundle, digest = _build(tmp_path)
    image = tmp_path / "cli-image"
    command = [str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/skill_bundle.py")]
    environment = {**os.environ, "http_proxy": "http://127.0.0.1:1", "https_proxy": "http://127.0.0.1:1"}
    result = subprocess.run(
        [
            *command,
            "build-image",
            str(bundle),
            digest,
            str(image),
            "--recipe-id",
            "claude-bootstrap",
        ],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    manifest_digest = json.loads(result.stdout)["manifest_sha256"]
    verify = subprocess.run(
        [
            *command,
            "verify-image",
            str(bundle),
            digest,
            str(image),
            "--recipe-id",
            "claude-bootstrap",
        ],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(verify.stdout) == {"manifest_sha256": manifest_digest}
