from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAMILY = ROOT / ".claude" / "skill-families" / "code-health-readonly"
MATCHER = ROOT / ".claude" / "skills" / "which-skill" / "scripts" / "match.py"
LAUNCHER_SPEC = importlib.util.spec_from_file_location(
    "code_health_family_launcher", FAMILY / "scripts" / "run.py"
)
assert LAUNCHER_SPEC and LAUNCHER_SPEC.loader
LAUNCHER = importlib.util.module_from_spec(LAUNCHER_SPEC)
LAUNCHER_SPEC.loader.exec_module(LAUNCHER)
VALID_STANDARDS = {
    "ideas": [
        {
            "id": "checked-json-parse",
            "contract": {
                "detector": {
                    "kind": "ast",
                    "call_matches": "^JSON\\.parse$",
                    "enclosed_by": "try",
                    "paths": ["src/**/*"],
                }
            },
        }
    ]
}


def _route(
    tmp_path: Path,
    *,
    standards: Path | None = None,
    inactive_skill: str | None = None,
    task: str = "Run a broad TypeScript code health audit across src without changing production code",
) -> dict:
    host = tmp_path / "host"
    (host / "ai-docs" / "decisions").mkdir(parents=True)
    (host / "src").mkdir()
    if inactive_skill:
        manifest = host / ".engineering" / "manifest.json"
        manifest.parent.mkdir()
        manifest.write_text(
            json.dumps(
                {
                    "skills": {
                        "default": "active",
                        "inactive": {inactive_skill: "disabled by host"},
                    }
                }
            )
            + "\n",
            encoding="utf-8",
        )
    command = [
        sys.executable,
        "-I",
        "-S",
        str(MATCHER),
        task,
        "--project-root",
        str(host),
        "--library-root",
        str(ROOT),
        "--json",
    ]
    if standards is not None:
        command.extend(["--standards", str(standards)])
    result = subprocess.run(command, cwd=host, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_router_selects_bounded_health_family_without_ambient_members(tmp_path: Path) -> None:
    payload = _route(tmp_path)

    assert payload["recommendation"] == "find-complexity-hotspots"
    family = payload["coverage_family"]
    assert family["name"] == "code-health-readonly"
    assert family["available"] is True
    assert family["execution"] == {
        "max_parallel_read_only": 3,
        "mutation": "forbidden",
        "synthesis_owner": "family-launcher",
    }
    assert family["coverage_set"] == [
        "audit-decisions",
        "find-complexity-hotspots",
        "find-standard-gaps",
    ]
    assert family["runnable"] == ["audit-decisions", "find-complexity-hotspots"]
    assert family["skips"] == [
        {
            "skill": "find-standard-gaps",
            "reason": "host_standards_path_not_supplied",
        }
    ]
    assert family["dependencies"]["decision_registry"]["available"] is True
    assert family["dependencies"]["host_standards"]["available"] is False
    assert family["paths"]["root"] == str(FAMILY)
    assert family["paths"]["core"] == str(FAMILY / "CORE.md")
    assert family["paths"]["launcher"] == str(FAMILY / "scripts" / "run.py")
    assert [row["guide"] for row in family["members"]] == [
        str(FAMILY / "members" / "audit-decisions.md"),
        str(FAMILY / "members" / "find-complexity-hotspots.md"),
        str(FAMILY / "members" / "find-standard-gaps.md"),
    ]
    assert all(
        row["on_demand_closure"]["capabilities"]["available"] is True
        for row in family["members"]
    )
    assert "optional_install" not in family
    assert all(".agents/skills" not in path for path in family["paths"].values())
    assert not (tmp_path / "host" / ".agents").exists()


def test_router_marks_all_family_members_runnable_with_declared_inputs(tmp_path: Path) -> None:
    standards = tmp_path / "host" / "standards.json"
    standards.parent.mkdir(parents=True)
    standards.write_text(json.dumps(VALID_STANDARDS) + "\n", encoding="utf-8")

    payload = _route(tmp_path, standards=standards)

    family = payload["coverage_family"]
    assert family["runnable"] == family["coverage_set"]
    assert family["skips"] == []
    assert family["dependencies"]["host_standards"] == {
        "available": True,
        "path": str(standards.resolve()),
    }


def test_router_skips_structurally_unusable_host_standards(tmp_path: Path) -> None:
    standards = tmp_path / "host" / "standards.json"
    standards.parent.mkdir(parents=True)
    standards.write_text('{"ideas": []}\n', encoding="utf-8")

    family = _route(tmp_path, standards=standards)["coverage_family"]

    assert "find-standard-gaps" not in family["runnable"]
    assert {"skill": "find-standard-gaps", "reason": "host_standards_invalid"} in family["skips"]
    assert family["dependencies"]["host_standards"] == {
        "available": False,
        "path": str(standards.resolve()),
        "reason": "host_standards_invalid",
    }


def test_router_skips_nonempty_standards_without_executable_detector(tmp_path: Path) -> None:
    standards = tmp_path / "host" / "standards.json"
    standards.parent.mkdir(parents=True)
    standards.write_text('{"ideas": [{}]}\n', encoding="utf-8")

    family = _route(tmp_path, standards=standards)["coverage_family"]

    assert "find-standard-gaps" not in family["runnable"]
    assert {"skill": "find-standard-gaps", "reason": "host_standards_invalid"} in family["skips"]


def test_router_skips_malformed_executable_detector(tmp_path: Path) -> None:
    standards = tmp_path / "host" / "standards.json"
    standards.parent.mkdir(parents=True)
    standards.write_text(
        json.dumps(
            {
                "ideas": [
                    {
                        "contract": {
                            "detector": {
                                "kind": "ast",
                                "call_matches": "(",
                                "enclosed_by": "try",
                            }
                        }
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    family = _route(tmp_path, standards=standards)["coverage_family"]

    assert "find-standard-gaps" not in family["runnable"]
    assert {"skill": "find-standard-gaps", "reason": "host_standards_invalid"} in family["skips"]


def test_all_benchmark_user_prompts_activate_the_family(tmp_path: Path) -> None:
    prompts = (
        "Run a read-only TypeScript code-health audit over src and give me one actionable result.",
        "Before release, inspect src for broad TypeScript engineering-health problems without editing code.",
        "Audit overall TypeScript code quality in src; keep the run read-only and preserve incomplete evidence.",
        "Give me a broad, read-only health check of this TypeScript repository's src directory.",
        "Check TypeScript src with complementary code-health lenses, make no production changes, and synthesize the evidence.",
    )

    for task in prompts:
        assert _route(tmp_path / str(len(task)), task=task)["coverage_family"]["name"] == "code-health-readonly"


def test_mixed_javascript_typescript_request_does_not_select_single_language_family(
    tmp_path: Path,
) -> None:
    host = tmp_path / "host"
    host.mkdir()
    result = subprocess.run(
        [
            sys.executable, "-I", "-S", str(MATCHER),
            "Run a broad read-only code health audit across src",
            "--project-root", str(host),
            "--library-root", str(ROOT),
            "--language", "javascript",
            "--language", "typescript",
            "--json",
        ],
        cwd=host,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "coverage_family" not in json.loads(result.stdout)


def test_narrow_requests_keep_single_skill_routing(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(MATCHER),
            "use find-complexity-hotspots on this TypeScript src directory",
            "--project-root",
            str(host),
            "--library-root",
            str(ROOT),
            "--json",
        ],
        cwd=host,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["recommendation"] == "find-complexity-hotspots"
    assert "coverage_family" not in payload


def test_host_inactive_family_member_is_an_explicit_skip(tmp_path: Path) -> None:
    payload = _route(tmp_path, inactive_skill="audit-decisions")

    family = payload["coverage_family"]
    assert "audit-decisions" not in family["runnable"]
    assert {(row["skill"], row["reason"]) for row in family["skips"]} >= {
        ("audit-decisions", "disabled by host"),
        ("find-standard-gaps", "host_standards_path_not_supplied"),
    }


def test_host_inactive_family_primary_suppresses_family_routing(tmp_path: Path) -> None:
    payload = _route(tmp_path, inactive_skill="find-complexity-hotspots")

    assert "coverage_family" not in payload


def test_mutating_health_request_does_not_parallelize_a_family(tmp_path: Path) -> None:
    payload = _route(
        tmp_path,
        task="Fix and refactor every problem from a broad TypeScript code health audit",
    )

    assert "coverage_family" not in payload


def test_compressed_contract_reduces_context_without_dropping_binding_guards() -> None:
    full = sum(
        (ROOT / ".claude" / "skills" / name / "SKILL.md").stat().st_size
        for name in (
            "audit-decisions",
            "find-complexity-hotspots",
            "find-standard-gaps",
        )
    )
    compressed_paths = [FAMILY / "CORE.md", *sorted((FAMILY / "members").glob("*.md"))]
    compressed = sum(path.stat().st_size for path in compressed_paths)
    text = "\n".join(path.read_text(encoding="utf-8") for path in compressed_paths)

    assert compressed <= full * 0.70
    for guard in (
        "read-only",
        "partial",
        "language_unsupported",
        "no_files_matched",
        "generated",
        "symlink",
        "source mutation",
        "final artifact",
    ):
        assert guard in text


def test_family_manifest_matches_router_and_member_contracts() -> None:
    manifest = json.loads((FAMILY / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["name"] == "code-health-readonly"
    assert manifest["primary"] == "find-complexity-hotspots"
    assert manifest["languages"] == ["typescript", "javascript"]
    assert manifest["max_parallel_read_only"] == 3
    assert [row["skill"] for row in manifest["members"]] == [
        "audit-decisions",
        "find-complexity-hotspots",
        "find-standard-gaps",
    ]
    assert all((FAMILY / row["guide"]).is_file() for row in manifest["members"])


def test_synthesis_does_not_collapse_distinct_evidence_at_one_location() -> None:
    findings, clean, incomplete = LAUNCHER._synthesize(
        [
            {
                "skill": "audit-decisions",
                "status": "complete",
                "semantic_projection": {
                    "drift": [],
                    "references": [],
                    "link_check": {"drift": ["decision 0001 missing docs", "decision 0002 missing docs"]},
                    "registry_audit": {"drift": []},
                },
            }
        ]
    )

    assert [row["evidence"] for row in findings] == [
        "decision 0001 missing docs",
        "decision 0002 missing docs",
    ]
    assert clean == []
    assert incomplete == []


def test_family_launcher_reaches_real_final_artifacts_without_source_mutation(
    tmp_path: Path,
) -> None:
    fixture = ROOT / "tests" / "fixtures" / "audit-decisions-typescript" / "host"
    host = tmp_path / "real-host"
    shutil.copytree(fixture, host)
    install = subprocess.run(
        ["npm", "ci", "--offline", "--ignore-scripts"],
        cwd=host,
        capture_output=True,
        text=True,
        check=False,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    branches = "\n".join(f"  if (value > {number}) value -= 1;" for number in range(18))
    source = host / "src" / "health.ts"
    source.write_text(
        "// decision:0001\n"
        "export function hotspot(value: number): number {\n"
        f"{branches}\n"
        "  return value;\n"
        "}\n"
        "export function unsafe(payload: string): unknown {\n"
        "  return JSON.parse(payload);\n"
        "}\n",
        encoding="utf-8",
    )
    standards = host / "standards.json"
    standards.write_text(
        json.dumps(
            {
                "ideas": [
                    {
                        "id": "checked-json-parse",
                        "label": "JSON parsing is protected",
                        "activation": {"baseline": True},
                        "contract": {
                            "detector": {
                                "kind": "ast",
                                "call_matches": "^JSON\\.parse$",
                                "enclosed_by": "try",
                                "paths": ["src/**/*"],
                            }
                        },
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    before = source.read_bytes()

    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(FAMILY / "scripts" / "run.py"),
            "--project-root",
            str(host),
            "--library-root",
            str(ROOT),
            "--target",
            "src",
            "--language",
            "typescript",
            "--standards",
            str(standards),
            "--mode",
            "parallel",
            "--run-id",
            "integration",
            "--output-dir",
            "reports/code-health/integration",
        ],
        cwd=host,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    artifact = host / "reports" / "code-health" / "integration" / "family-result.json"
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert [(row["skill"], row["status"]) for row in payload["lanes"]] == [
        ("audit-decisions", "complete"),
        ("find-complexity-hotspots", "complete"),
        ("find-standard-gaps", "complete"),
    ]
    assert {row["kind"] for row in payload["synthesis"]["findings"]} >= {
        "decision-drift",
        "complexity-hotspot",
        "standard-gap",
    }
    assert sum(
        row["kind"] == "decision-drift" for row in payload["synthesis"]["findings"]
    ) == 1
    assert payload["synthesis"]["incomplete_lanes"] == []
    assert payload["source_mutated"] is False
    assert payload["failures"] == []
    assert source.read_bytes() == before
    assert (artifact.parent / "summary.md").is_file()

    standards.write_text('{"ideas": [invalid]}\n', encoding="utf-8")
    failed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(FAMILY / "scripts" / "run.py"),
            "--project-root",
            str(host),
            "--library-root",
            str(ROOT),
            "--target",
            "src",
            "--language",
            "typescript",
            "--standards",
            str(standards),
            "--mode",
            "parallel",
            "--run-id",
            "invalid-standards",
            "--output-dir",
            "reports/code-health/invalid-standards",
        ],
        cwd=host,
        capture_output=True,
        text=True,
        check=False,
    )

    assert failed.returncode == 0
    failed_payload = json.loads(
        (host / "reports" / "code-health" / "invalid-standards" / "family-result.json").read_text(
            encoding="utf-8"
        )
    )
    assert [(row["skill"], row["status"]) for row in failed_payload["lanes"]] == [
        ("audit-decisions", "complete"),
        ("find-complexity-hotspots", "complete"),
        ("find-standard-gaps", "skipped"),
    ]
    assert failed_payload["lanes"][-1]["reason"] == "host_standards_invalid"
    assert failed_payload["synthesis"]["incomplete_lanes"] == ["find-standard-gaps"]
    assert "find-standard-gaps" not in failed_payload["synthesis"]["clean_lanes"]
    assert failed_payload["source_mutated"] is False
    assert source.read_bytes() == before


def test_family_launcher_marks_excluded_only_target_incomplete(tmp_path: Path) -> None:
    host = tmp_path / "host"
    target = host / "src"
    target.mkdir(parents=True)
    (target / "types.d.ts").write_text("export interface Row {}\n", encoding="utf-8")
    excluded_dir = target / "staticfiles"
    excluded_dir.mkdir()
    (excluded_dir / "ignored.ts").write_text("export const ignored = true;\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable, "-I", "-S", str(FAMILY / "scripts" / "run.py"),
            "--project-root", str(host),
            "--library-root", str(ROOT),
            "--target", "src",
            "--language", "typescript",
            "--mode", "parallel",
            "--run-id", "excluded-only",
            "--output-dir", "reports/code-health/excluded-only",
        ],
        cwd=host,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    artifact = host / "reports" / "code-health" / "excluded-only" / "family-result.json"
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    complexity = next(row for row in payload["lanes"] if row["skill"] == "find-complexity-hotspots")
    assert complexity == {
        "skill": "find-complexity-hotspots",
        "status": "skipped",
        "reason": "no_files_matched",
    }
    assert "find-complexity-hotspots" in payload["synthesis"]["incomplete_lanes"]
    assert "find-complexity-hotspots" not in payload["synthesis"]["clean_lanes"]
    assert (artifact.parent / "summary.md").is_file()


def test_family_launcher_honors_host_inactive_member(tmp_path: Path) -> None:
    host = tmp_path / "host"
    target = host / "src"
    target.mkdir(parents=True)
    (target / "types.d.ts").write_text("export interface Row {}\n", encoding="utf-8")
    (host / "ai-docs" / "decisions").mkdir(parents=True)
    manifest = host / ".engineering" / "manifest.json"
    manifest.parent.mkdir()
    manifest.write_text(
        json.dumps(
            {
                "skills": {
                    "default": "active",
                    "inactive": {"audit-decisions": "disabled by host"},
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable, "-I", "-S", str(FAMILY / "scripts" / "run.py"),
            "--project-root", str(host),
            "--library-root", str(ROOT),
            "--target", "src",
            "--language", "typescript",
            "--run-id", "inactive-member",
            "--output-dir", "reports/code-health/inactive-member",
        ],
        cwd=host,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(
        (host / "reports" / "code-health" / "inactive-member" / "family-result.json").read_text(
            encoding="utf-8"
        )
    )
    audit = next(row for row in payload["lanes"] if row["skill"] == "audit-decisions")
    assert audit == {"skill": "audit-decisions", "status": "skipped", "reason": "disabled by host"}
    assert "audit-decisions" in payload["synthesis"]["incomplete_lanes"]
    assert not list((host / "reports").glob("audit-decisions/**/raw-drift.json"))


def test_family_launcher_skips_explicit_missing_standards_path(tmp_path: Path) -> None:
    host = tmp_path / "host"
    target = host / "src"
    target.mkdir(parents=True)
    (target / "types.d.ts").write_text("export interface Row {}\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable, "-I", "-S", str(FAMILY / "scripts" / "run.py"),
            "--project-root", str(host),
            "--library-root", str(ROOT),
            "--target", "src",
            "--language", "typescript",
            "--standards", str(host / "missing-standards.json"),
            "--run-id", "missing-standards",
            "--output-dir", "reports/code-health/missing-standards",
        ],
        cwd=host,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(
        (host / "reports" / "code-health" / "missing-standards" / "family-result.json").read_text(
            encoding="utf-8"
        )
    )
    standards = next(row for row in payload["lanes"] if row["skill"] == "find-standard-gaps")
    assert standards == {
        "skill": "find-standard-gaps",
        "status": "skipped",
        "reason": "host_standards_path_missing",
    }
