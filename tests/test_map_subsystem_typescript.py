"""End-to-end TypeScript/TSX map-subsystem outcome and closure proof."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "map-subsystem"
SCRIPT = SKILL / "scripts" / "map_typescript.mjs"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "map-subsystem-typescript"


def _run(
    *args: str,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE / "host", host)
    install = _run("npm", "ci", "--offline", "--ignore-scripts", cwd=host)
    assert install.returncode == 0, install.stdout + install.stderr
    native = _run("npm", "run", "typecheck", cwd=host)
    assert native.returncode == 0, native.stdout + native.stderr
    return host


def _map(
    skill: Path,
    host: Path,
    target: str = "src/features",
    *,
    name: str = "features",
    tsconfig: str = "tsconfig.json",
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    output = host / ".claude" / "docs" / "subsystems" / f"{name}.md"
    evidence = host / "reports" / "map" / name / "typescript-map.json"
    result = _run(
        "node",
        str(skill / "scripts" / "map_typescript.mjs"),
        "--target",
        target,
        "--project-root",
        str(host),
        "--tsconfig",
        tsconfig,
        "--output",
        str(output),
        "--evidence",
        str(evidence),
        "--effectiveness-log",
        str(host / "reports" / "_meta" / "effectiveness.jsonl"),
        cwd=host,
    )
    return result, output, evidence


def _map_with_paths(
    host: Path,
    *,
    output: Path,
    evidence: Path,
) -> subprocess.CompletedProcess[str]:
    return _run(
        "node",
        str(SCRIPT),
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


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _documented_command(skill: Path, name: str) -> str:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(
        rf"<!-- installed-command:{name}:start -->\n```bash\n(.*?)\n```\n"
        rf"<!-- installed-command:{name}:end -->",
        text,
        re.DOTALL,
    )
    assert match is not None, name
    return match.group(1)


def test_typescript_map_reaches_final_doc_with_resolved_edges_and_honest_fields(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    result, output, evidence = _map(SKILL, host)

    assert result.returncode == 0, result.stdout + result.stderr
    assert output.is_file()
    assert evidence.is_file()
    payload = _load(evidence)

    assert payload["status"] == "complete"
    assert payload["language"] == "typescript"
    assert payload["analyzer"] == "typescript-compiler-api"
    assert payload["counts"] == {
        "source_files": 3,
        "exported_symbols": 5,
        "outbound_imports": 2,
        "inbound_imports": 2,
        "unresolved_imports": 0,
        "workflow_entries": 1,
    }
    assert {item["name"] for item in payload["exported_surface"]} == {
        "FeatureWidget",
        "WidgetProps",
        "formatWidgetLabel",
        "FeaturePanel",
    }
    assert any(
        edge["specifier"] == "@app/shared/math"
        and edge["resolved_file"] == "src/shared/math.ts"
        and edge["resolution"] == "resolved"
        for edge in payload["outbound_imports"]
    )
    assert any(
        edge["source_file"] == "src/feature-consumer.ts"
        and edge["specifier"] == "./features/widget"
        and edge["resolved_file"] == "src/features/widget.tsx"
        for edge in payload["inbound_imports"]
    )
    assert any(
        edge["source_file"] == "src/app.ts"
        and edge["specifier"] == "@app/features"
        and edge["resolved_file"] == "src/features/index.ts"
        and edge["barrel_boundary"] is True
        for edge in payload["inbound_imports"]
    )
    assert payload["barrel_boundaries"] == [{
        "file": "src/features/index.ts",
        "re_exports": [{"specifier": "./widget", "resolved_file": "src/features/widget.tsx"}],
    }]
    assert payload["workflow_participation"] == {
        "availability": "available",
        "entries": [{
            "name": "feature-checkout",
            "path": ".claude/docs/workflows/feature-checkout.md",
            "matched_paths": ["src/features/index.ts"],
        }],
    }
    assert payload["unavailable_fields"] == [
        {
            "field": "responsibility_clusters",
            "reason": "TypeScript v1 maps module facts and does not infer responsibility clusters.",
        },
        {
            "field": "open_questions",
            "reason": "TypeScript v1 does not generate judgment-oriented open questions.",
        },
    ]
    assert payload["compliance"]["typescript_diagnostics"]["availability"] == "available"
    assert payload["compliance"]["eslint"]["availability"] == "unavailable"
    assert "Status: **complete**" in output.read_text(encoding="utf-8")
    assert len((host / "reports" / "_meta" / "effectiveness.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_unresolved_import_is_a_visible_partial_map_not_a_false_complete_result(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    (host / "src" / "features" / "unresolved.ts").write_text(
        'import { absent } from "@app/not-here";\nexport const missing = absent;\n',
        encoding="utf-8",
    )
    result, _, evidence = _map(SKILL, host)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = _load(evidence)
    assert payload["status"] == "partial"
    assert payload["counts"]["unresolved_imports"] == 1
    assert payload["unresolved_imports"] == [{
        "file": "src/features/unresolved.ts",
        "kind": "import",
        "specifier": "@app/not-here",
    }]
    assert payload["completeness"] == {
        "inventory": "complete",
        "exports": "complete",
        "module_resolution": "partial",
        "workflow_participation": "complete",
    }


def test_invalid_typescript_and_missing_prerequisites_fail_clearly(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    (host / "src" / "features" / "broken.ts").write_text(
        "export function broken(: string { return ''; }\n", encoding="utf-8"
    )
    invalid, _, _ = _map(SKILL, host)
    assert invalid.returncode == 2
    assert "TypeScript syntax errors" in invalid.stderr

    missing_config, _, _ = _map(SKILL, host, tsconfig="missing-tsconfig.json")
    assert missing_config.returncode == 2
    assert "project-local TypeScript requires tsconfig" in missing_config.stderr

    no_typescript = tmp_path / "no-typescript"
    shutil.copytree(FIXTURE / "host", no_typescript, ignore=shutil.ignore_patterns("node_modules"))
    missing_ts, _, _ = _map(SKILL, no_typescript, name="no-typescript")
    assert missing_ts.returncode == 2
    assert "project-local TypeScript package is unavailable" in missing_ts.stderr


def test_typescript_exclusions_are_project_relative_for_broad_and_direct_targets(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)

    broad, _, broad_evidence = _map(SKILL, host, "src", name="broad")
    assert broad.returncode == 0, broad.stdout + broad.stderr
    broad_payload = _load(broad_evidence)
    assert broad_payload["counts"]["source_files"] == 6
    assert not any(
        "generated" in item["file"] or "vendor" in item["file"] or ".test." in item["file"]
        for item in broad_payload["files"]
    )

    direct_targets = ("src/generated", "src/vendor", "src/features/widget.test.tsx")
    for index, target in enumerate(direct_targets):
        result, _, evidence = _map(SKILL, host, target, name=f"excluded-{index}")
        assert result.returncode == 0, result.stdout + result.stderr
        payload = _load(evidence)
        assert payload["counts"]["source_files"] == 0
        assert payload["target"]["exclusion"] == "excluded"


def test_typescript_map_never_traverses_internal_or_external_directory_symlinks(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    (external / "outside.ts").write_text("export const outside = true;\n", encoding="utf-8")
    os.symlink(external, host / "src" / "external-link")
    os.symlink(host / "src" / "vendor", host / "src" / "vendor-link")

    broad, _, evidence = _map(SKILL, host, "src", name="symlink-broad")
    assert broad.returncode == 0, broad.stdout + broad.stderr
    payload = _load(evidence)
    assert all("link" not in item["file"] for item in payload["files"])

    direct, _, _ = _map(SKILL, host, "src/external-link", name="symlink-direct")
    assert direct.returncode == 2
    assert "symbolic link" in direct.stderr


def test_typescript_map_refuses_source_or_symlinked_artifact_paths(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    victim = host / "src" / "features" / "widget.tsx"
    before = victim.read_bytes()
    source_output = _map_with_paths(
        host,
        output=victim,
        evidence=host / "reports" / "map" / "safe" / "typescript-map.json",
    )
    assert source_output.returncode == 2
    assert "artifact output" in source_output.stderr
    assert victim.read_bytes() == before

    os.symlink(host / "src", host / "reports")
    linked_report = _map_with_paths(
        host,
        output=host / ".claude" / "docs" / "subsystems" / "safe.md",
        evidence=host / "reports" / "map" / "unsafe" / "typescript-map.json",
    )
    assert linked_report.returncode == 2
    assert "symbolic link" in linked_report.stderr
    assert victim.read_bytes() == before


def test_stock_install_runs_documented_map_command_without_checkout_runtime(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    install = _run(
        "bash",
        "-c",
        _documented_command(SKILL, "stock-install"),
        cwd=host,
        env={
            **os.environ,
            "DO_NOT_TRACK": "1",
            "MAP_SUBSYSTEM_SOURCE": str(REPO_ROOT),
        },
    )
    assert install.returncode == 0, install.stdout + install.stderr
    installed = host / ".agents" / "skills" / "map-subsystem"
    assert installed.is_dir()
    assert not installed.resolve().is_relative_to(REPO_ROOT.resolve())

    command = _documented_command(installed, "typescript-map")
    result = _run("bash", "-c", command, cwd=host)
    assert result.returncode == 0, result.stdout + result.stderr
    output = host / ".claude" / "docs" / "subsystems" / "typescript-features.md"
    evidence = host / "reports" / "map" / "typescript-features" / "typescript-map.json"
    payload = _load(evidence)
    assert output.is_file()
    assert payload["status"] == "complete"
    assert payload["counts"]["inbound_imports"] == 2
    assert str(REPO_ROOT) not in installed.joinpath("scripts", "map_typescript.mjs").read_text(encoding="utf-8")
