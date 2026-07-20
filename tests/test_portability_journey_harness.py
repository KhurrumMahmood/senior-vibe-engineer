"""Contract tests for the bounded read-only portability journey harness."""
from __future__ import annotations

import sys
import shutil
from pathlib import Path

import pytest

from tests.support.portability_journey import (
    JourneyObservation,
    NativeCheck,
    SyntaxFailure,
    ToolMissing,
    run_read_only_journey,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _handoff(library: Path) -> dict:
    skill = library / ".claude" / "skills" / "demo"
    return {
        "mode": "on_demand_library",
        "available": True,
        "library_root": str(library),
        "skills": ["demo"],
        "guides": [
            {
                "skill": "demo",
                "skill_root": str(skill),
                "guide": str(skill / "SKILL.md"),
                "bundled_tooling": str(skill / "scripts"),
            }
        ],
        "shared_tooling": str(library / "scripts"),
        "source_inventory_tool": str(library / "scripts" / "source_inventory.py"),
    }


@pytest.fixture
def journey_roots(tmp_path: Path) -> tuple[Path, Path, dict]:
    host = tmp_path / "host"
    library = tmp_path / "library"
    _write(host / "src" / "app.ts", "export const value = 1;\n")
    _write(host / "tests" / "test_app.py", "def test_value(): pass\n")
    _write(library / ".claude" / "skills" / "demo" / "SKILL.md", "# Demo\n")
    _write(
        library / ".claude" / "skills" / "demo" / "scripts" / "inspect.py",
        "print('inspect')\n",
    )
    inventory_tool = library / "scripts" / "source_inventory.py"
    inventory_tool.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        Path(__file__).resolve().parents[1] / "scripts" / "source_inventory.py",
        inventory_tool,
    )
    return host, library, _handoff(library)


@pytest.mark.parametrize("outcome", ["complete", "partial", "unsupported"])
def test_records_declared_observation_outcomes_and_evidence(
    journey_roots: tuple[Path, Path, dict], outcome: str
) -> None:
    host, _, handoff = journey_roots
    existing = host / "reports" / "existing.json"
    created = host / "reports" / "created.json"
    _write(existing, '{"state":"before"}\n')

    def closure(context):
        assert context.project_root == host.resolve()
        assert context.guides[0].name == "SKILL.md"
        _write(existing, '{"state":"after"}\n')
        _write(created, '{"status":"recorded"}\n')
        return JourneyObservation(outcome, "synthetic result", {"rows": 2})

    result = run_read_only_journey(
        project_root=host,
        handoff=handoff,
        closure=closure,
        native_checks=(
            NativeCheck(
                "python-ok",
                (sys.executable, "-c", "print('native ok')"),
            ),
        ),
        artifact_paths=(existing, created),
    )

    assert result.outcome == outcome
    assert result.observation == JourneyObservation(
        outcome, "synthetic result", {"rows": 2}
    )
    assert set(result.guide_hashes) == {".claude/skills/demo/SKILL.md"}
    assert set(result.tool_hashes) == {
        ".claude/skills/demo/scripts/inspect.py",
        "scripts/source_inventory.py",
    }
    assert set(result.source_digests["before"]) == {
        "src/app.ts",
        "tests/test_app.py",
    }
    assert result.source_changes == ()
    assert result.native_results[0].status == "passed"
    assert result.native_results[0].stdout == "native ok\n"
    assert result.artifact_hashes["before"]["reports/created.json"] is None
    assert {(event.path, event.event) for event in result.artifact_events} == {
        ("reports/existing.json", "modified"),
        ("reports/created.json", "created"),
    }


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (ToolMissing("node"), "tool-missing"),
        (SyntaxFailure("src/app.ts: invalid token"), "syntax-error"),
    ],
)
def test_typed_closure_failures_have_exact_outcomes(
    journey_roots: tuple[Path, Path, dict], failure: Exception, expected: str
) -> None:
    host, _, handoff = journey_roots

    def closure(_context):
        raise failure

    result = run_read_only_journey(
        project_root=host,
        handoff=handoff,
        closure=closure,
    )

    assert result.outcome == expected
    assert result.observation is None
    assert result.failure == str(failure)
    assert result.native_results == ()


def test_missing_native_tool_is_typed_without_installing(
    journey_roots: tuple[Path, Path, dict],
) -> None:
    host, _, handoff = journey_roots
    routers = host / ".agents" / "skills"
    _write(routers / "which-skill" / "SKILL.md", "# Router\n")

    result = run_read_only_journey(
        project_root=host,
        handoff=handoff,
        closure=lambda _context: JourneyObservation("complete"),
        native_checks=(
            NativeCheck("absent", ("/definitely/missing/portability-tool", "--check")),
        ),
    )

    assert result.outcome == "tool-missing"
    assert result.native_results[0].status == "tool-missing"
    assert [path.name for path in routers.iterdir()] == ["which-skill"]


def test_native_check_failure_is_distinct_and_records_literal_argv(
    journey_roots: tuple[Path, Path, dict],
) -> None:
    host, _, handoff = journey_roots
    argv = (sys.executable, "-c", "import sys; print('bad'); sys.exit(7)")

    result = run_read_only_journey(
        project_root=host,
        handoff=handoff,
        closure=lambda _context: JourneyObservation("complete"),
        native_checks=(NativeCheck("python-fail", argv),),
    )

    assert result.outcome == "native-check-failure"
    assert result.native_results[0].argv == argv
    assert result.native_results[0].returncode == 7
    assert result.native_results[0].status == "failed"


def test_any_inventoried_source_mutation_overrides_other_outcomes(
    journey_roots: tuple[Path, Path, dict],
) -> None:
    host, _, handoff = journey_roots

    def closure(_context):
        _write(host / "src" / "app.ts", "export const value = 2;\n")
        raise ToolMissing("node")

    result = run_read_only_journey(
        project_root=host,
        handoff=handoff,
        closure=closure,
    )

    assert result.outcome == "unexpected-source-mutation"
    assert result.failure == "required tool is unavailable: node"
    assert [(change.path, change.stage, change.kind) for change in result.source_changes] == [
        ("src/app.ts", "after_closure", "modified")
    ]


@pytest.mark.parametrize("field", ["guide", "bundled_tooling", "shared_tooling"])
def test_rejects_guide_or_tool_paths_outside_the_on_demand_library(
    journey_roots: tuple[Path, Path, dict], field: str
) -> None:
    host, _, handoff = journey_roots
    outside = host.parent / "outside"
    _write(outside / "SKILL.md", "# Escaped\n")
    _write(outside / "scripts" / "tool.py", "print('escaped')\n")
    if field == "guide":
        handoff["guides"][0][field] = str(outside / "SKILL.md")
    elif field == "bundled_tooling":
        handoff["guides"][0][field] = str(outside / "scripts")
    else:
        handoff[field] = str(outside / "scripts")

    with pytest.raises(ValueError, match="must stay within library root"):
        run_read_only_journey(
            project_root=host,
            handoff=handoff,
            closure=lambda _context: JourneyObservation("complete"),
        )


def test_rejects_a_guide_order_that_does_not_match_the_handoff_closure(
    journey_roots: tuple[Path, Path, dict],
) -> None:
    host, _, handoff = journey_roots
    handoff["skills"] = ["other"]

    with pytest.raises(ValueError, match="exact ordered skill closure"):
        run_read_only_journey(
            project_root=host,
            handoff=handoff,
            closure=lambda _context: JourneyObservation("complete"),
        )
