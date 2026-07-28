"""Decision propagation and portable register-or-exempt audit."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "coherence_audit.py"


def _load():
    spec = importlib.util.spec_from_file_location("coherence_audit_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write(path: Path, text: str = "value\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _json(path: Path, payload: object) -> None:
    _write(path, json.dumps(payload, indent=2) + "\n")


def _profile(host: Path) -> None:
    _json(
        host / ".engineering/project/surfaces.json",
        {
            "schema_version": 1,
            "first_party_surface_roots": [
                {"path": "app/pages", "group": "product", "candidate_depth": 1},
                {"path": "app/api", "group": "product", "candidate_depth": 1},
                {"path": "app/services", "group": "product", "candidate_depth": 1},
            ],
            "exemptions": [],
        },
    )


def _registry(host: Path, *, include_projects: bool) -> None:
    projects = (
        "  projects:\n"
        "    paths:\n"
        "      - app/pages/projects/\n"
        "      - app/api/projects/\n"
        "      - app/services/projects/\n"
        if include_projects
        else ""
    )
    _write(
        host / ".engineering/subsystems.yaml",
        "subsystems:\n"
        "  accounts:\n"
        "    paths:\n"
        "      - app/pages/accounts/\n"
        "      - app/api/accounts/\n"
        "      - app/services/accounts/\n"
        f"{projects}",
    )


def _host_surfaces(host: Path) -> None:
    for area in ("pages", "api", "services"):
        for product in ("accounts", "projects"):
            _write(host / "app" / area / product / "main.py")


def test_register_or_exempt_catches_new_cross_layer_surface(tmp_path: Path) -> None:
    audit = _load()
    _host_surfaces(tmp_path)
    _profile(tmp_path)
    _registry(tmp_path, include_projects=False)

    first = audit.audit_registry(tmp_path)
    assert first["status"] == "findings"
    project = next(row for row in first["candidates"] if row["candidate"] == "product:projects")
    assert project["disposition"] == "uncovered"
    assert project["paths"] == [
        "app/api/projects",
        "app/pages/projects",
        "app/services/projects",
    ]

    _registry(tmp_path, include_projects=True)
    repaired = audit.audit_registry(tmp_path)
    assert repaired["status"] == "pass"
    assert all(row["disposition"] == "registered" for row in repaired["candidates"])


def test_reasoned_exemption_is_a_valid_distinct_disposition(tmp_path: Path) -> None:
    audit = _load()
    _host_surfaces(tmp_path)
    _profile(tmp_path)
    _registry(tmp_path, include_projects=False)
    profile_path = tmp_path / ".engineering/project/surfaces.json"
    profile = json.loads(profile_path.read_text())
    profile["exemptions"] = [
        {
            "candidate": "product:projects",
            "reason": "Generated fixture surface, not a product subsystem.",
            "owner": "test-fixture policy",
            "review_trigger": "The directory gains a non-generated source file.",
        }
    ]
    _json(profile_path, profile)

    result = audit.audit_registry(tmp_path)

    assert result["status"] == "pass"
    assert next(
        row for row in result["candidates"] if row["candidate"] == "product:projects"
    )["disposition"] == "exempt"


def test_registry_integrity_is_separate_from_candidate_completeness(tmp_path: Path) -> None:
    audit = _load()
    _host_surfaces(tmp_path)
    _profile(tmp_path)
    _registry(tmp_path, include_projects=True)
    with (tmp_path / ".engineering/subsystems.yaml").open("a", encoding="utf-8") as stream:
        stream.write("  missing:\n    paths:\n      - app/does-not-exist/\n")

    result = audit.audit_registry(tmp_path)

    assert all(row["disposition"] == "registered" for row in result["candidates"])
    assert any(row["status"] == "missing" for row in result["integrity"])
    assert "registered path does not exist" in "\n".join(result["errors"])


def test_overlapping_registry_ownership_is_not_treated_as_complete(tmp_path: Path) -> None:
    audit = _load()
    _host_surfaces(tmp_path)
    _profile(tmp_path)
    _registry(tmp_path, include_projects=True)
    with (tmp_path / ".engineering/subsystems.yaml").open("a", encoding="utf-8") as stream:
        stream.write(
            "  projects-shadow:\n"
            "    paths:\n"
            "      - app/pages/projects/\n"
        )

    result = audit.audit_registry(tmp_path)

    project = next(row for row in result["candidates"] if row["candidate"] == "product:projects")
    assert project["disposition"] == "ambiguous-registration"
    assert "multiple registry owners" in "\n".join(result["errors"])


def test_impact_requires_every_surface_and_a_durable_deferred_item(tmp_path: Path) -> None:
    audit = _load()
    _write(
        tmp_path / ".claude/ideas/log.jsonl",
        json.dumps({"record_kind": "intake", "id": "tracked-work"}) + "\n",
    )
    _write(tmp_path / "evidence.txt")
    payload = {
        "schema_version": 1,
        "decision": "example",
        "obligations": [
            *(
                {
                    "surface": surface,
                    "disposition": "complete",
                    "evidence": ["evidence.txt"],
                }
                for surface in audit.SURFACES[:-1]
            ),
            {
                "surface": "release",
                "disposition": "deferred:tracked-work",
                "source_links": ["evidence.txt"],
                "review_trigger": "next release",
            },
        ],
        "legacy_fallbacks": [],
    }

    valid = audit.validate_impact(payload, tmp_path)
    payload["obligations"] = payload["obligations"][:-1]
    missing = audit.validate_impact(payload, tmp_path)

    assert valid["valid"]
    assert valid["deferred_work_items"] == ["tracked-work"]
    assert not missing["valid"]
    assert "missing obligation surfaces: release" in missing["errors"]


def test_unclassified_legacy_reference_is_reported(tmp_path: Path) -> None:
    audit = _load()
    _write(tmp_path / "scripts/allowed.py", "# .claude/old-state.json\n")
    _write(tmp_path / "README.md", "use .claude/old-state.json\n")
    fallback = {
        "legacy": ".claude/old-state.json",
        "canonical": ".engineering/old-state.json",
        "owner": "migration",
        "removal_condition": "after v2",
        "review_trigger": "release",
        "allowed_reference_prefixes": ["scripts/allowed.py"],
    }

    result = audit._reference_audit(tmp_path, [fallback])

    assert result["errors"] == [
        "unclassified legacy reference .claude/old-state.json: README.md"
    ]


def test_local_reference_checkouts_are_not_scanned_as_project_sources(
    tmp_path: Path,
) -> None:
    audit = _load()
    _write(
        tmp_path / ".engineering/local/reference-clone/README.md",
        "use .claude/old-state.json\n",
    )
    fallback = {
        "legacy": ".claude/old-state.json",
        "canonical": ".engineering/old-state.json",
        "owner": "migration",
        "removal_condition": "after v2",
        "review_trigger": "release",
        "allowed_reference_prefixes": ["scripts/allowed.py"],
    }

    result = audit._reference_audit(tmp_path, [fallback])

    assert result["errors"] == []
    assert result["rows"][0]["references"] == []


def test_host_only_adoption_requires_scope_clarification(tmp_path: Path) -> None:
    audit = _load()
    path = tmp_path / ".claude/ideas/log.jsonl"
    _write(
        path,
        json.dumps(
            {
                "id": "host-feature",
                "record_kind": "event",
                "outcome": "adopted",
                "summary": "Shipped in host-a only.",
            }
        )
        + "\n",
    )
    assert audit._idea_portability_audit(tmp_path)["status"] == "findings"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps(
                {
                    "id": "host-feature",
                    "record_kind": "event",
                    "event_kind": "scope-clarification",
                }
            )
            + "\n"
        )
    assert audit._idea_portability_audit(tmp_path)["status"] == "pass"


def test_optional_skill_tree_comparison_reports_real_content_drift(tmp_path: Path) -> None:
    audit = _load()
    left = tmp_path / "left"
    right = tmp_path / "right"
    _write(left / ".claude/skills/example/SKILL.md", "same\n")
    _write(right / ".claude/skills/example/SKILL.md", "same\n")
    assert audit._compare_skills(left, right)["status"] == "pass"
    _write(right / ".claude/skills/example/SKILL.md", "changed\n")
    result = audit._compare_skills(left, right)
    assert result == {
        "status": "drift",
        "differences": [{"skill": "example", "reason": "content-drift"}],
    }


def test_self_audit_passes_and_keeps_deferred_work_discoverable() -> None:
    audit = _load()

    result = audit.audit(ROOT)

    assert result["status"] == "pass", result["errors"]
    assert result["subsystem_coverage"]["status"] == "pass"
    assert result["scope_contract_adoption"]["status"] == "pass"
    authorities = result["authority_registry_drift"]
    assert authorities["decisions"]["drift"]
    assert authorities["decisions"]["enforcement_owner"] == "scripts/decisions.py audit"
    assert authorities["precedents"]["status"] == "pass"
    impact = next(
        row
        for row in result["decision_impacts"]
        if row["decision"] == "0021-engineering-folder-state-home"
    )
    assert impact["deferred_work_items"] == ["versioned-host-state-migrations"]
    maps = next(
        row
        for row in result["legacy_homes_and_references"]
        if row["legacy"] == ".claude/docs/subsystems/"
    )
    assert not maps["legacy_present"]
    assert maps["references"]
    assert maps["unclassified_references"] == []
    assert result["skill_tree_comparison"]["status"] == "not-configured"


def test_disposable_host_reproduces_state_home_and_registration_failures(tmp_path: Path) -> None:
    audit = _load()
    _host_surfaces(tmp_path)
    _profile(tmp_path)
    _registry(tmp_path, include_projects=False)
    _write(tmp_path / ".claude/subsystems.yaml", "subsystems: {}\n")
    fallback = {
        "legacy": ".claude/subsystems.yaml",
        "canonical": ".engineering/subsystems.yaml",
        "owner": "migration",
        "removal_condition": "after upgrade",
        "review_trigger": "release",
        "allowed_reference_prefixes": ["scripts/"],
    }
    reference = audit._reference_audit(tmp_path, [fallback])
    first = audit.audit_registry(tmp_path)
    assert reference["rows"][0]["legacy_present"]
    assert reference["rows"][0]["canonical_present"]
    assert "conflicting canonical and legacy homes" in "\n".join(reference["errors"])
    assert any("projects" in error for error in first["errors"])

    (tmp_path / ".claude/subsystems.yaml").unlink()
    _registry(tmp_path, include_projects=True)
    assert not audit._reference_audit(tmp_path, [fallback])["rows"][0][
        "legacy_present"
    ]
    assert audit.audit_registry(tmp_path)["status"] == "pass"
