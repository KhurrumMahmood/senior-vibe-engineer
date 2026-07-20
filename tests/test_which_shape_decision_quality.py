from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
ROUTE_PATH = REPO_ROOT / ".claude" / "skills" / "which-shape" / "scripts" / "route.py"


def _load_route():
    spec = importlib.util.spec_from_file_location("which_shape_quality_route", ROUTE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


route = _load_route()


def test_explicit_multi_phase_request_routes_only_the_first_phase(tmp_path):
    task = (
        "First audit this inherited subsystem, then propose a module boundary, "
        "and after approval execute the refactor and add a regression guard."
    )

    result = route.route(task, tmp_path)

    assert result["recommendation"]["shape"] in {"health-audit", "legacy-stabilization"}
    assert result["recommendation"]["shape"] != "regression-prevention"
    assert result["routing_scope"] == {
        "mode": "first_ordered_phase",
        "text": "audit this inherited subsystem",
    }


def test_before_delimiter_preserves_the_explicit_first_phase(tmp_path):
    result = route.route(
        "First audit this inherited subsystem before refactor and add a regression guard.",
        tmp_path,
    )

    assert result["recommendation"]["shape"] in {"health-audit", "legacy-stabilization"}
    assert result["routing_scope"]["text"] == "audit this inherited subsystem"


def test_generic_find_placeholder_does_not_create_an_executable_handoff(tmp_path, capsys):
    code = route.main([
        "First audit this inherited subsystem, then refactor it and add a guard.",
        "--project-root", str(tmp_path),
        "--library-root", str(REPO_ROOT),
        "--skip-log",
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["recommendation"]["shape"] == "health-audit"
    assert "handoff" not in payload


def test_stack_bound_shape_handoff_is_not_presented_as_executable(tmp_path, capsys):
    code = route.main([
        "Plan a new Rust CLI capability that spans configuration, persistence, "
        "and two user workflows.",
        "--project-root", str(tmp_path),
        "--library-root", str(REPO_ROOT),
        "--skip-log",
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["recommendation"]["shape"] == "feature-shaping"
    assert payload["handoff"]["skills"] == ["plan-feature"]
    assert payload["handoff"]["available"] is False
    assert payload["handoff"]["reason"] == "selected_skill_stack_bound_for_language"
    assert payload["handoff"]["blocked"] == [{
        "skill": "plan-feature",
        "language": "rust",
        "disposition": "framework-bound",
    }]
    assert payload["optional_install"]["available"] is False
    assert "command" not in payload["optional_install"]


def test_later_language_does_not_block_an_eligible_first_phase(tmp_path, capsys):
    code = route.main([
        "First plan a Python/Django capability for one workflow, then build the companion Rust CLI.",
        "--project-root", str(tmp_path),
        "--library-root", str(REPO_ROOT),
        "--skip-log",
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["recommendation"]["shape"] == "feature-shaping"
    assert payload["handoff"]["available"] is True


def test_plaintext_stack_block_names_capability_instead_of_bootstrap(tmp_path, capsys):
    code = route.main([
        "Plan a new Rust CLI capability that spans configuration and persistence.",
        "--project-root", str(tmp_path),
        "--library-root", str(REPO_ROOT),
        "--skip-log",
    ])

    output = capsys.readouterr().out
    assert code == 0
    assert "Handoff blocked by declared capability" in output
    assert "run the which-skill library bootstrap" not in output


def test_pending_go_shape_has_no_executable_handoff(tmp_path, capsys):
    code = route.main([
        "Propose a Go package boundary for the legacy module without editing source.",
        "--project-root", str(tmp_path),
        "--library-root", str(REPO_ROOT),
        "--skip-log",
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["recommendation"]["shape"] == "boundary-proposal"
    assert payload["handoff"]["available"] is False
    assert payload["handoff"]["reason"] == "selected_skill_not_validated_for_language"
    assert payload["optional_install"]["available"] is False
    assert "command" not in payload["optional_install"]
