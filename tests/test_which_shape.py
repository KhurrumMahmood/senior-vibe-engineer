from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import yaml

from _lib.host_profile import profile_host

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


def test_whole_codebase_route_reports_incomplete_before_profile_exists(tmp_path):
    result = route.route("audit the whole codebase with a broad health sweep", tmp_path)

    perimeter = result["recommendation"]["perimeter_audit"]
    assert perimeter["status"] == "incomplete_coverage"
    assert perimeter["invoked"] is False
    assert result["recommendation"]["rationale"][0].startswith(
        "whole-codebase perimeter is incomplete"
    )


def test_whole_codebase_route_invokes_perimeter_and_withholds_clean_conclusion(tmp_path):
    (tmp_path / "package.json").write_text('{"devDependencies":{"typescript":"5.9.3"}}')
    (tmp_path / "tsconfig.json").write_text("{}\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "large.ts").write_text("export const value = 1;\n" * 3200)
    profile_path = tmp_path / ".engineering" / "project" / "host-profile.json"
    profile_path.parent.mkdir(parents=True)
    profile_path.write_text(json.dumps(profile_host(tmp_path)), encoding="utf-8")
    empty_skills = tmp_path / "empty-skills"
    empty_skills.mkdir()

    result = route.route(
        "audit the whole codebase with a broad health sweep",
        tmp_path,
        skills_dir=empty_skills,
    )

    perimeter = result["recommendation"]["perimeter_audit"]
    assert perimeter["invoked"] is True
    assert perimeter["exit_code"] == 1
    assert perimeter["status"] == "incomplete_coverage"
    assert perimeter["coverage_mode"] == "executable-evidence"
    assert perimeter["gaps"][0]["language"] == "typescript"


def test_repeated_failure_routes_to_regression_prevention(tmp_path):
    assert _shape_for("this failure keeps coming back; prevent the regression again", tmp_path) == "regression-prevention"
    assert _shape_for("this bug keeps coming back", tmp_path) == "regression-prevention"


def test_durable_tradeoff_routes_to_decision_capture(tmp_path):
    assert _shape_for("choose the durable architecture tradeoff and record an ADR", tmp_path) == "decision-capture"


def test_concept_rename_strong_cues_route_to_concept_rename(tmp_path):
    # Frame review F4b probe: a negated "typo" must no longer beat the
    # registry's own concept-rename shape.
    assert _shape_for("this is not a typo, the whole subsystem terminology is wrong", tmp_path) == "concept-rename"
    assert _shape_for("rename the domain concept across the glossary and all surfaces", tmp_path) == "concept-rename"


def test_project_structure_routes_to_project_structure_not_path_move(tmp_path):
    assert _shape_for("make the repo top-level folder structure more intuitive", tmp_path) == "project-structure"


def test_task_closeout_strong_cues_route_to_task_closeout(tmp_path):
    assert _shape_for("the work is finished; run a closeout cleanup over the changed files", tmp_path) == "task-closeout"


def test_which_skill_failure_examples_route_to_shapes(tmp_path):
    assert _shape_for("I need to onboard an unknown inherited repo and figure out what loop to run", tmp_path) == "project-intake"
    assert _shape_for("This project feels messy and slow; identify the right cleanup loop", tmp_path) != "regression-prevention"


def test_shapes_registry_schema_is_valid():
    payload = yaml.safe_load((ROUTE_PATH.parents[1] / "shapes.yml").read_text(encoding="utf-8"))
    assert route.validate_shapes_payload(payload) == []
    assert len({shape["id"] for shape in payload["shapes"]}) == len(payload["shapes"])


def _registry_payload() -> dict:
    return yaml.safe_load((ROUTE_PATH.parents[1] / "shapes.yml").read_text(encoding="utf-8"))


def test_validate_passes_on_real_registry(capsys):
    assert route.main(["--validate"]) == 0
    assert "shapes OK" in capsys.readouterr().out


def _mystery_shape(**overrides) -> dict:
    shape = {
        "id": "mystery-shape",
        "title": "Mystery Shape",
        "summary": "Added to the registry for validation tests.",
        "first_next": "/orient",
        "sequence": ["/orient"],
        "stop": "Stop.",
        "cues": {"strong": ["mystery"], "normal": [], "negative": []},
        "alternatives": [],
    }
    shape.update(overrides)
    return shape


def _validate_registry_with(tmp_path, shape: dict) -> tuple[int, str]:
    payload = _registry_payload()
    payload["shapes"].append(shape)
    shapes_path = tmp_path / "shapes.yml"
    shapes_path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return route.main(["--validate", "--shapes", str(shapes_path)]), str(shapes_path)


def test_validate_fails_on_shape_without_boost_block(tmp_path, capsys):
    # F4b guard, data-driven form: every shape must declare a boost block
    # (an empty mapping is the explicit opt-out).
    code, _ = _validate_registry_with(tmp_path, _mystery_shape())
    assert code == 2
    assert "boost" in capsys.readouterr().err


def test_validate_accepts_explicitly_empty_boost_block(tmp_path, capsys):
    code, shapes_path = _validate_registry_with(tmp_path, _mystery_shape(boost={}))
    assert code == 0
    assert "shapes OK" in capsys.readouterr().out
    # And the unboosted shape still routes on its base cues without crashing.
    result = route.route("mystery", tmp_path, Path(shapes_path))
    assert result["recommendation"]["shape"] == "mystery-shape"


def test_validate_fails_on_malformed_boost_blocks(tmp_path, capsys):
    cases = [
        # (boost block, expected error fragment)
        ({"cues": ["mystery"], "weight": "30", "rationale": "r"}, "weight must be an integer"),
        ({"cues": [], "weight": 30, "rationale": "r"}, "cues must be a non-empty list"),
        ({"cues": ["mystery"], "weight": 30, "rationale": "r", "wieght": 1}, "unexpected keys"),
        ({"mode": "sometimes", "rules": [{"conditions": [], "weight": 1, "rationale": "r"}]},
         "mode must be one of"),
        ({"mode": "additive", "rules": [{"conditions": [{"type": "moon-phase"}], "weight": 1, "rationale": "r"}]},
         "unknown condition type"),
        ({"mode": "additive", "rules": [{"conditions": [{"type": "cue-hit"}], "weight": 1, "rationale": "r"}]},
         "exactly one of cues / cues_from"),
        ({"mode": "additive",
          "rules": [{"conditions": [{"type": "cue-hit", "cues_from": "no-such-shape"}], "weight": 1, "rationale": "r"}]},
         "cues_from must name a shape with a simple cues/weight boost"),
        ({"mode": "additive",
          # regression-prevention has a rules-form boost: not a valid cues_from target
          "rules": [{"conditions": [{"type": "cue-hit", "cues_from": "regression-prevention"}], "weight": 1, "rationale": "r"}]},
         "cues_from must name a shape with a simple cues/weight boost"),
    ]
    for boost, fragment in cases:
        code, _ = _validate_registry_with(tmp_path, _mystery_shape(boost=boost))
        err = capsys.readouterr().err
        assert code == 2, boost
        assert fragment in err, (boost, err)


# --- Path A parity battery ----------------------------------------------------
# Scores recorded from the pre-migration scorer (hard-coded boost arms,
# commit-time baseline in .claude/tasks/skill-repairs/which-shape/
# parity_baseline.json). The data-driven registry reproduced every entry
# byte-for-byte BEFORE the vocabulary restoration; the four prompts marked
# "restored" then changed intentionally when the trimmed boost tokens
# (crash / regression / back / new / extract / split) were re-added as data.
PARITY_BATTERY = [
    # (prompt, shape, score, confidence)
    ("help me with the thing we discussed", "bug-fix", 0, "low"),  # fallback tiebreak
    ("this is not a typo, the whole subsystem terminology is wrong", "concept-rename", 28, "medium"),
    ("fix one-line typo in the status label", "direct-change", 58, "high"),
    ("this bug keeps coming back", "regression-prevention", 50, "high"),
    ("this failure keeps coming back; prevent the regression again", "regression-prevention", 78, "high"),
    ("onboard an unknown inherited repo and figure out what loop to run", "project-intake", 76, "high"),
    ("adapt this codebase", "project-intake", 52, "high"),
    ("this project feels messy and slow; identify the right cleanup loop", "legacy-stabilization", 46, "high"),
    ("what should we audit for a broad health sweep", "health-audit", 62, "high"),
    ("choose the durable architecture tradeoff and record an ADR", "decision-capture", 78, "high"),
    ("add a new endpoint for the export workflow", "feature-shaping", 62, "high"),
    ("execute the approved refactor proposal", "refactor-execution", 68, "high"),
    ("rename the domain concept across the glossary and all surfaces", "concept-rename", 58, "high"),
    ("the work is finished; run a closeout cleanup over the changed files", "task-closeout", 66, "high"),
    # restored vocabulary — intentional deltas vs the narrowed scorer:
    ("the app shows a crash on startup", "bug-fix", 34, "medium"),  # was bug-fix/4/low
    ("stop this regression from coming back", "regression-prevention", 34, "medium"),  # was bug-fix/4/low (tiebreak)
    ("build a new export page", "feature-shaping", 30, "medium"),  # was feature-shaping/4/low
    ("extract the service and split the module", "refactor-execution", 28, "medium"),  # was refactor-execution/4/low
]


def test_parity_battery_against_recorded_scores(tmp_path):
    for prompt, shape, score, confidence in PARITY_BATTERY:
        rec = route.route(prompt, tmp_path)["recommendation"]
        got = (rec["shape"], rec["score"], rec["confidence"])
        assert got == (shape, score, confidence), (prompt, got)


def test_restored_boost_tokens_come_from_data(tmp_path):
    # The curated re-added tokens must trigger their shapes' boosts via
    # shapes.yml, at boosted (>= medium) confidence — the routing-quality
    # regression the constant-sync narrowing introduced.
    rec = route.route("the app shows a crash on startup", tmp_path)["recommendation"]
    assert rec["shape"] == "bug-fix"
    assert rec["confidence"] == "medium"
    assert "task starts from a failure symptom" in rec["rationale"]

    rec = route.route("stop this regression from coming back", tmp_path)["recommendation"]
    assert rec["shape"] == "regression-prevention"
    assert "task is about recurrence or guardrails" in rec["rationale"]


def test_regression_compound_boost_reads_bug_cues_via_cues_from(tmp_path):
    # cues_from: bug-fix now includes the restored "crash" token.
    rec = route.route("the crash keeps happening again", tmp_path)["recommendation"]
    assert rec["shape"] == "regression-prevention"
    assert "failure symptom is paired with recurrence language" in rec["rationale"]


def test_recommendation_events_do_not_pollute_skill_useful_rate(tmp_path):
    log = tmp_path / "log.jsonl"
    events = [
        {
            "ts": "2026-05-17T00:00:00Z",
            "skill": "which-shape",
            "event_kind": "recommendation",
            "target": "messy project",
            "artifact": None,
            "outcome": "unscored",
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


def test_outcome_defaults_to_unscored(tmp_path):
    log = tmp_path / "log.jsonl"
    assert route.main([
        "fix one-line typo in the status label",
        "--project-root", str(tmp_path),
        "--log", str(log),
    ]) == 0
    event = json.loads(log.read_text(encoding="utf-8").strip())
    assert event["event_kind"] == "recommendation"
    assert event["outcome"] == "unscored"


def test_compaction_overridden_rate_counts_only_scored_events():
    base = {
        "skill": "which-shape",
        "event_kind": "recommendation",
        "target": "messy project",
        "artifact": None,
        "human_override": None,
        "duration_s": 0.1,
        "follow_up_skill": None,
        "shape": "legacy-stabilization",
        "confidence": "medium",
    }
    events = [
        {**base, "ts": "2026-05-17T00:00:00Z", "outcome": "unscored"},
        {**base, "ts": "2026-05-17T00:00:01Z", "outcome": "unscored"},
        {**base, "ts": "2026-05-17T00:00:02Z", "outcome": "overridden",
         "human_override": "wrong-shape: should have started with project-intake"},
    ]

    digest = skill_compact._render_digest(events, "2026-05-17T00:00:00Z", "2026-05-17T00:00:02Z")

    # n=3 events, 1 scored, and the unscored majority must not dilute
    # the overridden rate toward 0%.
    assert "| `legacy-stabilization` | 3 | 1 | 100% |" in digest
