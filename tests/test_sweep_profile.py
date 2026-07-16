from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from sweep.profile import SweepProfileError, load_sweep_profile, validate_sweep_profile


REPO_ROOT = Path(__file__).resolve().parents[1]


def _profile() -> dict[str, object]:
    return {
        "schema_version": 1,
        "languages": ["go", "python", "rust", "typescript"],
        "paths": ["."],
        "roots": ["."],
        "exclusions": [],
        "case_sensitive": True,
    }


def test_profile_is_strict_deterministic_and_registry_backed(tmp_path):
    document = _profile()
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    first = load_sweep_profile(path)
    second = validate_sweep_profile(copy.deepcopy(document))

    assert first == second
    assert first.as_document() == document
    assert first.sha256 == second.sha256


def test_required_mixed_profile_is_canonical_and_content_addressed():
    profile = load_sweep_profile(
        REPO_ROOT / "tests/fixtures/sweep/profiles/mixed-case-sensitive.json"
    )

    assert profile.as_document() == _profile()
    assert profile.sha256 == "13bb953249510890e58d3d78b6d1de3289b948b9d790c05a699aa91d99bedd50"


@pytest.mark.parametrize("language", ["go", "python", "rust", "typescript"])
def test_required_single_language_profiles_are_strict_and_match_live_hosts(language):
    profile = load_sweep_profile(
        REPO_ROOT / f"tests/fixtures/sweep/profiles/{language}-case-sensitive.json"
    )

    assert profile.languages == (language,)
    assert profile.paths == (".",)
    assert profile.roots == (".",)
    assert profile.exclusions == ()
    for state in ("before", "after", "clean"):
        assert (REPO_ROOT / f"tests/fixtures/sweep/hosts/{language}/{state}").is_dir()


def test_required_mixed_host_contains_every_live_tool_project_boundary():
    required = {
        "pyproject.toml",
        "package.json",
        "tsconfig.json",
        "eslint.config.mjs",
        "Cargo.toml",
        "Cargo.lock",
        "go.mod",
    }
    mixed = REPO_ROOT / "tests/fixtures/sweep/hosts/mixed"

    for state in ("before", "after", "clean"):
        root = mixed / state
        assert required.issubset(
            path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda row: row.update(case_sensitive="yes"), "explicit boolean"),
        (lambda row: row["languages"].append("cobol"), "sorted unique"),
        (lambda row: row.update(languages=["css"]), "lack a registered sweep battery"),
        (lambda row: row.update(paths=["../src"]), "outside the repository"),
        (lambda row: row.update(paths=["src"], roots=["packages"]), "outside roots"),
        (
            lambda row: row.update(paths=["vendor"], exclusions=["vendor"]),
            "fully excluded",
        ),
        (lambda row: row.update(exclusions=["../vendor"]), "outside the repository"),
    ],
)
def test_profile_rejects_invalid_scope_and_battery(mutation, message):
    document = _profile()
    mutation(document)

    with pytest.raises(SweepProfileError, match=message):
        validate_sweep_profile(document)


def test_case_insensitive_profile_rejects_equivalent_duplicates():
    document = _profile()
    document["case_sensitive"] = False
    document["paths"] = ["SRC", "src"]

    with pytest.raises(SweepProfileError, match="case-equivalent duplicates"):
        validate_sweep_profile(document)


def test_profile_rejects_scope_native_tools_do_not_execute():
    document = _profile()
    document.update(paths=["src"], roots=["."], exclusions=[])

    with pytest.raises(SweepProfileError, match="full-root providers"):
        validate_sweep_profile(document)


def test_profile_reader_is_bounded(tmp_path):
    path = tmp_path / "profile.json"
    path.write_bytes(b" " * 65_537)

    with pytest.raises(SweepProfileError, match="exceeds 65536-byte limit"):
        load_sweep_profile(path)
