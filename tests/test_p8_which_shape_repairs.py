"""P8 regressions for which-shape routing and on-demand handoff closure."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ROUTE_PATH = ROOT / ".claude" / "skills" / "which-shape" / "scripts" / "route.py"


def _load_route():
    spec = importlib.util.spec_from_file_location("p8_which_shape_route", ROUTE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


route = _load_route()


def _route_json(prompt: str, project_root: Path, capsys) -> dict:
    code = route.main(
        [
            prompt,
            "--project-root",
            str(project_root),
            "--library-root",
            str(ROOT),
            "--skip-log",
            "--json",
        ]
    )
    assert code == 0
    return json.loads(capsys.readouterr().out)


def test_onboarding_operating_loop_beats_generic_choose_cue(tmp_path):
    onboarding = route.route(
        "onboard this unknown inherited Python repository and choose the right operating loop",
        tmp_path,
    )
    durable_decision = route.route(
        "choose the durable architecture tradeoff and record an ADR",
        tmp_path,
    )

    assert onboarding["recommendation"]["shape"] == "project-intake"
    assert onboarding["recommendation"]["first_next"] == "/adapt-project"
    assert durable_decision["recommendation"]["shape"] == "decision-capture"


@pytest.mark.parametrize(
    ("prompt", "shape", "closure"),
    [
        (
            "This is not a typo; the whole subsystem terminology is wrong and "
            "the glossary-backed domain concept must be renamed everywhere.",
            "concept-rename",
            ["rename-concept", "find-concept-divergence", "map-subsystem"],
        ),
        (
            "The parser bug keeps coming back after each fix; prevent this "
            "regression from returning again.",
            "regression-prevention",
            ["prevent-regression", "find-implicit-state", "map-subsystem"],
        ),
    ],
)
def test_frozen_shape_cases_return_complete_capability_closure(
    prompt, shape, closure, tmp_path, capsys
):
    payload = _route_json(prompt, tmp_path, capsys)

    assert payload["recommendation"]["shape"] == shape
    assert payload["handoff"]["skills"] == closure
    assert payload["handoff"]["available"] is True
    assert payload["handoff"]["capabilities"]["available"] is True
    assert payload["handoff"]["capabilities"]["skills"][0]["closure_skills"] == closure


@pytest.mark.parametrize(
    "prompt",
    [
        "Propose a database migration plan for the users table.",
        "Draft a database migration plan for the accounts table.",
    ],
)
def test_generic_database_migration_plan_asks_before_routing(prompt, tmp_path):
    result = route.route(prompt, tmp_path)

    assert result["recommendation"]["confidence"] == "low"
    assert result["discriminating_question"] == (
        "Is the schema or rollout choice still open, or are you planning an "
        "already-approved database change?"
    )
    assert (
        "Discriminating question: Is the schema or rollout choice still open"
        in route.render_markdown(result)
    )
