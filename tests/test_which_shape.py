from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ROUTE_PATH = REPO_ROOT / ".claude" / "skills" / "which-shape" / "scripts" / "route.py"
PROJECT_PATH = REPO_ROOT / ".claude" / "skill-use" / "project.py"
COMPACT_PATH = REPO_ROOT / ".claude" / "skill-use" / "compact.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


route = _load_module("which_shape_route", ROUTE_PATH)
skill_project = _load_module("skill_use_project", PROJECT_PATH)
skill_compact = _load_module("skill_use_compact", COMPACT_PATH)


def _shape_for(task: str, project_root: Path) -> str:
    return route.route(task, project_root)["recommendation"]["shape"]


def test_unknown_inherited_repo_routes_to_project_intake(tmp_path):
    assert _shape_for("onboard an unknown inherited repo and figure out what loop to run", tmp_path) == "project-intake"


def test_narrow_typo_without_profile_routes_to_direct_change(tmp_path):
    assert _shape_for("fix one-line typo in the status label", tmp_path) == "direct-change"


def test_messy_slow_cleanup_routes_to_legacy_stabilization(tmp_path):
    assert _shape_for("this project feels messy and slow; identify the right cleanup loop", tmp_path) == "legacy-stabilization"


def test_broad_audit_routes_to_health_audit(tmp_path):
    assert _shape_for("what should we audit for a broad health sweep", tmp_path) == "health-audit"


def test_repeated_failure_routes_to_regression_prevention(tmp_path):
    assert _shape_for("this failure keeps coming back; prevent the regression again", tmp_path) == "regression-prevention"
    assert _shape_for("this bug keeps coming back", tmp_path) == "regression-prevention"


def test_durable_tradeoff_routes_to_decision_capture(tmp_path):
    assert _shape_for("choose the durable architecture tradeoff and record an ADR", tmp_path) == "decision-capture"


def test_which_skill_failure_examples_route_to_shapes(tmp_path):
    assert _shape_for("I need to onboard an unknown inherited repo and figure out what loop to run", tmp_path) == "project-intake"
    assert _shape_for("This project feels messy and slow; identify the right cleanup loop", tmp_path) != "regression-prevention"


def test_shapes_registry_schema_is_valid():
    payload = yaml.safe_load((ROUTE_PATH.parents[1] / "shapes.yml").read_text(encoding="utf-8"))
    assert route.validate_shapes_payload(payload) == []
    assert len({shape["id"] for shape in payload["shapes"]}) == len(payload["shapes"])


def test_recommendation_events_do_not_pollute_skill_useful_rate(tmp_path):
    log = tmp_path / "log.jsonl"
    events = [
        {
            "ts": "2026-05-17T00:00:00Z",
            "skill": "which-shape",
            "event_kind": "recommendation",
            "target": "messy project",
            "artifact": None,
            "outcome": "useful",
            "human_override": None,
            "duration_s": 0.1,
            "follow_up_skill": None,
            "shape": "legacy-stabilization",
            "confidence": "high",
            "project_context_state": "missing",
            "recommended_first_skill": "/map-subsystem",
        },
        {
            "ts": "2026-05-17T00:00:01Z",
            "skill": "fix-workflow",
            "target": "cluster-1",
            "artifact": "reports/fix-workflow/cluster-1.md",
            "outcome": "useful",
            "human_override": None,
            "duration_s": 12,
            "follow_up_skill": "prevent-regression",
        },
    ]
    log.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")

    loaded = skill_project._load_events(log)
    run_events, recommendation_events = skill_project._split_events(loaded)
    summary = skill_project._project(run_events)
    shape_summary = skill_project._project_shapes(recommendation_events)
    rendered = skill_project._render(summary, shape_summary, len(loaded), len(run_events), len(recommendation_events))

    assert set(summary) == {"fix-workflow"}
    assert shape_summary["legacy-stabilization"]["n"] == 1
    assert "`legacy-stabilization`" in rendered


SKILLS_DIR = REPO_ROOT / ".claude" / "skills"


def _seed_manifest(root: Path, payload: dict) -> None:
    eng = root / ".engineering"
    eng.mkdir(parents=True, exist_ok=True)
    (eng / "manifest.json").write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_active_skill_steps_have_no_inactive_annotation(tmp_path):
    # No manifest => every skill active => project-intake's concrete steps
    # (/adapt-project, /project-interview) are not flagged.
    result = route.route(
        "onboard an unknown inherited repo and figure out what loop to run",
        tmp_path, skills_dir=SKILLS_DIR,
    )
    assert result["recommendation"]["shape"] == "project-intake"
    assert result["recommendation"]["inactive_steps"] == []


def test_inactive_skill_step_is_flagged_with_reason(tmp_path):
    _seed_manifest(tmp_path, {
        "version": 1,
        "skills": {"default": "active",
                   "inactive": {"project-interview": "no interview step here"}},
    })
    result = route.route(
        "onboard an unknown inherited repo and figure out what loop to run",
        tmp_path, skills_dir=SKILLS_DIR,
    )
    assert result["recommendation"]["shape"] == "project-intake"
    flagged = {s["skill"]: s["reason"] for s in result["recommendation"]["inactive_steps"]}
    assert flagged == {"project-interview": "no interview step here"}


def test_generic_find_placeholder_is_not_flagged(tmp_path):
    # health-audit's sequence uses "selected /find-* skill" — a placeholder that
    # resolves to no real skill, so it is never flagged even when some find-*
    # skills are deactivated.
    _seed_manifest(tmp_path, {
        "version": 1,
        "skills": {"default": "active", "inactive": {"find-route-sprawl": "no routes"}},
    })
    result = route.route(
        "audit the codebase health with a broad scan", tmp_path, skills_dir=SKILLS_DIR,
    )
    assert result["recommendation"]["inactive_steps"] == []


def test_render_markdown_surfaces_inactive_steps(tmp_path):
    _seed_manifest(tmp_path, {
        "version": 1,
        "skills": {"default": "active",
                   "inactive": {"project-interview": "no interview step here"}},
    })
    result = route.route(
        "onboard an unknown inherited repo and figure out what loop to run",
        tmp_path, skills_dir=SKILLS_DIR,
    )
    md = route.render_markdown(result)
    assert "Inactive here" in md
    assert "/project-interview" in md
    assert "no interview step here" in md


# --- status.json grounding (spec IM-9, AR-5) ---------------------------------


def _grounded_doc(pending: int = 2) -> dict:
    return {
        "schema_version": 1,
        "generated_at": "2026-06-12T00:00:00+00:00",
        "root": "x",
        "sections": {
            "pending_approvals": {"available": True, "pending_count": pending, "items": []},
            "staleness": {"available": True, "stale_count": 0, "artifacts": []},
            "queue": {"available": False, "reason": "none"},
            "in_flight": {"available": False, "reason": "none"},
        },
    }


def test_route_json_byte_identical_when_status_absent(tmp_path):
    """AR-5: with no status.json, grounding must not change a single byte."""
    task = "this project feels messy and slow; identify the right cleanup loop"
    baseline = json.dumps(route.route(task, tmp_path), indent=2, sort_keys=True)
    grounded = json.dumps(
        route.route(task, tmp_path, status_path=tmp_path / "nope.json"),
        indent=2, sort_keys=True,
    )
    assert baseline == grounded


def test_route_rationale_cites_projection_signal_when_present(tmp_path):
    status = tmp_path / "status.json"
    status.write_text(json.dumps(_grounded_doc(pending=2)))
    result = route.route(
        "this project feels messy and slow; identify the right cleanup loop",
        tmp_path, status_path=status,
    )
    cited = [r for r in result["recommendation"]["rationale"] if "project status" in r]
    assert cited == ["project status: 2 proposal(s) pending approval"]


def test_stale_projection_dropped_silently(tmp_path):
    doc = _grounded_doc()
    doc["generated_at"] = "2020-01-01T00:00:00+00:00"  # predates the live source below
    status = tmp_path / "status.json"
    status.write_text(json.dumps(doc))
    eng = tmp_path / ".engineering"
    eng.mkdir()
    (eng / "project-state.json").write_text("{}")  # mtime = now > generated_at
    assert route.load_status_signals(tmp_path, status) == []


def test_malformed_projection_dropped_silently(tmp_path):
    status = tmp_path / "status.json"
    status.write_text("{not json")
    assert route.load_status_signals(tmp_path, status) == []


def test_compaction_summarizes_recommendations_separately():
    events = [
        {
            "ts": "2026-05-17T00:00:00Z",
            "skill": "which-shape",
            "event_kind": "recommendation",
            "target": "messy project",
            "artifact": None,
            "outcome": "overridden",
            "human_override": "wrong-shape: should have started with project-intake",
            "duration_s": 0.1,
            "follow_up_skill": None,
            "shape": "legacy-stabilization",
            "confidence": "medium",
        },
        {
            "ts": "2026-05-17T00:00:01Z",
            "skill": "fix-workflow",
            "target": "cluster-1",
            "artifact": "reports/fix-workflow/cluster-1.md",
            "outcome": "useful",
            "human_override": None,
            "duration_s": 12,
            "follow_up_skill": None,
        },
    ]

    digest = skill_compact._render_digest(events, "2026-05-17T00:00:00Z", "2026-05-17T00:00:01Z")

    assert "| `fix-workflow` | 1 | 100% | 0% |" in digest
    assert "## Shape recommendation feedback" in digest
    assert "`legacy-stabilization`" in digest
