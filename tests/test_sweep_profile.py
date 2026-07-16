from __future__ import annotations

import copy
import json

import pytest

from sweep.profile import SweepProfileError, load_sweep_profile, validate_sweep_profile


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
