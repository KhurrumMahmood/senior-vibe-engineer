"""Reference-path repairs for find-semantic-duplication's Python branch."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "find-semantic-duplication"


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def test_python_reference_preserves_end_lines_and_separates_uncertain_triage(tmp_path: Path) -> None:
    host = tmp_path / "host"
    source = host / "src" / "summary.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "def summarize_by_sum(values: list[int]) -> dict[str, int]:\n"
        "    total = sum(values)\n"
        "    return {'total': total, 'count': len(values)}\n\n"
        "def summarize_by_loop(values: list[int]) -> dict[str, int]:\n"
        "    total = 0\n"
        "    for value in values:\n"
        "        total += value\n"
        "    return {'count': len(values), 'total': total}\n",
        encoding="utf-8",
    )
    before = source.read_bytes()
    installed = tmp_path / "installed"
    shutil.copytree(SKILL, installed)
    inventory = host / "inventory.jsonl"
    collect = _run(
        sys.executable, "-I", "-S", str(installed / "scripts" / "semantic_inventory.py"),
        "collect", "--target", "src", "--project-root", str(host), "--output", str(inventory), cwd=host,
    )
    assert collect.returncode == 0, collect.stdout + collect.stderr
    definitions = [json.loads(line) for line in inventory.read_text(encoding="utf-8").splitlines()]
    assert all(item["end_line"] >= item["line"] for item in definitions)

    summaries = host / "summaries.jsonl"
    summaries.write_text("\n".join(json.dumps({
        "type": "summary", "file": item["file"], "name": item["name"],
        "qualified_name": item["qualified_name"], "line": item["line"],
        "end_line": item["end_line"], "kind": item["kind"], "size": item["size"],
        "tier": item["tier"], "purpose": "Summarizes integer values.", "domain": "utility",
        "inputs": "values", "outputs": "dict", "side_effects": [], "key_operations": ["sum"],
    }) for item in definitions) + "\n", encoding="utf-8")
    prompts = host / "prompts"
    prompts_run = _run(
        sys.executable, "-I", "-S", str(installed / "scripts" / "semantic_inventory.py"),
        "prompts", str(summaries), "--output-dir", str(prompts), cwd=host,
    )
    assert prompts_run.returncode == 0, prompts_run.stdout + prompts_run.stderr
    prompt = json.loads((prompts / "prompt_utility.json").read_text(encoding="utf-8"))
    assert all(item["end_line"] >= item["line"] for item in prompt["items"])

    candidate_dir = host / "candidates"
    candidate_dir.mkdir()
    candidate_dir.joinpath("candidates_utility.json").write_text(json.dumps({
        "candidates": [
            {
                "id": "utility-C1", "level": "function", "similarity": 4,
                "a": definitions[0], "b": definitions[1], "rationale": "same outcome",
            },
            {
                "id": "retired-workflow-C2", "level": "workflow", "similarity": 5,
                "a": definitions[0], "b": definitions[1], "rationale": "unused legacy inventory",
            },
        ],
    }), encoding="utf-8")
    candidates = host / "candidates.json"
    collapse = _run(
        sys.executable, "-I", "-S", str(installed / "scripts" / "collapse_candidates.py"),
        "--prompts-dir", str(candidate_dir), "--output", str(candidates), cwd=host,
    )
    assert collapse.returncode == 0, collapse.stdout + collapse.stderr
    collapsed_payload = json.loads(candidates.read_text(encoding="utf-8"))
    assert collapsed_payload["counts"]["raw_candidates"] == 1
    members = collapsed_payload["findings"][0]["members"]
    assert all(member["end_line"] >= member["line"] for member in members)

    scout = host / "scout"
    scout.mkdir()
    base = {
        "finding_id": "SC-1", "level": "function", "members": members,
        "maintenance_risk_domain": "utility", "shared_core_description": "Summarizes values.",
        "divergence": {"accidental": [], "load_bearing": []}, "consolidation_shape": "share_utilities",
        "notes": "reference fixture", "tests_that_guard_this_area": [], "matrix_path": "capability_matrices/SC-1.md",
    }
    scout.joinpath("confirmed.json").write_text(json.dumps({**base, "investigation_status": "confirmed", "reason_code": None}), encoding="utf-8")
    scout.joinpath("uncertain.json").write_text(json.dumps({**base, "finding_id": "SC-2", "investigation_status": "uncertain", "reason_code": "dynamic_dispatch"}), encoding="utf-8")
    scout.joinpath("rejected.json").write_text(json.dumps({**base, "finding_id": "SC-3", "investigation_status": "false_positive", "reason_code": "caller_callee"}), encoding="utf-8")
    ranked = host / "ranked.json"
    rank = _run(
        sys.executable, "-I", "-S", str(installed / "scripts" / "rank.py"),
        "--confirmed", str(scout), "--output", str(ranked), cwd=host,
    )
    assert rank.returncode == 0, rank.stdout + rank.stderr
    ranked_payload = json.loads(ranked.read_text(encoding="utf-8"))
    assert [item["finding_id"] for item in ranked_payload["findings"]] == ["SC-1"]
    assert [item["finding_id"] for item in ranked_payload["uncertain"]] == ["SC-2"]
    assert [item["finding_id"] for item in ranked_payload["rejected"]] == ["SC-3"]

    triage = host / "triage.md"
    findings = host / "findings.json"
    report = _run(
        sys.executable, "-I", "-S", str(installed / "scripts" / "report.py"),
        "--input", str(ranked), "--output-md", str(triage), "--output-json", str(findings), "--scan-id", "reference", cwd=host,
    )
    assert report.returncode == 0, report.stdout + report.stderr
    rendered = triage.read_text(encoding="utf-8")
    assert "## Uncertain candidates" in rendered
    assert "SC-2" in rendered and "SC-3" in rendered
    assert [item["id"] for item in json.loads(findings.read_text(encoding="utf-8"))["findings"]] == ["SC-1"]
    assert source.read_bytes() == before
