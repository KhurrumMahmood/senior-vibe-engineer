"""Fresh-library sentinel journeys for the accepted TypeScript mapper."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from tests.support.portability_journey import (
    JourneyObservation,
    NativeCheck,
    SyntaxFailure,
    ToolMissing,
    run_read_only_journey,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "map-subsystem-typescript" / "host"
ROUTERS = ("which-shape", "which-skill", "which-cleanup")


def _run(
    *argv: str, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        shell=False,
    )


def _fresh_handoff(tmp_path: Path, host: Path) -> tuple[Path, dict]:
    installed = host / ".agents" / "skills"
    for router in ROUTERS:
        shutil.copytree(REPO_ROOT / ".claude" / "skills" / router, installed / router)
    library = tmp_path / "on-demand-library"
    bootstrap = _run(
        sys.executable,
        "-I",
        "-S",
        str(installed / "which-skill" / "scripts" / "bootstrap_library.py"),
        "--project-root",
        str(host),
        "--source",
        str(REPO_ROOT),
        "--library-root",
        str(library),
        cwd=host,
    )
    assert bootstrap.returncode == 0, bootstrap.stdout + bootstrap.stderr
    routed = _run(
        sys.executable,
        "-I",
        "-S",
        str(installed / "which-skill" / "scripts" / "match.py"),
        "map the TypeScript subsystem architecture in src/features",
        "--project-root",
        str(host),
        "--library-root",
        str(library),
        "--json",
        cwd=host,
    )
    assert routed.returncode == 0, routed.stdout + routed.stderr
    payload = json.loads(routed.stdout)
    assert payload["recommendation"] == "map-subsystem"
    assert payload["handoff"]["available"] is True

    migration = library / "scripts" / "host_migrations.py"
    preview = _run(
        sys.executable,
        str(migration),
        "--project-root",
        str(host),
        "plan",
        cwd=host,
    )
    assert preview.returncode == 0, preview.stdout + preview.stderr
    assert json.loads(preview.stdout)["status"] == "ready"
    applied = _run(
        sys.executable,
        str(migration),
        "--project-root",
        str(host),
        "apply",
        cwd=host,
    )
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert json.loads(applied.stdout)["status"] == "applied"
    return library, payload["handoff"]


def test_bootstrapped_library_map_subsystem_completes_and_reports_partial(
    tmp_path: Path,
) -> None:
    for expected in ("complete", "partial"):
        case = tmp_path / expected
        host = case / "host"
        shutil.copytree(FIXTURE, host, ignore=shutil.ignore_patterns("node_modules"))
        installed = _run(
            "npm",
            "ci",
            "--ignore-scripts",
            cwd=host,
            env={**os.environ, "npm_config_cache": str(case / "empty-npm-cache")},
        )
        assert installed.returncode == 0, installed.stdout + installed.stderr
        if expected == "partial":
            (host / "src" / "features" / "unresolved.ts").write_text(
                "// @ts-ignore -- unresolved edge is the partial-map sentinel\n"
                'import { absent } from "@app/not-here";\n'
                "export const missing = absent;\n",
                encoding="utf-8",
            )
        library, handoff = _fresh_handoff(case, host)
        output = host / ".engineering" / "docs" / "subsystems" / f"{expected}.md"
        evidence = host / "reports" / "map" / expected / "typescript-map.json"

        def closure(context, host=host, output=output, evidence=evidence):
            tool = context.tool_roots[0] / "map_typescript.mjs"
            if not tool.is_file():
                raise ToolMissing("map_typescript.mjs")
            mapped = _run(
                "node",
                str(tool),
                "--target",
                "src/features",
                "--project-root",
                str(host),
                "--tsconfig",
                "tsconfig.json",
                "--output",
                str(output),
                "--evidence",
                str(evidence),
                cwd=host,
            )
            if mapped.returncode != 0:
                if "syntax errors" in mapped.stderr:
                    raise SyntaxFailure(mapped.stderr.strip())
                if "unavailable" in mapped.stderr:
                    raise ToolMissing(mapped.stderr.strip())
                raise AssertionError(mapped.stdout + mapped.stderr)
            payload = json.loads(evidence.read_text(encoding="utf-8"))
            return JourneyObservation(payload["status"], details=payload["counts"])

        result = run_read_only_journey(
            project_root=host,
            handoff=handoff,
            closure=closure,
            native_checks=(NativeCheck("npm-typecheck", ("npm", "run", "typecheck")),),
            artifact_paths=(output, evidence),
        )

        assert result.outcome == expected
        assert result.native_results[0].status == "passed"
        assert result.source_changes == ()
        assert {event.event for event in result.artifact_events} == {"created"}
        manifest = json.loads((host / ".engineering" / "manifest.json").read_text())
        assert manifest["version"] == 3
        assert manifest["applied_migrations"] == [
            "0001-subsystem-registry-home",
            "0002-subsystem-maps-home",
        ]
        assert all(Path(path).is_relative_to(library) for path in result.absolute_closure_paths)
        assert {path.name for path in (host / ".agents" / "skills").iterdir()} == set(
            ROUTERS
        )
