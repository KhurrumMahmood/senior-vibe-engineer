"""Final-artifact, native-check, and copied-install proof for TypeScript proposals."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "propose-folder-reorganization"
SCRIPT = SKILL / "scripts" / "propose_typescript.mjs"
PYTHON_INSPECT = SKILL / "scripts" / "inspect.py"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "propose-folder-reorganization-typescript"


def _run(
    *args: str,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, check=False)


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE / "host", host)
    install = _run("npm", "ci", "--offline", "--ignore-scripts", cwd=host)
    assert install.returncode == 0, install.stdout + install.stderr
    native = _run("npm", "run", "typecheck", cwd=host)
    assert native.returncode == 0, native.stdout + native.stderr
    return host


def _propose(
    skill: Path,
    host: Path,
    *,
    parent: str = "src",
    prefix: str = "billing",
    judgment: str = "split",
    name: str = "billing",
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    proposal = host / "reports" / "propose-folder-reorganization" / name / "proposal.md"
    inspection = host / "reports" / "propose-folder-reorganization" / name / "inspection.json"
    result = _run(
        "node",
        str(skill / "scripts" / "propose_typescript.mjs"),
        "--parent",
        parent,
        "--prefix",
        prefix,
        "--cluster-judgment",
        judgment,
        "--project-root",
        str(host),
        "--tsconfig",
        "tsconfig.json",
        "--proposal",
        str(proposal),
        "--inspection",
        str(inspection),
        cwd=host,
    )
    return result, proposal, inspection


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix in {".ts", ".tsx"}
    }


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


def _apply_move_plan(host: Path, payload: dict) -> None:
    """Apply the proposed move table in a disposable host for native proof."""
    moved_paths = {item["current_path"]: item["new_path"] for item in payload["cluster_files"]}
    for item in payload["cluster_files"]:
        source = host / item["current_path"]
        destination = host / item["new_path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)

    for impact in payload["import_impact"]:
        importer = host / moved_paths.get(impact["importer"], impact["importer"])
        contents = importer.read_text(encoding="utf-8")
        old = f'"{impact["specifier"]}"'
        new = f'"{impact["after_move_specifier"]}"'
        assert old in contents, impact
        importer.write_text(contents.replace(old, new), encoding="utf-8")

    barrel = payload["compatibility"]["new_barrel"]
    barrel_path = host / barrel["path"]
    barrel_path.parent.mkdir(parents=True, exist_ok=True)
    barrel_path.write_text(
        "".join(
            f"export {{ {', '.join(item['symbols'])} }} from \"{item['specifier']}\";\n"
            for item in barrel["re_exports"]
            if item["symbols"]
        ),
        encoding="utf-8",
    )
    with barrel_path.open("a", encoding="utf-8") as handle:
        for item in barrel["re_exports"]:
            if item["type_symbols"]:
                handle.write(
                    f"export type {{ {', '.join(item['type_symbols'])} }} from \"{item['specifier']}\";\n"
                )


def test_typescript_proposal_reaches_final_artifacts_with_complete_resolved_impact(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    source_before = _tree_hashes(host / "src")
    result, proposal, inspection = _propose(SKILL, host)

    assert result.returncode == 0, result.stdout + result.stderr
    assert proposal.is_file()
    assert inspection.is_file()
    payload = _load(inspection)

    assert payload["status"] == "ready"
    assert payload["language"] == "typescript"
    assert payload["analyzer"] == "typescript-compiler-api"
    assert payload["recommendation"] == "refactor"
    assert payload["summary"] == {
        "cluster_size": 3,
        "resolved_import_impact_count": 7,
        "unresolved_import_count": 0,
    }
    assert [item["current_path"] for item in payload["cluster_files"]] == [
        "src/billing-parser.ts",
        "src/billing-types.ts",
        "src/billing-validator.ts",
    ]
    assert [item["new_path"] for item in payload["cluster_files"]] == [
        "src/billing/parser.ts",
        "src/billing/types.ts",
        "src/billing/validator.ts",
    ]
    assert any(
        item["importer"] == "src/alias-consumer.ts"
        and item["specifier"] == "@app/billing-parser"
        and item["after_move_specifier"] == "@app/billing/parser"
        for item in payload["import_impact"]
    )
    assert any(
        item["importer"] == "src/checkout.ts"
        and item["specifier"] == "./billing-validator"
        and item["after_move_specifier"] == "./billing/validator"
        for item in payload["import_impact"]
    )
    assert any(
        item["importer"] == "src/index.ts"
        and item["kind"] == "re_export"
        and item["after_move_specifier"] == "./billing/parser"
        for item in payload["import_impact"]
    )
    assert payload["compatibility"] == {
        "decision": "preserve_existing_barrels_migrate_subpaths",
        "existing_barrels": ["src/index.ts"],
        "new_barrel": {
            "path": "src/billing/index.ts",
            "re_exports": [
                {"specifier": "./parser", "symbols": ["parseInvoice"], "type_symbols": []},
                {"specifier": "./types", "symbols": [], "type_symbols": ["Invoice"]},
                {"specifier": "./validator", "symbols": ["validateInvoice"], "type_symbols": []},
            ],
        },
        "subpath_compatibility": "rewrite every resolved direct subpath importer; do not retain legacy file shims",
    }
    rendered = proposal.read_text(encoding="utf-8")
    assert "# TypeScript folder reorganization proposal — src::billing" in rendered
    assert "## Complete resolved import-impact table" in rendered
    assert "@app/billing-parser" in rendered
    assert "preserve_existing_barrels_migrate_subpaths" in rendered
    assert "npm run typecheck" in rendered
    assert _tree_hashes(host / "src") == source_before


def test_proposed_move_table_typechecks_after_characterization_rewrite(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    result, _, inspection = _propose(SKILL, host)

    assert result.returncode == 0, result.stdout + result.stderr
    _apply_move_plan(host, _load(inspection))
    native = _run("npm", "run", "typecheck", cwd=host)
    assert native.returncode == 0, native.stdout + native.stderr


def test_threshold_cohesive_scratch_and_excluded_targets_defer_without_false_proposals(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)

    cases = [
        ("src/two", "payment", "split", "threshold", "defer_below_threshold"),
        ("src/cohesive", "report", "cohesive", "cohesive", "defer_cohesive_cluster"),
        ("src/scratch", "legacy", "split", "scratch", "defer_scratch_code"),
        ("src/generated", "billing", "split", "generated", "defer_excluded_target"),
        ("src/vendor", "billing", "split", "vendor", "defer_excluded_target"),
        ("src/__tests__", "billing", "split", "tests", "defer_excluded_target"),
    ]
    for parent, prefix, judgment, name, recommendation in cases:
        result, proposal, inspection = _propose(
            SKILL,
            host,
            parent=parent,
            prefix=prefix,
            judgment=judgment,
            name=name,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert proposal.is_file()
        payload = _load(inspection)
        assert payload["status"] == "deferred"
        assert payload["recommendation"] == recommendation
        assert f"**Recommendation:** `{recommendation}`" in proposal.read_text(encoding="utf-8")


def test_unresolved_cluster_import_blocks_proposal_instead_of_claiming_complete_impact(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    (host / "src" / "billing-unresolved.ts").write_text(
        'import { absent } from "@app/not-here";\nexport const missing = absent;\n',
        encoding="utf-8",
    )

    result, proposal, inspection = _propose(SKILL, host, name="unresolved")

    assert result.returncode == 0, result.stdout + result.stderr
    payload = _load(inspection)
    assert payload["status"] == "blocked"
    assert payload["recommendation"] == "defer_unresolved_imports"
    assert payload["unresolved_imports"] == [{
        "file": "src/billing-unresolved.ts",
        "kind": "import",
        "specifier": "@app/not-here",
    }]
    assert "## Unresolved module facts — proposal blocked" in proposal.read_text(encoding="utf-8")


def test_logical_and_physical_path_safety_rejects_symlink_and_escape_paths(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    os.symlink(host / "src", host / "src-link")
    symlinked, _, _ = _propose(SKILL, host, parent="src-link", name="symlinked")
    assert symlinked.returncode == 2
    assert "symbolic link" in symlinked.stderr

    outside = tmp_path / "outside"
    outside.mkdir()
    escaped = _run(
        "node", str(SCRIPT),
        "--parent", "../outside", "--prefix", "billing", "--cluster-judgment", "split",
        "--project-root", str(host), "--tsconfig", "tsconfig.json",
        "--proposal", str(host / "reports" / "propose-folder-reorganization" / "escape" / "proposal.md"),
        "--inspection", str(host / "reports" / "propose-folder-reorganization" / "escape" / "inspection.json"),
        cwd=host,
    )
    assert escaped.returncode == 2
    assert "inside project root" in escaped.stderr

    linked_host = _copy_host(tmp_path, "linked-host")
    (linked_host / "reports").mkdir()
    victim = linked_host / "src" / "billing-parser.ts"
    before = victim.read_bytes()
    shutil.rmtree(linked_host / "reports")
    os.symlink(linked_host / "src", linked_host / "reports")
    linked_artifact, _, _ = _propose(SKILL, linked_host, name="unsafe-artifact")
    assert linked_artifact.returncode == 2
    assert "symbolic link" in linked_artifact.stderr
    assert victim.read_bytes() == before


def test_python_reference_inspection_preserves_positive_and_below_threshold_oracles(tmp_path: Path) -> None:
    host = tmp_path / "python-host"
    shutil.copytree(FIXTURE / "python-reference", host)

    positive = host / "reports" / "positive.json"
    result = _run(
        sys.executable, str(PYTHON_INSPECT),
        "--parent", "pkg", "--prefix", "billing", "--project-root", str(host), "--output", str(positive),
        cwd=host,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = _load(positive)
    assert payload["summary"]["cluster_size"] == 3
    assert payload["import_impact"] == [{
        "importer": "pkg/consumer.py",
        "lineno": 1,
        "statement": "from pkg.billing_parser import parse_invoice",
        "current_module": "pkg.billing_parser",
        "current_symbol": "parse_invoice",
        "new_module": "pkg.billing.parser",
        "form": "from",
    }]

    below = host / "reports" / "below.json"
    below_result = _run(
        sys.executable, str(PYTHON_INSPECT),
        "--parent", "pkg", "--prefix", "two", "--project-root", str(host), "--output", str(below),
        cwd=host,
    )
    assert below_result.returncode == 0, below_result.stdout + below_result.stderr
    assert _load(below)["defer_signals"] == ["cluster_below_threshold"]


def test_stock_selected_skill_install_replays_natural_typescript_proposal_task(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    install = _run(
        "bash", "-c", _documented_command(SKILL, "stock-install"),
        cwd=host,
        env={
            **os.environ,
            "DO_NOT_TRACK": "1",
            "PROPOSE_FOLDER_REORGANIZATION_SOURCE": str(REPO_ROOT),
        },
    )
    assert install.returncode == 0, install.stdout + install.stderr
    installed = host / ".agents" / "skills" / "propose-folder-reorganization"
    assert installed.is_dir()
    assert not installed.resolve().is_relative_to(REPO_ROOT.resolve())

    command = _documented_command(installed, "typescript-proposal")
    replay = _run(
        "bash", "-c", command,
        cwd=host,
        env={
            **os.environ,
            "PFR_PARENT": "src",
            "PFR_PREFIX": "billing",
            "PFR_CLUSTER_JUDGMENT": "split",
            "PFR_NAME": "installed-billing",
        },
    )
    assert replay.returncode == 0, replay.stdout + replay.stderr
    evidence = host / "reports" / "propose-folder-reorganization" / "installed-billing" / "inspection.json"
    proposal = host / "reports" / "propose-folder-reorganization" / "installed-billing" / "proposal.md"
    assert _load(evidence)["status"] == "ready"
    assert proposal.is_file()
    assert str(REPO_ROOT) not in installed.joinpath("scripts", "propose_typescript.mjs").read_text(encoding="utf-8")
