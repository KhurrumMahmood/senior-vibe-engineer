"""Checked-JavaScript semantic capability contracts and failure boundaries."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / ".claude" / "skills"
SEED = REPO_ROOT / "tests" / "fixtures" / "find-dormant-typescript" / "host"


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


def _host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(SEED, host)
    install = _run("npm", "ci", "--offline", "--ignore-scripts", cwd=host)
    assert install.returncode == 0, install.stdout + install.stderr
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
                },
                "files": [
                    "src/alpha.js", "src/panel.jsx", "src/worker.mjs",
                    "src/legacy.cjs", "src/common.cjs", "src/ignored.js",
                ],
            },
            indent=2,
        ) + "\n",
    )
    _write(
        host / "src" / "alpha.js",
        """/** @typedef {\"queued\" | \"sent\"} DeliveryState */
/** @type {{ status: DeliveryState }} */
export const delivery = { status: \"queued\" };
export const shipment = { status: \"sent\" };
export const unrelated = 1;

export function send({ notify = false } = {}) {
  return { total: notify ? 1 : 0, status: \"sent\" };
}

export function sendByLoop({ notify = false } = {}) {
  let total = 0;
  if (notify) total += 1;
  return { total, status: \"sent\" };
}

send({ notify: true });
send({ notify: true });
send({ notify: true });
send({});

export function used() { return send({ notify: true }); }
function dormant() { return 1; }
function dynamicEntry() { return 2; }
const dynamicName = \"dynamicEntry\";
void dynamicName;
const metadata = { delivery: \"delivery\" }; // delivery remains retired prose here
void metadata;
function shadow() { const delivery = 0; return delivery; }
void shadow;

if (delivery.status === \"queued\") delivery.status = \"sent\";
const open = { status: \"queued\" };
if (open.status === \"queued\") open.status = \"sent\";
""",
    )
    _write(host / "src" / "panel.jsx", "// @ts-nocheck\nexport function Panel() { return <main />; }\n")
    _write(host / "src" / "worker.mjs", "import { send, unrelated as delivery } from \"./alpha.js\";\nvoid delivery;\nexport const worker = () => send({ notify: true });\n")
    _write(host / "src" / "common.cjs", "exports.value = 1;\n")
    _write(host / "src" / "legacy.cjs", "// @ts-ignore\nconst common = require(\"./common.cjs\");\nconst dynamicName = \"./common.cjs\";\n// @ts-ignore\nconst dynamic = require(dynamicName);\nvoid dynamic;\nexports.value = common.value;\n")
    _write(host / "src" / "ignored.js", "export const ignored = true;\n")
    check = _run("npm", "run", "typecheck", cwd=host)
    assert check.returncode == 0, check.stdout + check.stderr
    native = _run("npm", "test", cwd=host)
    assert native.returncode == 0, native.stdout + native.stderr
    return host


def _node(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return _run("node", str(script), *args, cwd=cwd)


def test_checked_javascript_semantic_outputs_are_final_read_only_and_cover_suffixes(tmp_path: Path) -> None:
    host = _host(tmp_path)
    before = _hashes(host / "src")
    config = "jsconfig.json"

    dormant_dir = host / "reports" / "find-dormant" / "javascript"
    dormant = _node(
        SKILLS / "find-dormant" / "scripts" / "detect_typescript_dormant.mjs",
        "--target", "src", "--project-root", str(host), "--tsconfig", config,
        "--report-dir", str(dormant_dir), "--language", "javascript", cwd=host,
    )
    assert dormant.returncode == 0, dormant.stderr
    dormant_payload = json.loads((dormant_dir / "findings.json").read_text())
    assert dormant_payload["language"] == "javascript"
    assert dormant_payload["semantic_evidence"]["checked_javascript"] is True
    assert {entry["name"] for entry in dormant_payload["candidates"]} >= {"dormant"}
    assert {entry["name"] for entry in dormant_payload["uncertain_symbols"]} >= {"dynamicEntry"}
    assert all(entry["name"] != "legacy" for entry in dormant_payload["candidates"])

    state_output = host / "reports" / "implicit-state" / "javascript.jsonl"
    state_manifest = host / "reports" / "implicit-state" / "javascript.json"
    state = _node(
        SKILLS / "find-implicit-state" / "scripts" / "detect_typescript_state.mjs",
        "--target", "src", "--project-root", str(host), "--tsconfig", config,
        "--output", str(state_output), "--manifest", str(state_manifest), "--language", "javascript", cwd=host,
    )
    assert state.returncode == 0, state.stderr
    records = [json.loads(line) for line in state_output.read_text().splitlines()]
    assert any(record["classification"] == "first_party_state_operation" for record in records)
    assert any(record["classification"] == "open_ended_string" for record in records)
    assert json.loads(state_manifest.read_text())["semantic_evidence"]["checked_javascript"] is True

    sweep_dir = host / "reports" / "find-incomplete-sweep" / "javascript"
    sweep = _node(
        SKILLS / "find-incomplete-sweep" / "scripts" / "detect_typescript_sweep.mjs",
        "--target", "src", "--project-root", str(host), "--tsconfig", config,
        "--report-dir", str(sweep_dir), "--min-callsites", "4", "--min-present", "3",
        "--language", "javascript", "--no-gate", cwd=host,
    )
    assert sweep.returncode == 0, sweep.stderr
    sweep_payload = json.loads((sweep_dir / "manifest.json").read_text())
    assert sweep_payload["language"] == "javascript"
    assert any(
        finding["callee"] == "send" and finding["kwarg"] == "notify"
        for finding in [*sweep_payload["findings"], *sweep_payload["gated_out"]]
    )
    assert sweep_payload["semantic_evidence"]["compiler_inferred"]["resolved_direct_calls"] >= 4

    duplication_dir = host / "reports" / "semantic-duplication" / "javascript"
    duplication = _node(
        SKILLS / "find-semantic-duplication" / "scripts" / "detect_typescript.mjs",
        "--target", "src", "--project-root", str(host), "--tsconfig", config,
        "--report-dir", str(duplication_dir), "--language", "javascript", cwd=host,
    )
    assert duplication.returncode == 0, duplication.stderr
    duplication_payload = json.loads((duplication_dir / "findings.json").read_text())
    assert duplication_payload["language"] == "javascript"
    assert duplication_payload["semantic_evidence"]["checked_javascript"] is True
    assert all("caller_callee" != finding.get("reason_code") for finding in duplication_payload["findings"])

    map_output = ".claude/docs/subsystems/javascript-semantic.md"
    map_evidence = "reports/map/javascript-semantic.json"
    mapped = _node(
        SKILLS / "map-subsystem" / "scripts" / "map_typescript.mjs",
        "--target", "src", "--project-root", str(host), "--tsconfig", config,
        "--output", map_output, "--evidence", map_evidence, "--language", "javascript", cwd=host,
    )
    assert mapped.returncode == 0, mapped.stderr
    map_payload = json.loads((host / map_evidence).read_text())
    assert map_payload["language"] == "javascript"
    assert {Path(row["file"]).suffix for row in map_payload["files"]} == {".js", ".jsx", ".mjs", ".cjs"}
    assert any(edge["kind"] == "literal_require" for edge in map_payload["outbound_imports"])
    assert any(edge["kind"] == "dynamic_require" for edge in map_payload["unresolved_imports"])
    assert map_payload["status"] == "partial"

    rename_output = host / "reports" / "rename-concept" / "javascript-identifiers.json"
    rename = _node(
        SKILLS / "rename-concept" / "scripts" / "typescript_identifier_evidence.mjs",
        "--project-root", str(host), "--old-terms", json.dumps(["delivery"]),
        "--new-terms", json.dumps(["shipment"]), "--sources", json.dumps(["src/alpha.js", "src/panel.jsx", "src/worker.mjs", "src/legacy.cjs"]),
        "--language", "javascript", "--config", config, "--output", str(rename_output), cwd=host,
    )
    assert rename.returncode == 0, rename.stderr
    rename_payload = json.loads(rename_output.read_text())
    assert rename_payload["status"] == "resolved"
    assert rename_payload["semantic_evidence"]["checked_javascript"] is True
    assert {item["classification"] for item in rename_payload["occurrences"]} >= {
        "old_concept_symbol", "new_concept_symbol", "import_alias", "shadowed_local", "property_key",
    }
    assert rename_payload["textual_boundaries"]
    assert _hashes(host / "src") == before


def test_checked_javascript_never_turns_missing_config_tool_syntax_exclusion_or_symlink_into_clean(tmp_path: Path) -> None:
    host = _host(tmp_path)
    script = SKILLS / "find-dormant" / "scripts" / "detect_typescript_dormant.mjs"
    missing_config = _node(
        script, "--target", "src", "--project-root", str(host), "--tsconfig", "missing.json",
        "--report-dir", "reports/find-dormant/missing-config", "--language", "javascript", cwd=host,
    )
    assert missing_config.returncode == 2
    assert "unsupported" in missing_config.stderr

    no_tool = tmp_path / "no-tool"
    shutil.copytree(host, no_tool, ignore=shutil.ignore_patterns("node_modules"))
    tool_missing = _node(
        script, "--target", "src", "--project-root", str(no_tool), "--tsconfig", "jsconfig.json",
        "--report-dir", "reports/find-dormant/tool-missing", "--language", "javascript", cwd=no_tool,
    )
    assert tool_missing.returncode == 2
    assert "project-local TypeScript package is unavailable" in tool_missing.stderr

    config = json.loads((host / "jsconfig.json").read_text())
    config["files"] = ["src/alpha.js"]
    (host / "jsconfig.json").write_text(json.dumps(config) + "\n", encoding="utf-8")
    partial = _node(
        script, "--target", "src", "--project-root", str(host), "--tsconfig", "jsconfig.json",
        "--report-dir", "reports/find-dormant/partial", "--language", "javascript", cwd=host,
    )
    assert partial.returncode == 0, partial.stderr
    partial_payload = json.loads((host / "reports/find-dormant/partial/findings.json").read_text())
    assert partial_payload["status"] == "partial"
    assert partial_payload["uncovered_files"]

    _write(host / "src" / "broken.js", "export function broken() {\n")
    config["files"].append("src/broken.js")
    (host / "jsconfig.json").write_text(json.dumps(config) + "\n", encoding="utf-8")
    malformed = _node(
        script, "--target", "src", "--project-root", str(host), "--tsconfig", "jsconfig.json",
        "--report-dir", "reports/find-dormant/malformed", "--language", "javascript", cwd=host,
    )
    assert malformed.returncode == 2
    assert "JavaScript syntax errors" in malformed.stderr

    external = tmp_path / "external.js"
    external.write_text("export const escape = 1;\n", encoding="utf-8")
    (host / "src" / "escape.js").symlink_to(external)
    symlink = _node(
        script, "--target", "src/escape.js", "--project-root", str(host), "--tsconfig", "jsconfig.json",
        "--report-dir", "reports/find-dormant/symlink", "--language", "javascript", cwd=host,
    )
    assert symlink.returncode == 2
    assert "symbolic link" in symlink.stderr


def test_checked_javascript_copied_skill_keeps_family_local_compiler_closure(tmp_path: Path) -> None:
    host = _host(tmp_path)
    installed = tmp_path / "installed-find-dormant"
    shutil.copytree(SKILLS / "find-dormant", installed)
    result = _node(
        installed / "scripts" / "detect_typescript_dormant.mjs",
        "--target", "src", "--project-root", str(host), "--tsconfig", "jsconfig.json",
        "--report-dir", "reports/find-dormant/copied", "--language", "javascript", cwd=host,
    )
    assert result.returncode == 0, result.stderr
    assert (host / "reports/find-dormant/copied/findings.json").is_file()
    assert str(REPO_ROOT) not in (installed / "scripts" / "detect_typescript_dormant.mjs").read_text(encoding="utf-8")
