from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".claude/skills/propose-boundary/scripts/propose.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("propose_boundary_under_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _seam(module, name: str, score: float):
    return module.CandidateSeam(
        cluster_id=name,
        members=[f"{name}_one", f"{name}_two"],
        rationale="fixture",
        proposed_public_api=[],
        callers_into_private_helpers=[],
        scores={"combined": score},
    )


def test_python_candidate_selection_includes_cutoff_ties_and_reports_omissions():
    module = _load_module()
    ranked = [
        _seam(module, "alpha", 0.9),
        _seam(module, "beta", 0.8),
        _seam(module, "gamma", 0.8),
        _seam(module, "delta", 0.4),
    ]

    selected, evidence = module._select_candidate_seams(ranked, 2)

    assert [seam.cluster_id for seam in selected] == ["alpha", "beta", "gamma"]
    assert evidence == {
        "requested": 2,
        "eligible": 4,
        "returned": 3,
        "cutoff_score": 0.8,
        "ties_included": True,
        "omitted_count": 1,
        "omitted": [{"cluster_id": "delta", "score": 0.4}],
    }


def _write_subsystem_map(root: Path, relative: str, source: str) -> Path:
    source_path = root / source
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("VALUE = 1\n", encoding="utf-8")
    map_path = root / relative / "billing.md"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(f"# Billing\n\n- `{source}`\n", encoding="utf-8")
    return map_path


def test_subsystem_target_prefers_canonical_map_without_warning(tmp_path, capsys):
    module = _load_module()
    expected = _write_subsystem_map(
        tmp_path, ".engineering/docs/subsystems", "src/billing.py"
    )

    target, kind, files = module._resolve_target("billing", tmp_path)

    assert target == expected
    assert kind == "subsystem"
    assert files == [tmp_path / "src/billing.py"]
    assert capsys.readouterr().err == ""


def test_subsystem_target_warns_when_using_bounded_legacy_fallback(tmp_path, capsys):
    module = _load_module()
    expected = _write_subsystem_map(
        tmp_path, ".claude/docs/subsystems", "src/billing.py"
    )

    target, kind, files = module._resolve_target("billing", tmp_path)

    assert target == expected
    assert kind == "subsystem"
    assert files == [tmp_path / "src/billing.py"]
    assert "WARNING: reading legacy subsystem map" in capsys.readouterr().err


def test_subsystem_target_rejects_canonical_legacy_collision(tmp_path):
    module = _load_module()
    _write_subsystem_map(tmp_path, ".engineering/docs/subsystems", "src/billing.py")
    _write_subsystem_map(tmp_path, ".claude/docs/subsystems", "src/billing.py")

    with pytest.raises(ValueError, match="both canonical and legacy"):
        module._resolve_target("billing", tmp_path)
