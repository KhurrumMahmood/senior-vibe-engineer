from __future__ import annotations

import manifest
import pytest
from installer_selection import select_install
from sweep_shims import resolve_shims


def test_installer_selection_uses_registry_bindings_without_stack_enums():
    selection = select_install(
        {
            "languages": ["typescript"],
            "frameworks": ["react"],
            "tools": ["vite", "vitest"],
        }
    )

    assert selection["layers"] == ["core", "framework", "language"]
    assert selection["bindings"] == ["core", "javascript-typescript", "react"]


def test_sweep_shims_resolve_native_and_parser_providers_from_registry():
    shims = resolve_shims(["typescript", "rust", "go", "css"])

    assert shims["typescript"]["provider"] == "typescript-syntax"
    assert shims["rust"]["status"] == "unsupported"
    assert shims["rust"]["provider_kind"] == "native-shim"
    assert shims["rust"]["provider"] == "cargo"
    assert shims["go"]["provider"] == "go-toolchain"
    assert shims["css"] == {"status": "unsupported"}


def test_installer_selection_fails_on_ambiguous_mixed_root():
    with pytest.raises(ValueError, match="ambiguous binding selection"):
        select_install(
            {
                "languages": ["python", "typescript"],
                "frameworks": ["django", "react"],
                "tools": [],
            }
        )


def test_activation_manifest_validates_capability_selection(tmp_path):
    engineering = tmp_path / ".engineering"
    engineering.mkdir()
    engineering.joinpath("manifest.json").write_text(
        """{
  "version": 1,
  "capability_registry_version": 1,
  "capability_contract_version": 1,
  "capability_selection": {
    "languages": ["typescript"],
    "frameworks": ["vite"],
    "tools": [],
    "layers": ["framework"],
    "bindings": ["react"]
  }
}
""",
        encoding="utf-8",
    )

    errors = manifest.validate_manifest(tmp_path)

    assert errors == [
        "manifest.capability_selection.frameworks contains unregistered identifiers: ['vite']"
    ]
