from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


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
