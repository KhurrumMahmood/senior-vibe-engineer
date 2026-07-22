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


def _write_annotation(path: Path, target: dict, *, intent: str | None = None) -> None:
    intent_text = intent or f"`{target['symbol']}` exposes the fixture's direct public behavior."
    path.write_text(
        f"""# Annotation — {target['symbol_key']}

## Location
- Symbol: `{target['symbol']}`
- File: `{target['file']}`
- Kind: `{target['kind']}`
- Status: `found`

## Intent
{intent_text}

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

    directory_output = host / "reports" / "python-directory-targets.json"
    directory_result = _run_isolated(
        installed / "scripts" / "inventory_symbols.py",
        "--target",
        "src",
        "--repo-root",
        str(host),
        "--output",
        str(directory_output),
        cwd=host,
    )
    assert directory_result.returncode == 0, directory_result.stdout + directory_result.stderr
    assert json.loads(directory_output.read_text(encoding="utf-8")) == json.loads(
        (FIXTURES / "python-oracle" / "expected-directory-targets.json").read_text(
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


def test_typescript_multibinding_and_regex_literal_keep_following_export(
    tmp_path: Path,
) -> None:
    host = tmp_path / "host"
    shutil.copytree(FIXTURES / "lexical-edge-host", host)
    installed = tmp_path / "installed" / "explain-code"
    shutil.copytree(SKILL, installed)
    output = host / "reports" / "targets.json"

    result = _run_isolated(
        installed / "scripts" / "inventory_symbols.py",
        "--target",
        "src",
        "--repo-root",
        str(host),
        "--output",
        str(output),
        cwd=host,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    targets = json.loads(output.read_text(encoding="utf-8"))
    assert {item["symbol"] for item in targets["targets"]} == {
        "first",
        "second",
        "afterRegex",
        "Palette",
    }
    palette = next(item for item in targets["targets"] if item["symbol"] == "Palette")
    assert palette["kind"] == "enum"
    assert targets["unexplained"] == []


def test_same_basename_symbols_have_distinct_annotations(tmp_path: Path) -> None:
    host = tmp_path / "host"
    shutil.copytree(FIXTURES / "collision-host", host)
    installed = tmp_path / "installed" / "explain-code"
    shutil.copytree(SKILL, installed)
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
    assert [item["symbol"] for item in targets["targets"]] == ["shared", "shared"]
    assert len({item["symbol_key"] for item in targets["targets"]}) == 2
    assert {item["file"] for item in targets["targets"]} == {
        "src/a-b/index.ts",
        "src/a_b/index.ts",
    }

    annotations = report_dir / "annotations"
    annotations.mkdir(parents=True)
    for target in targets["targets"]:
        _write_annotation(
            annotations / f"{target['symbol_key']}.md",
            target,
            intent=f"`{target['file']}` owns this distinct `shared` export.",
        )
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
        "Two modules expose distinct direct exports with the same symbol name.",
        "--regenerated",
        "2026-07-19T00:00:00Z",
        cwd=host,
    )
    assert render.returncode == 0, render.stdout + render.stderr
    rendered = document.read_text(encoding="utf-8")
    assert "`src/a-b/index.ts` owns this distinct `shared` export." in rendered
    assert "`src/a_b/index.ts` owns this distinct `shared` export." in rendered


def test_reexport_only_target_renders_visible_unexplained_output(tmp_path: Path) -> None:
    host = tmp_path / "host"
    shutil.copytree(FIXTURES / "reexport-only-host", host)
    installed = tmp_path / "installed" / "explain-code"
    shutil.copytree(SKILL, installed)
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
    assert targets["targets"] == []
    assert {item["symbol"] for item in targets["unexplained"]} == {
        'export { Local as PublicLocal } from "./local"',
        'export * from "./values"',
        'export type * from "./types"',
    }

    annotations = report_dir / "annotations"
    annotations.mkdir(parents=True)
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
        "This target contains only unresolved re-exports and has no directly annotatable declarations.",
        "--regenerated",
        "2026-07-19T00:00:00Z",
        cwd=host,
    )
    assert render.returncode == 0, render.stdout + render.stderr
    rendered = document.read_text(encoding="utf-8")
    assert "Annotated this run | 0" in rendered
    assert 'export type * from "./types"' in rendered
    unexplained = (report_dir / "unexplained.txt").read_text(encoding="utf-8")
    assert unexplained.count("TypeScript v1 does not resolve") == 3


def test_truncated_typescript_blocks_without_targets_artifact(tmp_path: Path) -> None:
    host = tmp_path / "host"
    shutil.copytree(FIXTURES / "invalid-host", host)
    installed = tmp_path / "installed" / "explain-code"
    shutil.copytree(SKILL, installed)
    output = host / "reports" / "targets.json"

    result = _run_isolated(
        installed / "scripts" / "inventory_symbols.py",
        "--target",
        "src",
        "--repo-root",
        str(host),
        "--output",
        str(output),
        cwd=host,
    )

    assert result.returncode != 0
    assert "lexical syntax check failed" in result.stderr
    assert "unclosed" in result.stderr
    assert not output.exists()
