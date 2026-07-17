from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from _lib.distribution_contracts import (
    ALIAS_ROW_FIELDS,
    DistributionContractError,
    SURFACE_IDS,
    TABLE_NAMES,
    canonical_json_bytes,
    load_canonical_json,
    load_distribution_tables,
    validate_alias_table,
)
from _lib.host_profile import HOST_PROFILE_SCHEMA_VERSION


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = ROOT / ".claude/skills/_common/distribution"
CANONICAL_NAMES = {"plan-feature", "which-shape", "which-skill"}


def _alias(public_name: str, target: str = "plan-feature") -> dict[str, object]:
    return {
        "public_name": public_name,
        "canonical_target": target,
        "surface_spellings": {
            surface: public_name for surface in sorted(SURFACE_IDS)
        },
        "introduced_release": 1,
        "retirement_release": None,
    }


FIXTURE_ALIAS = _alias("plan-feature-v1")


def _table(*rows: dict[str, object]) -> dict[str, object]:
    return {"aliases": list(rows), "schema_version": 1}


def test_production_reference_tables_are_canonical_and_semantically_valid() -> None:
    tables = load_distribution_tables(
        CONTRACT_ROOT,
        canonical_names=CANONICAL_NAMES,
    )

    assert tables["aliases-v1"] == {"aliases": [], "schema_version": 1}
    assert tables["legacy-layouts-v1"] == {"layouts": [], "schema_version": 1}
    assert tables["compatibility-v1"]["host_profile_schema"] == {
        "lower": HOST_PROFILE_SCHEMA_VERSION,
        "upper": HOST_PROFILE_SCHEMA_VERSION,
    }
    assert HOST_PROFILE_SCHEMA_VERSION == 1


@pytest.mark.parametrize("table_name", TABLE_NAMES)
def test_reference_table_raw_bytes_are_exact_canonical_jcs(table_name: str) -> None:
    path = CONTRACT_ROOT / f"{table_name}.json"
    parsed = json.loads(path.read_bytes())

    assert path.read_bytes() == canonical_json_bytes(parsed)


def test_canonical_loader_rejects_pretty_or_newline_terminated_json(tmp_path: Path) -> None:
    path = tmp_path / "aliases-v1.json"
    path.write_text('{"aliases": [], "schema_version": 1}\n', encoding="utf-8")

    with pytest.raises(DistributionContractError, match="not RFC-8785 canonical"):
        load_canonical_json(path)


def test_fixture_alias_is_valid_but_absent_from_release_inputs_and_artifacts() -> None:
    rows, resolved = validate_alias_table(_table(FIXTURE_ALIAS), CANONICAL_NAMES)

    assert rows == [FIXTURE_ALIAS]
    assert resolved == {"plan-feature-v1": "plan-feature"}
    assert load_canonical_json(CONTRACT_ROOT / "aliases-v1.json")["aliases"] == []
    for path in CONTRACT_ROOT.iterdir():
        if path.is_file():
            assert b"plan-feature-v1" not in path.read_bytes()


def test_alias_chain_resolves_only_to_a_known_canonical_target() -> None:
    rows, resolved = validate_alias_table(
        _table(
            _alias("plan-feature-old", "plan-feature-v1"),
            FIXTURE_ALIAS,
        ),
        CANONICAL_NAMES,
    )

    assert [row["public_name"] for row in rows] == [
        "plan-feature-old",
        "plan-feature-v1",
    ]
    assert resolved == {
        "plan-feature-old": "plan-feature",
        "plan-feature-v1": "plan-feature",
    }


def _invalid_alias_cases() -> list[tuple[object, str]]:
    missing = copy.deepcopy(FIXTURE_ALIAS)
    missing.pop("retirement_release")
    extra = {**FIXTURE_ALIAS, "migration_note": "not allowed"}
    missing_surface = copy.deepcopy(FIXTURE_ALIAS)
    missing_surface["surface_spellings"].pop("gemini")
    extra_surface = copy.deepcopy(FIXTURE_ALIAS)
    extra_surface["surface_spellings"]["windsurf"] = "plan-feature-v1"
    divergent = copy.deepcopy(FIXTURE_ALIAS)
    divergent["surface_spellings"]["codex"] = "engineering-skills:plan-feature-v1"
    return [
        (_table(missing), "must contain exactly"),
        (_table(extra), "must contain exactly"),
        (_table(missing_surface), "must contain exactly"),
        (_table(extra_surface), "must contain exactly"),
        (_table(divergent), "must all equal public_name"),
        (_table({**FIXTURE_ALIAS, "public_name": "Plan_Feature"}), "safe public name"),
        (
            _table({**FIXTURE_ALIAS, "canonical_target": "plan_feature"}),
            "canonical_target is not a safe public name",
        ),
        (_table({**FIXTURE_ALIAS, "introduced_release": True}), "positive integer"),
        (_table({**FIXTURE_ALIAS, "introduced_release": 1.0}), "positive integer"),
        (_table({**FIXTURE_ALIAS, "introduced_release": 0}), "positive integer"),
        (
            _table({**FIXTURE_ALIAS, "retirement_release": True}),
            "at least introduced_release",
        ),
        (
            _table({**FIXTURE_ALIAS, "retirement_release": 1.0}),
            "at least introduced_release",
        ),
        (
            _table({**FIXTURE_ALIAS, "retirement_release": 0}),
            "at least introduced_release",
        ),
        (_table(_alias("plan-feature")), "alias collision"),
        (_table(FIXTURE_ALIAS, FIXTURE_ALIAS), "alias collision"),
        (_table(_alias("plan-feature-v1", "missing-skill")), "stale target"),
        (
            _table(
                _alias("plan-feature-old", "plan-feature-v1"),
                _alias("plan-feature-v1", "plan-feature-old"),
            ),
            "alias cycle",
        ),
        (
            _table(FIXTURE_ALIAS, _alias("plan-feature-old")),
            "must be sorted by public_name",
        ),
    ]


@pytest.mark.parametrize(("table", "message"), _invalid_alias_cases())
def test_alias_reference_contract_rejects_invalid_rows(
    table: object, message: str
) -> None:
    with pytest.raises(DistributionContractError, match=message):
        validate_alias_table(table, CANONICAL_NAMES)


def test_alias_row_contract_has_exactly_the_amended_five_keys() -> None:
    assert ALIAS_ROW_FIELDS == {
        "canonical_target",
        "introduced_release",
        "public_name",
        "retirement_release",
        "surface_spellings",
    }
