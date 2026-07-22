"""Contract test for the fixed ML-009 read-only-lenses benchmark."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "scripts" / "benchmark_readonly_lenses.py"
LANES = ["audit-decisions", "find-complexity-hotspots", "find-standard-gaps"]


def test_fixed_contract_rejects_a_single_language(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(BENCHMARK),
            "--trials",
            "7",
            "--languages",
            "typescript",
            "--output",
            str(tmp_path / "result.json"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "fixed ML-009 contract requires exactly typescript, javascript" in result.stderr


def test_one_pair_per_language_has_compact_honest_results(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    workdir = tmp_path / "work"
    result = subprocess.run(
        [
            sys.executable,
            str(BENCHMARK),
            "--trials",
            "1",
            "--languages",
            "typescript,javascript",
            "--output",
            str(output),
            "--keep-workdir",
            str(workdir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert payload["correct"] is True
    assert payload["failure_count"] == 0
    assert payload["failures"] == []
    assert payload["configuration"] == {
        "trials": 1,
        "languages": ["typescript", "javascript"],
        "lane_order": LANES,
        "parallel_workers": 3,
    }
    assert payload["kept_workdir"] == str(workdir)

    for language, suffix, unsafe_line in (("typescript", "ts", 27), ("javascript", "js", 29)):
        expected = payload["expected_semantic_projection"][language]
        assert expected["audit-decisions"] == [
            {"id": "0001", "language": language, "path": f"src/benchmark.{suffix}"},
        ]
        assert expected["find-complexity-hotspots"][0]["branch_score"] == 18
        assert expected["find-complexity-hotspots"][0]["analyzer"] == "typescript-compiler-api"
        assert expected["find-standard-gaps"] == {
            "status": "scanned",
            "scanned_files": 1,
            "situation_sites": 2,
            "gaps": [{"file": f"src/benchmark.{suffix}", "line": unsafe_line}],
        }
        assert all(payload["setup"][language][key] for key in payload["setup"][language] if key.endswith("passed"))
        assert payload["setup"][language]["npm_ci_setup_ms"] >= 0

    assert {trial["language"] for trial in payload["trials"]} == {"typescript", "javascript"}
    for trial in payload["trials"]:
        assert trial["condition_order"] == ["serial", "parallel"]
        assert trial["semantic_equal"] is True
        assert trial["fixed_oracle"] is True
        assert trial["source_unchanged"] is True
        assert trial["native_checks_passed"] is True
        assert trial["actual_filesystem_read_bytes"] is None
        assert trial["model_tokens"] is None
        assert trial["interventions"] == 0
        assert trial["failure_count"] == 0
        assert trial["failures"] == []
        assert set(trial) == {
            "language", "trial", "condition_order", "serial", "parallel", "semantic_equal",
            "fixed_oracle", "source_unchanged", "native_checks_passed", "task_packet_utf8_bytes",
            "copied_closure_bytes", "eligible_input_overlap_proxy_bytes",
            "actual_filesystem_read_bytes", "model_tokens", "interventions", "failure_count", "failures",
        }
        assert set(trial["serial"]) == {"wall_ms", "per_lens_ms"}
        assert set(trial["parallel"]) == {"wall_ms", "per_lens_ms"}
        assert set(trial["serial"]["per_lens_ms"]) == set(LANES)
        assert set(trial["parallel"]["per_lens_ms"]) == set(LANES)
        packets = trial["task_packet_utf8_bytes"]
        assert packets["serial_total"] == packets["parallel_total"] == sum(packets["per_lens"].values())
        assert trial["copied_closure_bytes"]["total"] == sum(trial["copied_closure_bytes"]["per_lens"].values())
        assert trial["eligible_input_overlap_proxy_bytes"] > 0

    for language in ("typescript", "javascript"):
        gate = payload["summary"]["by_language"][language]
        assert gate["trial_count"] == 1
        assert gate["gate_evaluable"] is False
        assert gate["materiality_gate_passed"] is False
    assert payload["summary"]["materiality_gate_passed"] is False
    assert payload["materiality_gate_passed"] is False

    library = workdir / "on_demand_library"
    assert library.is_dir()
    for language in ("typescript", "javascript"):
        for condition in ("serial", "parallel"):
            host = workdir / "trials" / language / "trial-1" / condition
            assert host.is_dir()
            assert not (host / ".claude").exists()
            assert not (host / ".agents").exists()
            assert library not in host.parents
