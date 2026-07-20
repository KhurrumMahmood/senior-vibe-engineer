"""Final-artifact contracts for the checked-JavaScript proposal cohort."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / ".claude" / "skills"
SEED = REPO_ROOT / "tests" / "fixtures" / "find-dormant-typescript" / "host"
SUFFIXES = {".js", ".jsx", ".mjs", ".cjs"}


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)


def _write(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def _hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def _host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(SEED, host)
    install = _run("npm", "ci", "--offline", "--ignore-scripts", cwd=host)
    assert install.returncode == 0, install.stdout + install.stderr
    _write(host / "src" / "typed.ts", "export const typed = true;\n")
    _write(
        host / "src" / "state.js",
        """/** @typedef {\"queued\" | \"sent\"} DeliveryState */
/** @type {{ status: DeliveryState }} */
export const delivery = { status: \"queued\" };
export function advance() {
  if (delivery.status === \"queued\") delivery.status = \"sent\";
  return delivery.status;
}
const open = { status: \"queued\" };
if (open.status === \"queued\") open.status = \"sent\";
""",
    )
    _write(
        host / "src" / "panel.jsx",
        """/** @type {{ status: import(\"./state.js\").DeliveryState }} */
export const panelState = { status: \"queued\" };
if (panelState.status === \"queued\") panelState.status = \"sent\";
export function Panel() { return panelState.status; }
""",
    )
    _write(
        host / "src" / "worker.mjs",
        """import { delivery } from \"./state.js\";
if (delivery.status === \"sent\") delivery.status = \"queued\";
export const worker = delivery.status;
""",
    )
    _write(
        host / "src" / "legacy.cjs",
        """/** @type {{ status: import(\"./state.js\").DeliveryState }} */
const legacy = { status: \"queued\" };
if (legacy.status === \"queued\") legacy.status = \"sent\";
exports.value = legacy.status;
""",
    )
    _write(
        host / "src" / "boundary" / "quote.js",
        """export function quotePrice() { return 1; }
export function quotePreview() { return quotePrice(); }
function _quoteNormalize() { return 1; }
export function quoteNormalize() { return _quoteNormalize(); }
""",
    )
    _write(
        host / "src" / "boundary" / "settlement.mjs",
        """export function settlementCapture() { return 1; }
export function settlementReceipt() { return settlementCapture(); }
export function settlementStatus() { return \"paid\"; }
""",
    )
    _write(
        host / "src" / "boundary" / "panel.jsx",
        """export function panelRender() { return \"panel\"; }
export function panelState() { return \"ready\"; }
""",
    )
    _write(
        host / "src" / "boundary" / "legacy.cjs",
        """function legacyRead() { return 1; }
function legacyWrite() { return legacyRead(); }
exports.legacyRead = legacyRead;
exports.legacyWrite = legacyWrite;
""",
    )
    _write(host / "src" / "boundary-consumer.js", 'import { quotePrice } from "./boundary/quote.js";\nvoid quotePrice;\n')
    _write(host / "src" / "boundary-alias.mjs", 'import { settlementCapture } from "@app/boundary/settlement.mjs";\nvoid settlementCapture;\n')
    _write(host / "src" / "boundary-require.cjs", 'const legacy = require("./boundary/legacy.cjs");\nvoid legacy;\n')
    _write(host / "src" / "folder" / "billing-parser.js", "export function parseInvoice() { return 1; }\n")
    _write(host / "src" / "folder" / "billing_validator.jsx", "export function validateInvoice() { return true; }\n")
    _write(host / "src" / "folder" / "billing-types.mjs", "export const invoiceKind = \"invoice\";\n")
    _write(host / "src" / "folder" / "billing-client.cjs", "exports.loadInvoice = () => 1;\n")
    _write(host / "src" / "checkout.js", 'import { parseInvoice } from "./folder/billing-parser.js";\nvoid parseInvoice;\n')
    _write(host / "src" / "folder-panel.jsx", 'import { validateInvoice } from "./folder/billing_validator.jsx";\nvoid validateInvoice;\n')
    _write(host / "src" / "folder-worker.mjs", 'import { invoiceKind } from "./folder/billing-types.mjs";\nvoid invoiceKind;\n')
    _write(host / "src" / "folder-legacy.cjs", 'const client = require("./folder/billing-client.cjs");\nvoid client;\n')
    _write(host / "src" / "folder-alias.js", 'import { parseInvoice } from "@folder/billing-parser.js";\nvoid parseInvoice;\n')
    _write(host / "src" / "shadow-a.js", "export function first() { return { value: 1 }; }\n")
    _write(host / "src" / "shadow-b.jsx", "export function second() { return { value: 1 }; }\n")
    _write(
        host / "jsconfig.json",
        json.dumps(
            {
                "compilerOptions": {
                    "allowJs": True,
                    "checkJs": True,
                    "jsx": "preserve",
                    "module": "NodeNext",
                    "moduleResolution": "NodeNext",
                    "noEmit": True,
                    "strict": False,
                    "target": "ES2022",
                    "baseUrl": ".",
                    "paths": {"@app/*": ["src/*"], "@folder/*": ["src/folder/*"]},
                },
                "include": ["src/**/*"],
            },
            indent=2,
        ) + "\n",
    )
    package = json.loads((host / "package.json").read_text(encoding="utf-8"))
    package["scripts"]["check-js"] = "tsc --project jsconfig.json"
    (host / "package.json").write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    check = _run("npm", "run", "check-js", cwd=host)
    assert check.returncode == 0, check.stdout + check.stderr
    return host


def _node(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return _run("node", str(script), *args, cwd=cwd)


def _copy_skill(tmp_path: Path, name: str) -> Path:
    destination = tmp_path / "installed" / name
    shutil.copytree(SKILLS / name, destination)
    return destination


def _apply_folder_plan(host: Path, inspection: dict) -> None:
    moved = {item["current_path"]: item["new_path"] for item in inspection["cluster_files"]}
    for item in inspection["cluster_files"]:
        source = host / item["current_path"]
        destination = host / item["new_path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)
    for impact in inspection["import_impact"]:
        importer = host / moved.get(impact["importer"], impact["importer"])
        source = importer.read_text(encoding="utf-8")
        importer.write_text(
            source.replace(f'"{impact["specifier"]}"', f'"{impact["after_move_specifier"]}"'),
            encoding="utf-8",
        )
    barrel = inspection["compatibility"]["new_barrel"]
    extensions = {
        Path(item["new_path"]).stem: Path(item["new_path"]).suffix
        for item in inspection["cluster_files"]
    }
    _write(
        host / barrel["path"],
        "".join(
            f"export {{ {', '.join(item['symbols'])} }} from \"{item['specifier']}{extensions[Path(item['specifier']).name]}\";\n"
            for item in barrel["re_exports"]
            if item["symbols"]
        ),
    )


def test_checked_javascript_proposals_reach_copied_final_artifacts_without_source_mutation(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    before = _hashes(host / "src")
    for source in ("src/state.js", "src/worker.mjs", "src/legacy.cjs"):
        checked = _run("node", "--check", source, cwd=host)
        assert checked.returncode == 0, checked.stderr
    assert _run("npm", "run", "check-js", cwd=host).returncode == 0
    assert _run("npm", "test", cwd=host).returncode == 0

    implicit = host / "reports" / "implicit-state" / "javascript.jsonl"
    manifest = host / "reports" / "implicit-state" / "javascript.json"
    state = _node(
        SKILLS / "find-implicit-state" / "scripts" / "detect_typescript_state.mjs",
        "--target", "src", "--project-root", str(host), "--tsconfig", "jsconfig.json",
        "--output", str(implicit), "--manifest", str(manifest), "--language", "javascript", cwd=host,
    )
    assert state.returncode == 0, state.stderr
    state_records = [json.loads(line) for line in implicit.read_text(encoding="utf-8").splitlines() if line]
    assert {Path(row["file"]).suffix for row in state_records if row["classification"] == "first_party_state_operation"} == SUFFIXES
    assert any(row["classification"] == "open_ended_string" for row in state_records)

    enum = _copy_skill(tmp_path, "extract-enum")
    enum_targets = host / "reports" / "extract-enum" / "delivery" / "targets.json"
    enum_proposal = enum_targets.with_name("proposal.md")
    extract = _node(
        enum / "scripts" / "collect_typescript_state.mjs",
        "--findings", str(implicit), "--project-root", str(host), "--manifest", str(manifest),
        "--language", "javascript", "--output", str(enum_targets), "--proposal", str(enum_proposal), cwd=host,
    )
    assert extract.returncode == 0, extract.stderr
    enum_payload = json.loads(enum_targets.read_text(encoding="utf-8"))
    assert enum_payload["language"] == "javascript"
    assert enum_payload["status"] == "complete"
    assert "finite JSDoc authority" in enum_payload["evidence_provenance"]
    assert "checked-JavaScript closed state" in enum_proposal.read_text(encoding="utf-8")

    boundary = _copy_skill(tmp_path, "propose-boundary")
    boundary_inspection = host / "reports" / "propose-boundary" / "javascript" / "inspection.json"
    boundary_proposal = boundary_inspection.with_name("proposal.md")
    bounded = _node(
        boundary / "scripts" / "propose_typescript.mjs",
        "--target", "src/boundary", "--project-root", str(host), "--tsconfig", "jsconfig.json",
        "--language", "javascript", "--candidates", "2", "--inspection", str(boundary_inspection),
        "--proposal", str(boundary_proposal), cwd=host,
    )
    assert bounded.returncode == 0, bounded.stderr
    boundary_payload = json.loads(boundary_inspection.read_text(encoding="utf-8"))
    assert boundary_payload["language"] == "javascript"
    assert boundary_payload["status"] == "complete"
    assert boundary_payload["recommendation"] == "refactor"
    assert boundary_payload["graph"]["module_resolution"] == "complete"
    assert boundary_payload["target"]["source_files"] == 4
    assert "Checked-JavaScript" in boundary_proposal.read_text(encoding="utf-8")

    folder = _copy_skill(tmp_path, "propose-folder-reorganization")
    folder_inspection = host / "reports" / "propose-folder-reorganization" / "javascript" / "inspection.json"
    folder_proposal = folder_inspection.with_name("proposal.md")
    organized = _node(
        folder / "scripts" / "propose_typescript.mjs",
        "--parent", "src/folder", "--prefix", "billing", "--cluster-judgment", "split",
        "--project-root", str(host), "--tsconfig", "jsconfig.json", "--language", "javascript",
        "--proposal", str(folder_proposal), "--inspection", str(folder_inspection), cwd=host,
    )
    assert organized.returncode == 0, organized.stderr
    folder_payload = json.loads(folder_inspection.read_text(encoding="utf-8"))
    assert folder_payload["language"] == "javascript"
    assert folder_payload["status"] == "ready"
    assert {Path(row["current_path"]).suffix for row in folder_payload["cluster_files"]} == SUFFIXES
    assert all("billing/" in row["new_path"] for row in folder_payload["cluster_files"])
    assert "Complete resolved import-impact table" in folder_proposal.read_text(encoding="utf-8")

    findings_dir = host / "reports" / "semantic-duplication" / "javascript"
    matrix = findings_dir / "capability_matrices" / "JS-SD-0001.md"
    _write(matrix, "\n".join([
        "| Static return type | object |",
        "| Returned fields | value |",
        "| Direct call relationship | none |",
        "| Exception / async policy | synchronous |",
        "",
    ]))
    finding = {
        "skill": "find-semantic-duplication",
        "language": "javascript",
        "status": "complete",
        "confirmed": [{
            "finding_id": "JS-SD-0001", "investigation_status": "confirmed", "level": "function",
            "consolidation_shape": "share_utilities", "shared_core_description": "Two checked JavaScript functions return the same value shape.",
            "matrix_path": "capability_matrices/JS-SD-0001.md", "members": [
                {"file": "src/shadow-a.js", "qualified_name": "first", "line": 1, "end_line": 1, "caller_count": 1},
                {"file": "src/shadow-b.jsx", "qualified_name": "second", "line": 1, "end_line": 1, "caller_count": 1},
            ],
        }],
        "findings": [{"finding_id": "JS-SD-0001", "consolidation_shape": "share_utilities"}],
    }
    findings = findings_dir / "findings.json"
    _write(findings, json.dumps(finding, indent=2) + "\n")
    shadows = _copy_skill(tmp_path, "unify-shadows")
    shadow_proposal = host / "reports" / "unify-shadows" / "JS-SD-0001" / "proposal.md"
    shadow_evidence = shadow_proposal.with_name("evidence.json")
    unified = _node(
        shadows / "scripts" / "propose_typescript.mjs",
        "--findings", str(findings), "--finding-id", "JS-SD-0001", "--project-root", str(host),
        "--language", "javascript", "--proposal", str(shadow_proposal), "--evidence", str(shadow_evidence), cwd=host,
    )
    assert unified.returncode == 0, unified.stderr
    assert json.loads(shadow_evidence.read_text(encoding="utf-8"))["language"] == "javascript"
    assert "Checked-JavaScript shadow proposal" in shadow_proposal.read_text(encoding="utf-8")

    separated = json.loads(findings.read_text(encoding="utf-8"))
    separated["confirmed"][0]["consolidation_shape"] = "keep_separate_document_why"
    separated["findings"][0]["consolidation_shape"] = "keep_separate_document_why"
    keep_findings = findings.with_name("keep-separate.json")
    _write(keep_findings, json.dumps(separated, indent=2) + "\n")
    keep_proposal = host / "reports" / "unify-shadows" / "JS-SD-keep" / "proposal.md"
    kept = _node(
        shadows / "scripts" / "propose_typescript.mjs",
        "--findings", str(keep_findings), "--finding-id", "JS-SD-0001", "--project-root", str(host),
        "--language", "javascript", "--proposal", str(keep_proposal), "--evidence", str(keep_proposal.with_name("evidence.json")), cwd=host,
    )
    assert kept.returncode == 0, kept.stderr
    action = keep_proposal.read_text(encoding="utf-8").split("## Proposed action\n", 1)[1].split("\n## Caller impact", 1)[0].lower()
    assert "preserve both implementations" in action
    assert "merge" not in action and "migrat" not in action

    assert _hashes(host / "src") == before
    moved_host = tmp_path / "moved-host"
    shutil.copytree(host, moved_host, ignore=shutil.ignore_patterns("node_modules"))
    moved_install = _run("npm", "ci", "--offline", "--ignore-scripts", cwd=moved_host)
    assert moved_install.returncode == 0, moved_install.stdout + moved_install.stderr
    _apply_folder_plan(moved_host, folder_payload)
    moved_check = _run("npm", "run", "check-js", cwd=moved_host)
    assert moved_check.returncode == 0, moved_check.stdout + moved_check.stderr


def test_checked_javascript_proposal_failures_remain_explicit_and_non_mutating(tmp_path: Path) -> None:
    host = _host(tmp_path)
    before = _hashes(host / "src")
    boundary = _copy_skill(tmp_path, "propose-boundary")
    folder = _copy_skill(tmp_path, "propose-folder-reorganization")
    shadows = _copy_skill(tmp_path, "unify-shadows")
    enum = _copy_skill(tmp_path, "extract-enum")

    missing_config = _node(
        boundary / "scripts" / "propose_typescript.mjs",
        "--target", "src/boundary", "--project-root", str(host), "--tsconfig", "missing.json",
        "--language", "javascript", "--inspection", "reports/propose-boundary/missing/inspection.json",
        "--proposal", "reports/propose-boundary/missing/proposal.md", cwd=host,
    )
    assert missing_config.returncode == 2
    assert not (host / "reports" / "propose-boundary" / "missing").exists()

    partial_config = json.loads((host / "jsconfig.json").read_text(encoding="utf-8"))
    partial_config.pop("include")
    partial_config["files"] = ["src/boundary/quote.js"]
    _write(host / "partial.json", json.dumps(partial_config) + "\n")
    partial = _node(
        boundary / "scripts" / "propose_typescript.mjs",
        "--target", "src/boundary", "--project-root", str(host), "--tsconfig", "partial.json",
        "--language", "javascript", "--inspection", "reports/propose-boundary/partial/inspection.json",
        "--proposal", "reports/propose-boundary/partial/proposal.md", cwd=host,
    )
    assert partial.returncode == 0, partial.stderr
    assert json.loads((host / "reports/propose-boundary/partial/inspection.json").read_text())["status"] == "partial"

    broken = host / "src" / "broken"
    _write(broken / "bad.js", "export function broken( { return 1; }\n")
    malformed = _node(
        boundary / "scripts" / "propose_typescript.mjs",
        "--target", "src/broken", "--project-root", str(host), "--tsconfig", "jsconfig.json",
        "--language", "javascript", "--inspection", "reports/propose-boundary/broken/inspection.json",
        "--proposal", "reports/propose-boundary/broken/proposal.md", cwd=host,
    )
    assert malformed.returncode == 2
    assert "JavaScript syntax errors" in malformed.stderr

    linked = host / "src-link"
    os.symlink(host / "src/folder", linked)
    symlinked = _node(
        folder / "scripts" / "propose_typescript.mjs",
        "--parent", "src-link", "--prefix", "billing", "--cluster-judgment", "split",
        "--project-root", str(host), "--tsconfig", "jsconfig.json", "--language", "javascript",
        "--proposal", "reports/propose-folder-reorganization/link/proposal.md",
        "--inspection", "reports/propose-folder-reorganization/link/inspection.json", cwd=host,
    )
    assert symlinked.returncode == 2
    assert "symbolic link" in symlinked.stderr

    open_records = host / "reports" / "implicit-state" / "open.jsonl"
    _write(open_records, json.dumps({"classification": "open_ended_string", "literal": "queued"}) + "\n")
    open_manifest = host / "reports" / "implicit-state" / "open.json"
    _write(open_manifest, json.dumps({"language": "javascript", "status": "complete", "semantic_evidence": {"checked_javascript": True}}))
    rejected_open = _node(
        enum / "scripts" / "collect_typescript_state.mjs",
        "--findings", str(open_records), "--project-root", str(host), "--manifest", str(open_manifest),
        "--language", "javascript", "--output", "reports/extract-enum/open/targets.json",
        "--proposal", "reports/extract-enum/open/proposal.md", cwd=host,
    )
    assert rejected_open.returncode == 2
    assert not (host / "reports" / "extract-enum" / "open").exists()

    findings = host / "reports" / "semantic-duplication" / "partial" / "findings.json"
    _write(findings, json.dumps({"skill": "find-semantic-duplication", "language": "javascript", "status": "partial", "confirmed": [], "findings": []}))
    rejected_partial = _node(
        shadows / "scripts" / "propose_typescript.mjs",
        "--findings", str(findings), "--finding-id", "JS-SD-0001", "--project-root", str(host),
        "--language", "javascript", "--proposal", "reports/unify-shadows/partial/proposal.md",
        "--evidence", "reports/unify-shadows/partial/evidence.json", cwd=host,
    )
    assert rejected_partial.returncode == 2
    assert not (host / "reports" / "unify-shadows" / "partial").exists()
    assert _hashes(host / "src") == before | {"broken/bad.js": hashlib.sha256((broken / "bad.js").read_bytes()).hexdigest()}
