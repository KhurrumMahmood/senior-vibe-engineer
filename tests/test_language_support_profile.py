"""Strict, isolated contract tests for versioned language profiles."""
from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts._lib.language_support.profile import ProfileError, load_profiles


ROOT = Path(__file__).resolve().parents[1]
PROFILE_ROOT = ROOT / "scripts" / "language_profiles"
LOADER = ROOT / "scripts" / "_lib" / "language_support" / "profile.py"


def _profile(language: str = "typescript", suffix: str = ".ts") -> dict:
    return {
        "schema_version": 1,
        "language": language,
        "suffixes": [suffix],
        "project_markers": ["package.json"],
        "source_roles": {
            "supported": [
                "source", "test", "generated", "vendor", "build", "declaration",
                "configuration", "tooling", "symlink",
                "migration",
            ],
            "test_file_globs": ["*.test.ts"],
            "declaration_file_globs": ["*.d.ts"],
            "configuration_files": ["tsconfig.json"],
        },
        "native_tools": [
            {
                "id": "node",
                "project_paths": ["node_modules/.bin/node"],
                "system_commands": ["node"],
                "version_argv": ["{tool}", "--version"],
                "minimum_version": "18.0.0",
                "required": True,
            }
        ],
        "fact_tiers": ["lexical-filesystem", "syntax", "semantic-project"],
        "verification_commands": [
            {
                "id": "typecheck",
                "argv": ["{tool:node}", "--check", "{project_root}/index.ts"],
                "requires": ["node"],
            }
        ],
        "terminal_outcomes": ["complete", "partial", "unsupported", "tool-missing"],
        "explicit_limits": ["No framework semantics."],
    }


def _write(root: Path, payload: dict, name: str | None = None) -> None:
    path = root / f"{name or payload['language']}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_repository_profiles_cover_current_inventory_languages() -> None:
    profiles = load_profiles(PROFILE_ROOT)

    assert set(profiles) == {
        "python", "javascript", "typescript", "go", "java", "php", "swift", "c",
        "cpp", "ruby", "rust", "dart",
    }
    suffixes = {
        suffix: language
        for language, profile in profiles.items()
        for suffix in profile.suffixes
    }
    assert suffixes == {
        ".py": "python", ".pyi": "python",
        ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
        ".cjs": "javascript", ".ts": "typescript", ".tsx": "typescript",
        ".go": "go", ".java": "java", ".php": "php", ".swift": "swift",
        ".c": "c", ".i": "c", ".cc": "cpp", ".cpp": "cpp",
        ".cxx": "cpp", ".c++": "cpp", ".ii": "cpp", ".hpp": "cpp",
        ".hh": "cpp", ".hxx": "cpp", ".h++": "cpp", ".ipp": "cpp",
        ".inl": "cpp", ".tpp": "cpp", ".rb": "ruby", ".rs": "rust",
        ".dart": "dart",
    }
    assert profiles["typescript"].native_tools[1].id == "tsc"
    assert profiles["java"].native_tools[1].minimum_version == "17.0.0"
    assert profiles["php"].native_tools[0].id == "php"
    assert profiles["php"].native_tools[1].id == "composer"
    assert [tool.id for tool in profiles["swift"].native_tools] == ["swift", "swiftc"]
    assert profiles["swift"].project_markers == ("Package.swift",)
    assert profiles["swift"].source_roles.configuration_files == ("Package.swift",)
    assert [tool.id for tool in profiles["rust"].native_tools] == [
        "rustc", "cargo", "rust-analyzer", "cargo-clippy", "rustfmt",
    ]
    assert profiles["rust"].project_markers == ("Cargo.toml", "Cargo.lock")


def test_loader_runs_under_isolated_no_site_python() -> None:
    completed = subprocess.run(
        [
            sys.executable, "-I", "-S", str(LOADER),
            "--profiles-root", str(PROFILE_ROOT), "--language", "typescript",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["language"] == "typescript"
    assert payload["schema_version"] == 1


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda row: row.update(schema_version=2), "schema_version"),
        (lambda row: row.update(extra=True), "unknown keys"),
        (lambda row: row["source_roles"]["supported"].append("fixture"), "source role"),
        (lambda row: row["terminal_outcomes"].append("clean"), "terminal outcome"),
    ],
)
def test_schema_drift_and_unknown_vocabulary_are_rejected(
    tmp_path: Path, mutation, message: str
) -> None:
    payload = _profile()
    mutation(payload)
    _write(tmp_path, payload)

    with pytest.raises(ProfileError, match=message):
        load_profiles(tmp_path)


def test_duplicate_suffixes_are_rejected_within_and_across_profiles(tmp_path: Path) -> None:
    within = _profile()
    within["suffixes"].append(".ts")
    _write(tmp_path, within)
    with pytest.raises(ProfileError, match="duplicate suffix"):
        load_profiles(tmp_path)

    (tmp_path / "typescript.json").unlink()
    _write(tmp_path, _profile())
    _write(tmp_path, _profile("javascript", ".ts"))
    with pytest.raises(ProfileError, match="claimed by both"):
        load_profiles(tmp_path)


@pytest.mark.parametrize(
    "argv",
    [
        "node --check index.ts",
        ["bash", "-c", "node --check index.ts"],
        ["{tool:node}", "--check;rm", "index.ts"],
        ["{tool:missing}", "--version"],
        ["{tool:node}", "{unknown}"],
    ],
)
def test_unsafe_verification_command_shapes_are_rejected(
    tmp_path: Path, argv: object
) -> None:
    payload = _profile()
    payload["verification_commands"][0]["argv"] = argv
    _write(tmp_path, payload)

    with pytest.raises(ProfileError, match="verification command"):
        load_profiles(tmp_path)


def test_unsafe_native_tool_command_shapes_are_rejected(tmp_path: Path) -> None:
    payload = deepcopy(_profile())
    payload["native_tools"][0]["version_argv"] = ["sh", "-c", "node --version"]
    _write(tmp_path, payload)

    with pytest.raises(ProfileError, match="native tool"):
        load_profiles(tmp_path)


def test_profile_roots_and_files_may_not_be_symlinks(tmp_path: Path) -> None:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    _write(profiles, _profile())
    linked_root = tmp_path / "linked-profiles"
    linked_root.symlink_to(profiles, target_is_directory=True)

    with pytest.raises(ProfileError, match="regular directory"):
        load_profiles(linked_root)

    profile = profiles / "typescript.json"
    profile.unlink()
    external = tmp_path / "external.json"
    external.write_text(json.dumps(_profile()), encoding="utf-8")
    profile.symlink_to(external)
    with pytest.raises(ProfileError, match="symbolic link"):
        load_profiles(profiles)
