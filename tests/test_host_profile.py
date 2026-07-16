"""Canonical deterministic host-profile contract for WP2."""
from __future__ import annotations

import json
from pathlib import Path

from _lib.host_profile import profile_host, validate_host_profile


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_django(root: Path) -> None:
    _write(root / "manage.py", "#!/usr/bin/env python3\n")
    _write(root / "requirements.txt", "Django==5.2\npytest==9.0.3\nruff==0.6.9\n")
    _write(root / "app" / "models.py", "class Item: pass\n")


def _seed_typescript(root: Path) -> None:
    _write(
        root / "package.json",
        json.dumps(
            {
                "scripts": {"test": "vitest --run", "lint": "eslint .", "build": "tsc"},
                "dependencies": {"react": "19.0.0", "vite": "7.0.0"},
                "devDependencies": {"typescript": "5.9.3", "vitest": "3.0.0"},
            }
        ),
    )
    _write(root / "pnpm-lock.yaml", "lockfileVersion: '9.0'\n")
    _write(root / "tsconfig.json", "{}\n")
    _write(root / "src" / "App.tsx", "export const App = () => null;\n")


def _seed_rust(root: Path) -> None:
    _write(root / "Cargo.toml", "[package]\nname='sample'\nversion='0.1.0'\n")
    _write(root / "src" / "lib.rs", "pub fn run() {}\n")


def _seed_go(root: Path) -> None:
    _write(root / "go.mod", "module example.test/sample\n\ngo 1.24\n")
    _write(root / "main.go", "package main\nfunc main() {}\n")


def _assert_evidenced(profile: dict) -> None:
    for root in profile["roots"]:
        asserted = {
            (category, identifier)
            for category in ("languages", "frameworks", "tools")
            for identifier in root[category]
        }
        evidenced = {
            (item["category"], item["identifier"])
            for item in root["evidence"]
        }
        assert asserted <= evidenced


# spec:portable-host-profile-routing::IM-2
def test_five_host_shapes_are_schema_valid_deterministic_and_evidenced(tmp_path):
    seeders = {
        "django": _seed_django,
        "typescript": _seed_typescript,
        "rust": _seed_rust,
        "go": _seed_go,
    }
    for name, seed in seeders.items():
        root = tmp_path / name
        seed(root)
        first = profile_host(root)
        second = profile_host(root)
        assert first == second
        assert validate_host_profile(first) == []
        assert "generated_at" not in first
        assert str(root) not in json.dumps(first)
        assert first["roots"]
        assert all(entry["commands"]["test"] for entry in first["roots"])
        assert all(item["reason"] for item in first["exclusions"])
        _assert_evidenced(first)


def test_mixed_monorepo_composes_independent_sorted_roots(tmp_path):
    _seed_django(tmp_path / "backend")
    _seed_typescript(tmp_path / "web")
    _seed_rust(tmp_path / "native")
    _seed_go(tmp_path / "worker")

    profile = profile_host(tmp_path)

    assert validate_host_profile(profile) == []
    roots = {entry["path"]: entry for entry in profile["roots"]}
    assert list(roots) == ["backend", "native", "web", "worker"]
    assert roots["backend"]["frameworks"] == ["django"]
    assert "typescript" in roots["web"]["languages"]
    assert roots["native"]["languages"] == ["rust"]
    assert roots["worker"]["languages"] == ["go"]
    assert profile["stack"]["languages"] == ["go", "javascript", "python", "rust", "typescript"]
    _assert_evidenced(profile)


def test_rust_and_go_profiles_have_native_commands(tmp_path):
    _seed_rust(tmp_path / "rust")
    _seed_go(tmp_path / "go")

    roots = {entry["path"]: entry for entry in profile_host(tmp_path)["roots"]}

    assert roots["rust"]["commands"] == {
        "build": ["cargo build"],
        "dev": [],
        "lint": ["cargo clippy --all-targets --all-features -- -D warnings"],
        "setup": [],
        "test": ["cargo test"],
    }
    assert roots["go"]["commands"] == {
        "build": ["go build ./..."],
        "dev": [],
        "lint": ["go vet ./..."],
        "setup": [],
        "test": ["go test ./..."],
    }


def test_validator_rejects_unregistered_and_unevidenced_assertions(tmp_path):
    _seed_django(tmp_path)
    profile = profile_host(tmp_path)
    profile["roots"][0]["languages"].append("bogus")
    profile["roots"][0]["frameworks"].append("react")

    errors = validate_host_profile(profile)

    assert any("unregistered" in error and "bogus" in error for error in errors)
    assert any("no evidence" in error and "react" in error for error in errors)


def test_profile_component_and_surface_defaults_are_neutral(tmp_path):
    _seed_typescript(tmp_path)

    profile = profile_host(tmp_path)

    assert profile["component_profile"] == {
        "definitions_root": "",
        "extensions": [],
        "kind": "none",
        "reference_pattern": "",
    }
    assert profile["surface_labels"] == {}
