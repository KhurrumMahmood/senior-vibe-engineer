from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "explain-code"
INVENTORY = SKILL / "scripts" / "inventory_symbols.py"
RENDER = SKILL / "scripts" / "render_explanation.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "explain-code-typescript"


def _run_isolated(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-S", str(script), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def _snapshot_tree(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _write_annotation(path: Path, target: dict) -> None:
    path.write_text(
        f"""# Annotation — {target['symbol_key']}

## Location
- Symbol: `{target['symbol']}`
- File: `{target['file']}`
- Kind: `{target['kind']}`
- Status: `found`

## Intent
`{target['symbol']}` exposes the fixture's direct public behavior.

## Preconditions
None beyond the signature types.

## Postconditions
- **Success:** returns the branch selected by its input.
- **Failure:** does not resolve imported behavior.
- **Side effects:** none.

## Invariants
- The exported symbol remains the public entry point.

## Callers (0 total)
No in-fixture callers.

## Unexplained regions
- The imported fallback branch — resolving its implementation would require module resolution. Re-run: `/explain-code src/fallback.ts`.

## Surprising behavior
No surprises — behavior matches the symbol name.
""",
        encoding="utf-8",
    )


def test_python_targets_reference_oracle_is_stable_and_copyable(tmp_path: Path) -> None:
    """D2: freeze the Python targets.json contract before copying it to TS."""
    host = tmp_path / "host"
    shutil.copytree(FIXTURES / "python-oracle", host)
    installed = tmp_path / "installed" / "explain-code"
    shutil.copytree(SKILL, installed)
    output = host / "reports" / "python-targets.json"

    result = _run_isolated(
        installed / "scripts" / "inventory_symbols.py",
        "--target",
        "src/sample.py",
        "--repo-root",
        str(host),
        "--output",
        str(output),
        cwd=host,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(output.read_text(encoding="utf-8")) == json.loads(
        (FIXTURES / "python-oracle" / "expected-targets.json").read_text(
            encoding="utf-8"
        )
    )


def test_typescript_final_artifact_is_honest_and_leaves_source_unchanged(
    tmp_path: Path,
) -> None:
    """D3/D5: copied skill produces the doc + sidecars for direct exports only."""
    host = tmp_path / "host"
    shutil.copytree(FIXTURES / "typescript-host", host)
    installed = tmp_path / "installed" / "explain-code"
    shutil.copytree(SKILL, installed)
    source_before = _snapshot_tree(host / "src")
    report_dir = host / "reports" / "explanations" / "src"
    targets_path = report_dir / "targets.json"

    collect = _run_isolated(
        installed / "scripts" / "inventory_symbols.py",
        "--target",
        "src",
        "--repo-root",
        str(host),
        "--output",
        str(targets_path),
        cwd=host,
    )

    assert collect.returncode == 0, collect.stdout + collect.stderr
    targets = json.loads(targets_path.read_text(encoding="utf-8"))
    second_targets_path = report_dir / "targets-second.json"
    repeat = _run_isolated(
        installed / "scripts" / "inventory_symbols.py",
        "--target",
        "src",
        "--repo-root",
        str(host),
        "--output",
        str(second_targets_path),
        cwd=host,
    )
    assert repeat.returncode == 0, repeat.stdout + repeat.stderr
    assert second_targets_path.read_bytes() == targets_path.read_bytes()
    assert targets["language"] == "typescript"
    assert [item["symbol"] for item in targets["targets"]] == [
        "decide",
        "renderLabel",
        "Badge",
    ]
    assert {item["file"] for item in targets["targets"]} == {
        "src/branchy.ts",
        "src/Badge.tsx",
    }
    assert targets["targets"][0]["branch_count"] >= 2
    assert all("private" not in item["symbol"].lower() for item in targets["targets"])
    assert all("test" not in item["file"] for item in targets["targets"])
    assert all("vendor" not in item["file"] for item in targets["targets"])
    assert all("generated" not in item["file"] for item in targets["targets"])
    assert {
        item["symbol"] for item in targets["unexplained"]
    } == {
        "export { localThing as legacyThing }",
        "export { remoteThing } from \"./remote\"",
        "export * from \"./barrel\"",
    }

    annotations = report_dir / "annotations"
    annotations.mkdir(parents=True)
    for target in targets["targets"]:
        _write_annotation(annotations / f"{target['symbol_key']}.md", target)
    document = host / "reports" / "explanations" / "src.md"
    render = _run_isolated(
        installed / "scripts" / "render_explanation.py",
        "--targets",
        str(targets_path),
        "--annotations-dir",
        str(annotations),
        "--output",
        str(document),
        "--summary",
        "Direct TypeScript exports are annotated without resolving imports or export aliases.",
        "--regenerated",
        "2026-07-19T00:00:00Z",
        cwd=host,
    )

    assert render.returncode == 0, render.stdout + render.stderr
    rendered = document.read_text(encoding="utf-8")
    assert "# Explanation — src" in rendered
    assert "### decide" in rendered
    assert "### renderLabel" in rendered
    assert "### Badge" in rendered
    assert "**Preconditions.**" in rendered
    assert "**Postconditions.**" in rendered
    assert "**Invariants.**" in rendered
    assert "**Callers.**" in rendered
    assert "## Unexplained regions" in rendered
    assert "export { localThing as legacyThing }" in rendered
    assert "TypeScript v1 does not resolve export aliases or re-exports" in rendered
    unexplained = (report_dir / "unexplained.txt").read_text(encoding="utf-8")
    assert "export { remoteThing } from \"./remote\"" in unexplained
    assert (report_dir / "surprises.txt").is_file()
    assert _snapshot_tree(host / "src") == source_before


def test_typescript_ignores_are_relative_to_requested_target(tmp_path: Path) -> None:
    """A host may itself sit below a vendor-named ancestor; only descendants skip."""
    host = tmp_path / "vendor" / "host"
    shutil.copytree(FIXTURES / "typescript-host", host)
    output = host / "reports" / "targets.json"

    result = _run_isolated(
        INVENTORY,
        "--target",
        "src",
        "--repo-root",
        str(host),
        "--output",
        str(output),
        cwd=host,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert {item["symbol"] for item in json.loads(output.read_text())["targets"]} >= {
        "decide",
        "renderLabel",
        "Badge",
    }
