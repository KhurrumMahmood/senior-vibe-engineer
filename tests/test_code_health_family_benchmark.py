from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "benchmark_code_health_family.py"
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("benchmark_code_health_family", SCRIPT)
assert SPEC and SPEC.loader
BENCHMARK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCHMARK)


def test_compressed_prompts_materially_reduce_controlled_context() -> None:
    task = BENCHMARK.TRIAL_TASKS[0]
    full_lane = sum(
        len(
            BENCHMARK._lane_prompt(
                task=task,
                condition=BENCHMARK.CONDITIONS[0],
                lane=lane,
                command=["python", f"{lane}.py"],
                artifact=Path(f"reports/{lane}.json"),
            ).encode("utf-8")
        )
        for lane in BENCHMARK.LANES
    )
    compressed_lane = sum(
        len(
            BENCHMARK._lane_prompt(
                task=task,
                condition=BENCHMARK.CONDITIONS[1],
                lane=lane,
                command=["python", f"{lane}.py"],
                artifact=Path(f"reports/{lane}.json"),
            ).encode("utf-8")
        )
        for lane in BENCHMARK.LANES
    )

    assert compressed_lane <= full_lane * 0.70


def test_structured_codex_events_preserve_usage_and_command_exits(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    events.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": "python lane.py",
                            "exit_code": 1,
                            "status": "completed",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {
                            "input_tokens": 100,
                            "cached_input_tokens": 40,
                            "output_tokens": 20,
                            "reasoning_output_tokens": 5,
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    usage, commands = BENCHMARK._parse_events(events)

    assert usage == {
        "input_tokens": 100,
        "cached_input_tokens": 40,
        "output_tokens": 20,
        "reasoning_output_tokens": 5,
    }
    assert commands == [
        {
            "command": "python lane.py",
            "exit_code": 1,
            "status": "completed",
        }
    ]


def test_hidden_synthesis_check_rejects_clean_claim_for_incomplete_lane() -> None:
    expected = {
        "findings": [("complexity-hotspot", "src/app.ts")],
        "incomplete_lanes": ["find-standard-gaps"],
        "clean_lanes": ["audit-decisions"],
    }
    final = {
        "findings": [
            {
                "kind": "complexity-hotspot",
                "path": "src/app.ts",
                "line_or_symbol": "work",
            }
        ],
        "incomplete_lanes": [],
        "clean_lanes": ["audit-decisions", "find-standard-gaps"],
    }

    passed, failures = BENCHMARK._score_synthesis(final, expected)

    assert passed is False
    assert "incomplete lane mismatch" in failures
    assert "incomplete lane presented as clean" in failures


def test_budget_reserves_parallel_groups_atomically() -> None:
    budget = BENCHMARK.Budget(3)
    assert budget.reserve(3) is True
    assert budget.reserve() is False
    assert budget.used == 3


def test_resume_rejects_host_bytes_changed_since_frozen_baseline(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    source = host / "source.ts"
    source.write_text("export const value = 1;\n", encoding="utf-8")
    initial_digest = BENCHMARK._tree_digest(host)
    source.write_text("export const value = 2;\n", encoding="utf-8")

    try:
        BENCHMARK._condition(
            task=BENCHMARK.TRIAL_TASKS[0],
            condition=BENCHMARK.CONDITIONS[0],
            host=host,
            checkpoint=tmp_path / "checkpoint",
            standards=host / "standards.json",
            initial_digest=initial_digest,
            label="mutated-resume",
            budget=BENCHMARK.Budget(0),
        )
    except RuntimeError as exc:
        assert "frozen initial_digest" in str(exc)
    else:
        raise AssertionError("changed host bytes must stop a resumed condition")
