from __future__ import annotations

import json
from pathlib import Path

from distribution_probe import build_bundle_inventory
from _lib.portfolio_snapshots import (
    ACTIVATION_MODES,
    SURFACE_CONTRACTS,
    build_portfolio_snapshots,
)


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "tests/fixtures/wp3/portfolio-snapshots-v1.json"
ROUTERS = ["which-shape", "which-skill"]


def _expected() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def test_three_portfolios_match_the_checked_exact_snapshot() -> None:
    expected = _expected()
    alias_authority = build_bundle_inventory(ROOT)["aliases"]
    assert alias_authority == expected["alias_authority"]

    actual = build_portfolio_snapshots(
        ROOT,
        aliases=alias_authority,
        host_owned_by_surface=expected["host_owned_by_surface"],
    )

    assert actual == expected["snapshot"]


def test_core_and_typescript_portfolios_do_not_leak_framework_native_content() -> None:
    portfolios = _expected()["snapshot"]["portfolios"]

    for name in ("core-only", "typescript-react"):
        portfolio = portfolios[name]
        assert portfolio["catalog"]
        assert {row["layer"] for row in portfolio["catalog"]} == {"core"}
        assert portfolio["framework_native_content_hits"] == []
        assert all(row["selected_bindings"] == ["core"] for row in portfolio["catalog"])
        assert all(len(row["source_sha256"]) == 64 for row in portfolio["catalog"])
        assert all(len(row["rendered_sha256"]) == 64 for row in portfolio["catalog"])


def test_typescript_snapshot_proves_selection_without_claiming_wp6_behavior() -> None:
    portfolio = _expected()["snapshot"]["portfolios"]["typescript-react"]

    assert portfolio["profile_stack"] == {
        "frameworks": ["react"],
        "languages": ["typescript"],
    }
    assert portfolio["selection_claim"] == "projection-and-binding-selection-only"
    assert portfolio["selected_non_core_bindings"] == []
    assert "django" not in json.dumps(portfolio, sort_keys=True).lower()


def test_django_snapshot_preserves_the_exact_ar1_applicable_set() -> None:
    portfolio = _expected()["snapshot"]["portfolios"]["django"]
    catalog_names = [row["name"] for row in portfolio["catalog"]]

    assert catalog_names == portfolio["ar1_applicable_names"]
    assert len(catalog_names) == 76
    assert portfolio["ar1_names_sha256"] == (
        "e7ed28551e071089e2f11c76713f1c1ec7c2d342107109a22630c6f9828ff138"
    )


def test_default_and_named_activation_sets_are_exact_for_every_surface() -> None:
    snapshot = _expected()["snapshot"]

    assert list(ACTIVATION_MODES) == ["router-only", "full-discovery"]
    assert snapshot["activation_modes"] == list(ACTIVATION_MODES)
    for portfolio in snapshot["portfolios"].values():
        assert portfolio["default_activation"] == ROUTERS
        assert portfolio["non_discovered_catalog"] == [
            row["name"] for row in portfolio["catalog"]
        ]
        for surface in portfolio["surfaces"].values():
            router_only = surface["states"]["router-only"]
            named = surface["states"]["named-non-router"]
            full = surface["states"]["full-discovery"]
            assert router_only["canonical_procedures"] == ROUTERS
            assert len(router_only["public_names"]) == 2
            assert len(named["canonical_procedures"]) == 3
            assert len(named["public_names"]) == 3
            assert full["mode"] == "full-discovery"
            assert full["canonical_procedures"] == portfolio["non_discovered_catalog"]
            assert full["public_names"] == portfolio["non_discovered_catalog"]
            assert router_only["host_owned_discovery"] == surface["host_owned_discovery"]
            assert named["host_owned_discovery"] == surface["host_owned_discovery"]
            assert full["host_owned_discovery"] == surface["host_owned_discovery"]


def test_public_syntax_namespace_and_generated_identity_table_is_pinned() -> None:
    assert SURFACE_CONTRACTS == {
        "augment": {
            "generated_identity": ".augment/rules/imported/{public_name}/SKILL.md",
            "public_syntax": "use skill {public_name}",
        },
        "claude-code": {
            "generated_identity": ".claude/skills/{public_name}/SKILL.md",
            "public_syntax": "/{public_name}",
        },
        "codex": {
            "generated_identity": "skills/{public_name}/SKILL.md",
            "plugin": "engineering-skills",
            "public_syntax": "$engineering-skills:{public_name}",
        },
        "cursor": {
            "generated_identity": ".cursor/rules/{public_name}/SKILL.mdc",
            "public_syntax": "use skill {public_name}",
        },
        "gemini": {
            "generated_identity": ".gemini/skills/{public_name}/SKILL.md",
            "public_syntax": "use skill {public_name}",
        },
    }


def test_empty_versioned_alias_authority_exposes_the_im14_dependency_exactly() -> None:
    expected = _expected()
    assert expected["alias_authority"] == []

    for portfolio in expected["snapshot"]["portfolios"].values():
        assert portfolio["aliases"] == []
        for surface in portfolio["surfaces"].values():
            states = surface["states"]
            assert states["named-alias"] == {
                "available": False,
                "dependency": "aliases-v1 has no public alias rows",
            }
            assert states["cumulative-canonical-alias"] == {
                "available": False,
                "dependency": "aliases-v1 has no public alias rows",
            }
