"""Capability contracts for the JavaScript lexical cohort's final artifacts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / ".claude" / "skills"
PYTHON = Path(sys.executable)


def _run(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(PYTHON), "-I", "-S", str(script), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def _write(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def _hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def _javascript_host(root: Path) -> None:
    _write(root / "package.json", '{"name":"mixed-host","scripts":{"test":"node test"}}\n')
    _write(root / "src" / "alpha.js", "export const alpha = 1;\n")
    _write(root / "src" / "panel.jsx", "export function Panel() { return null; }\n")
    _write(root / "src" / "worker.mjs", "export const worker = 1;\n")
    _write(root / "src" / "legacy.cjs", "exports.legacy = 1;\n")
    _write(root / "src" / "typed.ts", "export const typed = 1;\n")
    _write(root / "src" / "generated" / "ignored.js", "export const ignored = 1;\n")
    _write(root / "src" / "vendor" / "ignored.jsx", "export const ignored = 1;\n")
    _write(root / "src" / "tests" / "ignored.mjs", "export const ignored = 1;\n")
    _write(root / "src" / "ignored.min.cjs", "exports.ignored = 1;\n")


def test_adapt_project_counts_first_party_javascript_without_framework_inference(tmp_path: Path) -> None:
    host = tmp_path / "host"
    _javascript_host(host)
    external = tmp_path / "external.js"
    external.write_text("export const escape = 1;\n", encoding="utf-8")
    (host / "src" / "escape.js").symlink_to(external)
    before = _hashes(host)
    artifacts = tmp_path / "artifacts"

    result = _run(
        SKILLS / "adapt-project" / "scripts" / "discover.py",
        "--project-root", str(host), "--artifact-root", str(artifacts),
        "--timestamp", "javascript", "--no-host-write", cwd=host,
    )

    assert result.returncode == 0, result.stderr
    scan = Path(result.stdout.strip())
    adapter = json.loads((scan / "adapter.json").read_text(encoding="utf-8"))
    src = next(row for row in adapter["source_roots"] if row["path"] == "src")
    assert src["javascript_files"] == 4
    assert src["javascript_file_kinds"] == {"cjs": 1, "js": 1, "jsx": 1, "mjs": 1}
    assert src["typescript_files"] == 1
    assert adapter["stack"]["languages"] == ["typescript", "javascript"]
    assert adapter["stack"]["frameworks"] == []
    assert "JavaScript: 4" in (scan / "report.md").read_text(encoding="utf-8")
    evidence = _run(SKILLS / "adapt-project" / "scripts" / "check_evidence.py", "--scan-dir", str(scan), cwd=host)
    assert evidence.returncode == 0, evidence.stderr
    assert _hashes(host) == before


def test_explain_code_javascript_outputs_unexplained_and_syntax_error(tmp_path: Path) -> None:
    host = tmp_path / "host"
    _write(host / "src" / "main.js", """\
/** Build a value. */
export function build(value) { return value ? value : 0; }
export class Widget {}
export const first = 1, second = 2;
export { first as legacyFirst };
export * from "./barrel.js";
export default build;
""")
    _write(host / "src" / "view.jsx", "export function View() { return <main />; }\n")
    _write(host / "src" / "worker.mjs", "export const worker = 1;\n")
    _write(host / "src" / "legacy.cjs", "exports.run = function run() { return 1; };\nmodule.exports = loadDynamic();\n")
    _write(host / "src" / "generated" / "skip.js", "export const skip = 1;\n")
    _write(host / "src" / "vendor" / "skip.jsx", "export const skip = 1;\n")
    _write(host / "src" / "tests" / "skip.mjs", "export const skip = 1;\n")
    _write(host / "src" / "skip.min.cjs", "exports.skip = 1;\n")
    before = _hashes(host / "src")
    output = host / "reports" / "targets.json"

    result = _run(
        SKILLS / "explain-code" / "scripts" / "inventory_symbols.py",
        "--target", "src", "--repo-root", str(host), "--output", str(output), cwd=host,
    )

    assert result.returncode == 0, result.stderr
    targets = json.loads(output.read_text(encoding="utf-8"))
    assert targets["language"] == "javascript"
    assert {target["symbol"] for target in targets["targets"]} >= {
        "build", "Widget", "first", "second", "View", "worker", "run",
    }
    assert {Path(target["file"]).suffix for target in targets["targets"]} == {".js", ".jsx", ".mjs", ".cjs"}
    assert {entry["kind"] for entry in targets["unexplained"]} >= {
        "unresolved-export", "unresolved-commonjs-export",
    }
    assert all("skip" not in target["file"] for target in targets["targets"])
    assert _hashes(host / "src") == before

    broken = host / "broken.js"
    broken.write_text("export function broken() {\n", encoding="utf-8")
    malformed = host / "reports" / "broken-targets.json"
    invalid = _run(
        SKILLS / "explain-code" / "scripts" / "inventory_symbols.py",
        "--target", str(broken), "--repo-root", str(host), "--output", str(malformed), cwd=host,
    )
    assert invalid.returncode == 1
    assert "syntax-error" in invalid.stderr
    assert not malformed.exists()


def test_comment_and_concept_lexical_reports_cover_all_javascript_suffixes(tmp_path: Path) -> None:
    host = tmp_path / "host"
    for suffix in ("js", "jsx", "mjs", "cjs"):
        _write(host / "src" / f"bad.{suffix}", "// Get the deprecated status\nasync function handle() {}\n")
    for tree in ("generated", "vendor", "tests"):
        _write(host / "src" / tree / "ignored.js", "// Get the deprecated status\nasync function handle() {}\n")
    _write(host / "src" / "ignored.min.js", "// Get the deprecated status\nasync function handle() {}\n")
    external = tmp_path / "external.js"
    external.write_text("// Get the deprecated status\nasync function handle() {}\n", encoding="utf-8")
    (host / "src" / "escape.js").symlink_to(external)
    before = _hashes(host / "src")
    comment_jsonl = host / "reports" / "comment.jsonl"
    detect = _run(
        SKILLS / "find-comment-drift" / "scripts" / "detect.py",
        "--project-root", str(host), "--output", str(comment_jsonl), "src", cwd=host,
    )
    assert detect.returncode == 0, detect.stderr
    comment_records = [json.loads(line) for line in comment_jsonl.read_text().splitlines()]
    assert {Path(record["file"]).suffix for record in comment_records} == {".js", ".jsx", ".mjs", ".cjs"}
    rendered = _run(
        SKILLS / "find-comment-drift" / "scripts" / "report.py",
        str(comment_jsonl), "--output", str(host / "reports" / "comment.md"), "--target", "src", cwd=host,
    )
    assert rendered.returncode == 0, rendered.stderr
    assert json.loads((host / "reports" / "findings.json").read_text())["summary"]["findings_total"] == len(comment_records)

    glossary = {
        "concepts": [{"name": "current status", "avoid": ["deprecated status"]}],
        "flagged_ambiguities": [],
    }
    _write(host / ".claude" / "contracts" / "concepts.yaml", json.dumps(glossary))
    _write(host / "src" / "negative.js", "const deprecatedStatuses = [];\n")
    concept_jsonl = host / "reports" / "concept.jsonl"
    concept_report = host / "reports" / "concept.md"
    concept = _run(
        SKILLS / "find-concept-divergence" / "scripts" / "scan.py",
        "--project-root", str(host), "--output", str(concept_jsonl), "--report", str(concept_report), "src", cwd=host,
    )
    assert concept.returncode == 0, concept.stderr
    concept_records = [json.loads(line) for line in concept_jsonl.read_text().splitlines()]
    assert {Path(record["file"]).suffix for record in concept_records} == {".js", ".jsx", ".mjs", ".cjs"}
    assert all(record["file"].startswith("src/bad.") for record in concept_records)
    assert _hashes(host / "src") == before | {"negative.js": hashlib.sha256((host / "src" / "negative.js").read_bytes()).hexdigest()}


def _write_fake_jscpd(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "out = pathlib.Path(args[args.index('--output') + 1])\n"
        "stage = pathlib.Path(args[-1])\n"
        "(out / 'staged.json').write_text(json.dumps(sorted(p.name for p in stage.rglob('*') if p.is_file())))\n"
        "payload = {'duplicates': [{'lines': 3, 'firstFile': {'name': 'clone-a.js', 'start': 2, 'end': 4}, 'secondFile': {'name': 'clone-b.jsx', 'start': 2, 'end': 4}}]}\n"
        "(out / 'jscpd-report.json').write_text(json.dumps(payload))\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_javascript_duplication_final_artifact_and_failure_outcomes(tmp_path: Path) -> None:
    host = tmp_path / "host"
    _write(host / "src" / "clone-a.js", "export function first() {\n  const value = 1;\n  return value + 2;\n}\n")
    _write(host / "src" / "clone-b.jsx", "export function second() {\n  const value = 1;\n  return value + 2;\n}\n")
    _write(host / "src" / "third.mjs", "export const third = () => { return 3; };\n")
    _write(host / "src" / "fourth.cjs", "exports.fourth = () => { return 4; };\n")
    _write(host / "src" / "vendor" / "ignored.js", "export const ignored = 1;\n")
    _write(host / "src" / "ignored.min.js", "export const ignored = 1;\n")
    before = _hashes(host / "src")
    binary = host / "node_modules" / ".bin" / "jscpd"
    _write_fake_jscpd(binary)
    report_dir = host / "reports" / "duplication"
    run = _run(
        SKILLS / "find-duplication" / "scripts" / "run_jscpd_javascript.py",
        "--target", str(host / "src"), "--project-root", str(host), "--output", str(report_dir / "jscpd"),
        "--jscpd-bin", str(binary), cwd=host,
    )
    assert run.returncode == 0, run.stderr
    assert json.loads((report_dir / "jscpd" / "staged.json").read_text()) == ["clone-a.js", "clone-b.jsx", "fourth.cjs", "third.mjs"]
    collapse = _run(
        SKILLS / "find-duplication" / "scripts" / "collapse_javascript.py",
        "--jscpd-report", str(report_dir / "jscpd" / "jscpd-report.json"), "--target", str(host / "src"),
        "--project-root", str(host), "--output", str(report_dir / "collapsed.json"), cwd=host,
    )
    assert collapse.returncode == 0, collapse.stderr
    rank = _run(SKILLS / "find-duplication" / "scripts" / "rank.py", "--input", str(report_dir / "collapsed.json"), "--output", str(report_dir / "ranked.json"), cwd=host)
    assert rank.returncode == 0, rank.stderr
    final = _run(
        SKILLS / "find-duplication" / "scripts" / "report.py", "--input", str(report_dir / "ranked.json"),
        "--output-md", str(report_dir / "triage.md"), "--output-json", str(report_dir / "findings.json"), cwd=host,
    )
    assert final.returncode == 0, final.stderr
    findings = json.loads((report_dir / "findings.json").read_text())
    assert findings["scan_meta"]["language"] == "javascript"
    assert findings["findings"][0]["source"] == "jscpd-javascript"
    assert "Do not consolidate automatically" in (report_dir / "triage.md").read_text()
    assert _hashes(host / "src") == before

    missing = _run(
        SKILLS / "find-duplication" / "scripts" / "run_jscpd_javascript.py",
        "--target", str(host / "src"), "--project-root", str(host), "--output", str(host / "reports" / "missing"),
        "--jscpd-bin", str(host / "no-tool"), cwd=host,
    )
    assert missing.returncode == 3
    assert json.loads((host / "reports" / "missing" / "run.json").read_text())["status"] == "tool-missing"
    only_excluded = host / "only-excluded"
    _write(only_excluded / "vendor" / "no.js", "export const no = 1;\n")
    partial = _run(
        SKILLS / "find-duplication" / "scripts" / "run_jscpd_javascript.py",
        "--target", str(only_excluded), "--project-root", str(host), "--output", str(host / "reports" / "partial"),
        "--jscpd-bin", str(binary), cwd=host,
    )
    assert partial.returncode == 2
    assert json.loads((host / "reports" / "partial" / "run.json").read_text())["status"] == "partial"

    broken = host / "src" / "broken.mjs"
    broken.write_text("export function broken() {\n", encoding="utf-8")
    malformed_report = host / "reports" / "malformed-input.json"
    malformed_report.write_text(json.dumps({"duplicates": [{
        "lines": 1,
        "firstFile": {"name": str(broken), "start": 1, "end": 1},
        "secondFile": {"name": str(host / "src" / "clone-a.js"), "start": 2, "end": 2},
    }]}), encoding="utf-8")
    malformed = _run(
        SKILLS / "find-duplication" / "scripts" / "collapse_javascript.py",
        "--jscpd-report", str(malformed_report), "--target", str(host / "src"),
        "--project-root", str(host), "--output", str(host / "reports" / "malformed.json"), cwd=host,
    )
    assert malformed.returncode == 1
    assert "syntax-error" in malformed.stderr
    assert not (host / "reports" / "malformed.json").exists()


def test_folder_topology_javascript_uses_report_language_boundary(tmp_path: Path) -> None:
    host = tmp_path / "host"
    for name in ("billing-parser.js", "billing_validator.jsx", "billing-types.mjs", "billing-client.cjs"):
        _write(host / "src" / name, "export const value = 1;\n")
    for name in ("index.js", "billing.test.js", "billing.spec.jsx", "billing.min.mjs"):
        _write(host / "src" / name, "export const ignored = 1;\n")
    for tree in ("tests", "generated", "vendor"):
        _write(host / "src" / tree / "billing-extra.js", "export const ignored = 1;\n")
    external = tmp_path / "external"
    _write(external / "billing-extra.js", "export const ignored = 1;\n")
    (host / "src" / "linked").symlink_to(external, target_is_directory=True)
    before = _hashes(host / "src")
    detections = host / "reports" / "detections.jsonl"
    detect = _run(
        SKILLS / "find-folder-topology-drift" / "scripts" / "detect.py",
        "--project-root", str(host), "--javascript-root", "src", "--output", str(detections), cwd=host,
    )
    assert detect.returncode == 0, detect.stderr
    records = [json.loads(line) for line in detections.read_text().splitlines()]
    assert len(records) == 1
    assert records[0]["language"] == "javascript"
    assert {Path(path).suffix for path in records[0]["files"]} == {".js", ".jsx", ".mjs", ".cjs"}
    report = _run(
        SKILLS / "find-folder-topology-drift" / "scripts" / "report.py",
        "--detections", str(detections), "--output-md", str(host / "reports" / "report.md"),
        "--output-json", str(host / "reports" / "findings.json"), "--target", "src", "--language", "javascript", cwd=host,
    )
    assert report.returncode == 0, report.stderr
    findings = json.loads((host / "reports" / "findings.json").read_text())
    assert findings["scan_meta"]["language"] == "javascript"
    assert "**Language:** `javascript`" in (host / "reports" / "report.md").read_text()

    for name in ("billing-parser.ts", "billing_validator.ts", "billing-types.ts"):
        _write(host / "typed" / name, "export const value = 1;\n")
    mixed_detections = host / "reports" / "mixed.jsonl"
    mixed = _run(
        SKILLS / "find-folder-topology-drift" / "scripts" / "detect.py",
        "--project-root", str(host), "--javascript-root", "src", "--typescript-root", "typed",
        "--output", str(mixed_detections), cwd=host,
    )
    assert mixed.returncode == 0, mixed.stderr
    assert {json.loads(line).get("language") for line in mixed_detections.read_text().splitlines()} == {
        "javascript", "typescript",
    }
    mixed_report = _run(
        SKILLS / "find-folder-topology-drift" / "scripts" / "report.py",
        "--detections", str(mixed_detections), "--output-md", str(host / "reports" / "mixed.md"),
        "--output-json", str(host / "reports" / "mixed.json"), "--target", "src + typed", "--language", "mixed", cwd=host,
    )
    assert mixed_report.returncode == 0, mixed_report.stderr
    assert json.loads((host / "reports" / "mixed.json").read_text())["scan_meta"]["language"] == "mixed"
    assert _hashes(host / "src") == before
