"""Canonical deterministic host-profile contract for WP2."""
from __future__ import annotations

import copy
import hashlib
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


def _rehash(profile: dict) -> None:
    unhashed = dict(profile)
    unhashed.pop("profile_sha256", None)
    encoded = json.dumps(unhashed, sort_keys=True, separators=(",", ":")).encode()
    profile["profile_sha256"] = hashlib.sha256(encoded).hexdigest()


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


def test_validator_rejects_rehashed_malformed_nested_shapes_and_aggregates(tmp_path):
    _seed_django(tmp_path)
    valid = profile_host(tmp_path)
    mutations = {
        "unknown top field": lambda item: item.__setitem__("unexpected", True),
        "boolean schema version": lambda item: item.__setitem__("schema_version", True),
        "boolean registry version": lambda item: item.__setitem__(
            "capability_registry_version", True
        ),
        "boolean contract version": lambda item: item.__setitem__(
            "capability_contract_version", True
        ),
        "project mapping": lambda item: item.__setitem__("project", "sample"),
        "project name": lambda item: item["project"].__setitem__("name", 7),
        "root mapping": lambda item: item["roots"].__setitem__(0, "app"),
        "root path": lambda item: item["roots"][0].__setitem__("path", 7),
        "root traversal": lambda item: item["roots"][0].__setitem__("path", "../app"),
        "languages": lambda item: item["roots"][0].__setitem__("languages", "python"),
        "code roots": lambda item: item["roots"][0].__setitem__("code_roots", "app"),
        "commands mapping": lambda item: item["roots"][0].__setitem__("commands", []),
        "command list": lambda item: item["roots"][0]["commands"].__setitem__(
            "test", "pytest"
        ),
        "empty command": lambda item: item["roots"][0]["commands"].__setitem__(
            "test", [" "]
        ),
        "evidence list": lambda item: item["roots"][0].__setitem__("evidence", "marker"),
        "evidence path": lambda item: item["roots"][0]["evidence"][0].__setitem__(
            "path", 7
        ),
        "evidence identifier": lambda item: item["roots"][0]["evidence"][0].__setitem__(
            "identifier", 7
        ),
        "evidence kind": lambda item: item["roots"][0]["evidence"][0].__setitem__(
            "kind", 7
        ),
        "aggregate languages": lambda item: item["stack"].__setitem__("languages", []),
        "aggregate mapping": lambda item: item.__setitem__("stack", []),
        "project roots": lambda item: item["stack"].__setitem__("project_roots", "app"),
        "exclusion pattern": lambda item: item["exclusions"][0].__setitem__(
            "pattern", 7
        ),
        "exclusion reason": lambda item: item["exclusions"][0].__setitem__("reason", 7),
        "component kind": lambda item: item["component_profile"].__setitem__("kind", 7),
        "component root": lambda item: item["component_profile"].__setitem__(
            "definitions_root", 7
        ),
        "component pattern": lambda item: item["component_profile"].__setitem__(
            "reference_pattern", 7
        ),
        "component extensions": lambda item: item["component_profile"].__setitem__(
            "extensions", ".html"
        ),
        "surface label": lambda item: item.__setitem__("surface_labels", {"app": 7}),
        "surface selector": lambda item: item.__setitem__("surface_labels", {7: "app"}),
        "missing block": lambda item: item.pop("component_profile"),
    }

    for label, mutate in mutations.items():
        candidate = copy.deepcopy(valid)
        mutate(candidate)
        _rehash(candidate)
        assert validate_host_profile(candidate), label


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
