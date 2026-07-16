from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "wp3_move_gate.py"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "wp3" / "move_gate"


def _load_gate():
    spec = importlib.util.spec_from_file_location("wp3_move_gate_under_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _copy_tree(source: Path, target: Path) -> None:
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if path.is_dir():
            (target / relative).mkdir(parents=True, exist_ok=True)
        else:
            (target / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target / relative)


def _make_repo(tmp_path: Path, variant: str) -> tuple[Path, str]:
    root = tmp_path / "host"
    root.mkdir()
    _copy_tree(FIXTURE_ROOT / "common", root)
    _copy_tree(FIXTURE_ROOT / "before", root)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "fixture@example.test")
    _git(root, "config", "user.name", "Fixture")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "before")
    base = _git(root, "rev-parse", "HEAD")

    (root / "foundation" / "runner.py").unlink()
    _copy_tree(FIXTURE_ROOT / variant, root)
    _git(root, "add", "-A")
    return root, base


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _diff_files(root: Path, base: str) -> list[str]:
    output = _git(root, "diff", "--name-only", "--diff-filter=ACMR", base, "--")
    return output.splitlines()


def _evidence(root: Path, base: str) -> dict:
    before = 'Path(__file__).resolve().parent / "assets" / "prompt.txt"'
    after = 'Path(__file__).resolve().parents[1] / "assets" / "prompt.txt"'
    document = root / ".claude" / "skills" / "move-path" / "SKILL.md"
    return {
        "schema_version": 1,
        "base_revision": base,
        "moves": [
            {
                "batch": "foundation",
                "from": "foundation/runner.py",
                "to": "foundation/scripts/runner.py",
            }
        ],
        "diff_files": _diff_files(root, base),
        "concept_renames": [
            {
                "old": "old-worker",
                "new": "new-worker",
                "retired_terms": ["legacy worker"],
                "scan_targets": ["foundation"],
                "prose_review": [
                    {
                        "file": "foundation/scripts/runner.py",
                        "reviewer": "fixture-reviewer",
                        "before_summary": "The legacy worker loaded its local prompt.",
                        "after_summary": "The new worker loads the portable shared prompt.",
                        "rationale": (
                            "The explanation now describes the renamed worker and the "
                            "asset location that remains true after relocation."
                        ),
                    }
                ],
            }
        ],
        "self_anchors": [
            {
                "batch": "foundation",
                "source_before": "foundation/runner.py",
                "source_after": "foundation/scripts/runner.py",
                "line_before": 5,
                "line_after": 5,
                "expression_before": before,
                "expression_after": after,
                "target_before": "foundation/assets/prompt.txt",
                "target_after": "foundation/assets/prompt.txt",
                "target_kind": "file",
                "classification": "tractable",
                "rewrite_note": "The extra directory requires one additional parent hop.",
            }
        ],
        "batch_smokes": [
            {
                "batch": "foundation",
                "imports": ["foundation/scripts/runner.py"],
                "assets": ["foundation/assets/prompt.txt"],
            }
        ],
        "disk_scan": {"files": _diff_files(root, base)},
        "non_rewrite_ack": {
            "document": ".claude/skills/move-path/SKILL.md",
            "sha256": _sha256(document),
            "reviewer": "fixture-reviewer",
            "acknowledged_classes": ["ambiguous prose", "unsupported import forms"],
            "acknowledged_omission": (
                "Self-anchored runtime expressions are not documented or rewritten "
                "by move-path."
            ),
        },
        "lesson_capture": {
            "log": ".claude/tasks/lessons.md",
            "fired_rules": [],
        },
    }


def _run(gate, tmp_path: Path, root: Path, evidence: dict):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return gate.run_gate(evidence_path=evidence_path, project_root=root)


def test_clean_move_emits_exact_two_band_and_smoke_evidence(tmp_path: Path) -> None:
    gate = _load_gate()
    root, base = _make_repo(tmp_path, "good")
    result = _run(gate, tmp_path, root, _evidence(root, base))

    assert result["ok"] is True
    assert result["findings"] == []
    two_band = result["evidence"]["two_band"][0]
    assert two_band["bands"] == {
        "avoid_term_hit": [],
        "superseded_co_occurrence": [],
    }
    assert "scan.py" in " ".join(two_band["command"])
    assert two_band["exit_code"] == 0
    assert "wrote 0 findings" in two_band["stdout"]
    assert result["evidence"]["batch_smokes"][0]["exit_code"] == 0
    assert result["evidence"]["disk_scan"]["files"] == evidence_files(root, base)


def evidence_files(root: Path, base: str) -> list[str]:
    return _diff_files(root, base)


def test_blocking_fixture_rejects_stale_prose_and_broken_anchor(
    tmp_path: Path,
) -> None:
    gate = _load_gate()
    root, base = _make_repo(tmp_path, "bad")
    evidence = _evidence(root, base)
    first = _run(gate, tmp_path, root, evidence)
    primary_rules = sorted(
        finding["rule"]
        for finding in first["findings"]
        if not finding["rule"].startswith("lesson_")
    )
    lessons = root / ".claude" / "tasks" / "lessons.md"
    lessons.parent.mkdir(parents=True, exist_ok=True)
    lessons.write_text(
        "\n".join(
            f"[wp3-move-gate:{rule}] Cause: fixture fired. How: repair before move."
            for rule in primary_rules
        )
        + "\n",
        encoding="utf-8",
    )
    evidence["diff_files"] = _diff_files(root, base)
    evidence["disk_scan"]["files"] = evidence["diff_files"]
    evidence["lesson_capture"]["fired_rules"] = primary_rules
    result = _run(gate, tmp_path, root, evidence)

    rules = {finding["rule"] for finding in result["findings"]}
    assert result["ok"] is False
    assert "retired_prose" in rules
    assert "anchor_target_mismatch" in rules
    assert "disk_target_missing" in rules
    assert not any(rule.startswith("lesson_") for rule in rules)


def test_identifier_only_cleanup_cannot_bypass_retired_prose_band(
    tmp_path: Path,
) -> None:
    gate = _load_gate()
    root, base = _make_repo(tmp_path, "bad")
    evidence = _evidence(root, base)
    evidence["self_anchors"][0]["expression_after"] = (
        'Path(__file__).resolve().parent / "assets" / "prompt.txt"'
    )
    result = _run(gate, tmp_path, root, evidence)

    rules = {finding["rule"] for finding in result["findings"]}
    assert "retired_prose" in rules
    assert result["evidence"]["two_band"][0]["bands"]["avoid_term_hit"]


def test_exists_only_asset_smoke_cannot_accept_directory_for_file(
    tmp_path: Path,
) -> None:
    gate = _load_gate()
    root, base = _make_repo(tmp_path, "good")
    runner = root / "foundation" / "scripts" / "runner.py"
    runner.write_text(
        runner.read_text(encoding="utf-8").replace(
            ' / "assets" / "prompt.txt"', ' / "assets"'
        ),
        encoding="utf-8",
    )
    evidence = _evidence(root, base)
    anchor = evidence["self_anchors"][0]
    anchor["expression_after"] = 'Path(__file__).resolve().parents[1] / "assets"'
    anchor["target_after"] = "foundation/assets"
    evidence["batch_smokes"][0]["assets"] = ["foundation/assets"]
    result = _run(gate, tmp_path, root, evidence)

    rules = {finding["rule"] for finding in result["findings"]}
    assert (root / "foundation" / "assets").exists()
    assert "disk_target_type" in rules
    assert result["ok"] is False


def test_unhandled_anchor_requires_review_and_uses_explicit_target_pin(
    tmp_path: Path,
) -> None:
    gate = _load_gate()
    root, base = _make_repo(tmp_path, "good")
    runner = root / "foundation" / "scripts" / "runner.py"
    runner.write_text(
        runner.read_text(encoding="utf-8").replace(
            'ASSET = Path(__file__).resolve().parents[1] / "assets" / "prompt.txt"',
            'PROMPT_NAME = "prompt.txt"\n'
            'ASSET = Path(__file__).resolve().parents[1] / "assets" / PROMPT_NAME',
        ),
        encoding="utf-8",
    )
    evidence = _evidence(root, base)
    anchor = evidence["self_anchors"][0]
    anchor.update(
        line_after=6,
        expression_after=(
            'Path(__file__).resolve().parents[1] / "assets" / PROMPT_NAME'
        ),
        classification="unhandled",
        reviewer_note=(
            "The computed final segment is pinned to the unchanged prompt file and "
            "the batch smoke imports the exported constant."
        ),
    )
    anchor.pop("rewrite_note")

    result = _run(gate, tmp_path, root, evidence)
    assert result["ok"] is True
    disk_anchor = result["evidence"]["disk_scan"]["anchors"][0]
    assert disk_anchor["classification"] == "unhandled"
    assert disk_anchor["pin_used"] is True
    assert disk_anchor["target"] == "foundation/assets/prompt.txt"


def test_anchor_inventory_detects_direct_non_assignment_expression(tmp_path: Path) -> None:
    gate = _load_gate()
    source = (
        "from pathlib import Path\n"
        "def load():\n"
        '    return (Path(__file__).resolve().parent / "prompt.txt").read_text()\n'
    )
    anchors = gate._anchors_from_text(source, tmp_path / "runner.py", tmp_path)
    assert len(anchors) == 1
    assert "Path(__file__)" in anchors[0].expression
    assert anchors[0].classification == "unhandled"


@pytest.mark.parametrize(
    ("mutation", "expected_rule"),
    [
        (lambda evidence: evidence.update(self_anchors=[]), "anchor_inventory"),
        (
            lambda evidence: evidence["non_rewrite_ack"].update(
                acknowledged_classes=["ambiguous prose"]
            ),
            "non_rewrite_ack",
        ),
        (
            lambda evidence: evidence["concept_renames"][0].update(
                prose_review=[]
            ),
            "prose_review",
        ),
    ],
)
def test_required_evidence_cannot_be_omitted(
    tmp_path: Path, mutation, expected_rule: str
) -> None:
    gate = _load_gate()
    root, base = _make_repo(tmp_path, "good")
    evidence = _evidence(root, base)
    mutation(evidence)

    result = _run(gate, tmp_path, root, evidence)
    assert expected_rule in {finding["rule"] for finding in result["findings"]}
    assert result["ok"] is False


def test_cli_blocks_and_writes_machine_readable_report(tmp_path: Path) -> None:
    root, base = _make_repo(tmp_path, "bad")
    evidence_path = tmp_path / "evidence.json"
    report_path = tmp_path / "report.json"
    evidence_path.write_text(
        json.dumps(_evidence(root, base), indent=2) + "\n", encoding="utf-8"
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-root",
            str(root),
            "--evidence",
            str(evidence_path),
            "--report",
            str(report_path),
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is False
    assert json.loads(completed.stdout)["ok"] is False
