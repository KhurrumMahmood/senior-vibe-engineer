"""End-to-end TypeScript proposal, deferral, and installed-closure proof."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "propose-boundary"
SCRIPT = SKILL / "scripts" / "propose_typescript.mjs"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "propose-boundary-typescript"


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
    typecheck = _run("npm", "run", "typecheck", cwd=host)
    assert typecheck.returncode == 0, typecheck.stdout + typecheck.stderr
    native_test = _run("npm", "test", cwd=host)
    assert native_test.returncode == 0, native_test.stdout + native_test.stderr
    return host


def _propose(
    skill: Path,
    host: Path,
    target: str = "src/legacy",
    *,
    name: str = "legacy",
    candidates: int = 2,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    inspection = host / "reports" / "propose-boundary" / name / "inspection.json"
    proposal = host / "reports" / "propose-boundary" / name / "proposal.md"
    result = _run(
        "node",
        str(skill / "scripts" / "propose_typescript.mjs"),
        "--target",
        target,
        "--project-root",
        str(host),
        "--tsconfig",
        "tsconfig.json",
        "--candidates",
        str(candidates),
        "--inspection",
        str(inspection),
        "--proposal",
        str(proposal),
        cwd=host,
    )
    return result, inspection, proposal


def _payload(path: Path) -> dict:
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


def test_typescript_proposal_reaches_final_artifact_from_resolved_graph(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    result, inspection, proposal = _propose(SKILL, host)

    assert result.returncode == 0, result.stdout + result.stderr
    assert inspection.is_file()
    assert proposal.is_file()
    payload = _payload(inspection)
    rendered = proposal.read_text(encoding="utf-8")

    assert payload["language"] == "typescript"
    assert payload["analyzer"] == "typescript-compiler-api"
    assert payload["status"] == "complete"
    assert payload["recommendation"] == "refactor"
    assert payload["graph"]["module_resolution"] == "complete"
    assert payload["graph"]["ambiguous_symbols"] == []
    assert payload["candidate_selection"] == {
        "requested": 2,
        "eligible": 2,
        "returned": 2,
        "cutoff_score": 0.75,
        "ties_included": False,
        "omitted_count": 0,
        "omitted": [],
    }
    assert {edge["style"] for edge in payload["graph"]["inbound_imports"]} == {
        "alias",
        "barrel",
        "direct",
    }
    assert any(
        edge["caller_symbol"] == "settlementCapture"
        and edge["callee_symbol"] == "_quoteNormalize"
        and edge["resolution"] == "resolved"
        for edge in payload["graph"]["call_edges"]
    )
    quote = next(seam for seam in payload["candidate_seams"] if seam["cluster_id"] == "quote")
    assert "_quoteNormalize" in quote["members"]
    assert "_quoteNormalize" not in quote["proposed_public_api"]
    assert any(
        impact["source_file"] == "src/direct-consumer.ts" and impact["imports_private"]
        for impact in payload["caller_impact"]
    )
    assert "## Compatibility and barrel plan" in rendered
    assert "src/legacy/index.ts" in rendered
    assert "`index.ts`/`index.tsx`" in rendered
    assert "index.js" not in rendered
    assert "## Characterization and native verification plan" in rendered
    assert "npm run typecheck" in rendered
    assert "npm test" in rendered
    assert "Resolved graph evidence" in rendered


def test_cohesive_target_defers_instead_of_inventing_a_boundary(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    result, inspection, proposal = _propose(SKILL, host, "src/cohesive", name="cohesive")

    assert result.returncode == 0, result.stdout + result.stderr
    payload = _payload(inspection)
    assert payload["status"] == "deferred"
    assert payload["recommendation"] == "defer_no_seam"
    assert payload["defer_signals"] == ["single_cluster_no_seam"]
    assert payload["candidate_seams"] == []
    assert "No extraction proposal is safe" in proposal.read_text(encoding="utf-8")


def test_unresolved_and_ambiguous_graphs_defer_explicitly(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    unresolved, unresolved_json, unresolved_proposal = _propose(
        SKILL, host, "src/unresolved", name="unresolved"
    )
    ambiguous, ambiguous_json, ambiguous_proposal = _propose(
        SKILL, host, "src/ambiguous", name="ambiguous"
    )

    assert unresolved.returncode == 0, unresolved.stdout + unresolved.stderr
    unresolved_payload = _payload(unresolved_json)
    assert unresolved_payload["status"] == "deferred"
    assert unresolved_payload["recommendation"] == "defer_unresolved_graph"
    assert unresolved_payload["graph"]["unresolved_imports"] == [{
        "file": "src/unresolved/workflow.ts",
        "kind": "import",
        "specifier": "@orders/no-such-module",
    }]
    assert "unresolved static module specifiers" in unresolved_proposal.read_text(encoding="utf-8")

    assert ambiguous.returncode == 0, ambiguous.stdout + ambiguous.stderr
    ambiguous_payload = _payload(ambiguous_json)
    assert ambiguous_payload["status"] == "deferred"
    assert ambiguous_payload["recommendation"] == "defer_unresolved_graph"
    assert ambiguous_payload["graph"]["ambiguous_symbols"]
    assert "ambiguous exported symbols" in ambiguous_proposal.read_text(encoding="utf-8")


def test_exclusions_and_symlink_policy_apply_to_broad_and_direct_targets(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    broad, broad_json, _ = _propose(SKILL, host, "src", name="broad")

    assert broad.returncode == 0, broad.stdout + broad.stderr
    broad_payload = _payload(broad_json)
    assert not any(
        any(token in symbol["file"] for token in ("generated", "vendor", ".test."))
        for symbol in broad_payload["symbols"]
    )

    for index, target in enumerate(("src/generated", "src/vendor", "src/legacy/order-workflow.test.ts")):
        result, inspection, _ = _propose(SKILL, host, target, name=f"excluded-{index}")
        assert result.returncode == 0, result.stdout + result.stderr
        payload = _payload(inspection)
        assert payload["target"]["exclusion"] == "excluded"
        assert payload["symbols"] == []

    external = tmp_path / "external"
    external.mkdir()
    (external / "outside.ts").write_text("export const outside = true;\n", encoding="utf-8")
    os.symlink(external, host / "src" / "external-link")
    linked, _, _ = _propose(SKILL, host, "src/external-link", name="linked")
    assert linked.returncode == 2
    assert "symbolic link" in linked.stderr


def test_stock_install_runs_documented_command_outside_checkout_without_repo_imports(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    install = _run(
        "bash",
        "-c",
        _documented_command(SKILL, "stock-install"),
        cwd=host,
        env={
            **os.environ,
            "DO_NOT_TRACK": "1",
            "PROPOSE_BOUNDARY_SOURCE": str(REPO_ROOT),
        },
    )
    assert install.returncode == 0, install.stdout + install.stderr
    installed = host / ".agents" / "skills" / "propose-boundary"
    assert installed.is_dir()
    assert not installed.resolve().is_relative_to(REPO_ROOT.resolve())

    command = _documented_command(installed, "typescript-proposal")
    result = _run("bash", "-c", command, cwd=host)
    assert result.returncode == 0, result.stdout + result.stderr
    proposal = host / "reports" / "propose-boundary" / "typescript-legacy" / "proposal.md"
    assert proposal.is_file()
    assert "Recommendation: **refactor**" in proposal.read_text(encoding="utf-8")
    closure = (installed / "scripts" / "propose_typescript.mjs").read_text(encoding="utf-8")
    assert "scripts/_lib" not in closure
    assert "../.." not in closure
    assert str(REPO_ROOT) not in closure


def test_skill_docs_truthfully_limit_typescript_v1() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    assert "language: any" in text
    assert "framework: any" in text
    assert "scans: [python, typescript, javascript]" in text
    assert "project-local `tsconfig.json`" in text
    assert "unresolved or ambiguous" in text
    assert "framework semantics" in text


def test_python_reference_positive_clean_and_excluded_paths_remain_unchanged(tmp_path: Path) -> None:
    host = tmp_path / "python-host"
    (host / "src" / "node_modules").mkdir(parents=True)
    (host / "src" / "boundary.py").write_text(
        "\n".join([
            "def quote_price(): return _quote_normalize()",
            "def quote_preview(): return quote_price()",
            "def quote_discount(): return 0",
            "def _quote_normalize(): return 1",
            "def settlement_capture(): return _quote_normalize()",
            "def settlement_receipt(): return settlement_capture()",
            "def settlement_status(): return 'paid'",
            "def _settlement_validate(): return True",
            "",
        ]),
        encoding="utf-8",
    )
    (host / "src" / "cohesive.py").write_text(
        "\n".join([
            "def shipping_quote(): return 1",
            "def shipping_schedule(): return shipping_quote()",
            "def shipping_confirm(): return True",
            "def shipping_label(): return 'label'",
            "def shipping_region(): return 'region'",
            "def shipping_cancel(): return False",
            "",
        ]),
        encoding="utf-8",
    )
    (host / "src" / "node_modules" / "ignored.py").write_text(
        "def quote_price(): return 0\n", encoding="utf-8"
    )

    def inspect(target: str, name: str) -> dict:
        output = host / "reports" / name / "inspection.json"
        result = _run(
            sys.executable,
            str(SKILL / "scripts" / "propose.py"),
            "--target",
            target,
            "--project-root",
            str(host),
            "--output",
            str(output),
            cwd=host,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return _payload(output)

    positive = inspect("src/boundary.py", "positive")
    assert {seam["cluster_id"] for seam in positive["candidate_seams"]} == {"quote"}
    assert positive["defer_signals"] == []

    cohesive = inspect("src/cohesive.py", "cohesive")
    assert cohesive["candidate_seams"] == []
    assert cohesive["defer_signals"] == ["single_cluster_no_seam"]

    excluded = inspect("src/node_modules", "excluded")
    assert excluded["symbols"] == []
    assert excluded["candidate_seams"] == []
