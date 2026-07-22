"""Checked-JavaScript semantic capability contracts and failure boundaries."""
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
SKILLS = REPO_ROOT / ".claude" / "skills"
SEED = REPO_ROOT / "tests" / "fixtures" / "find-dormant-typescript" / "host"
TEST_PYTHON = Path(sys.executable)


def _run(
    *args: str,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, check=False)


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


def _prepare_javascript_git_trajectory(host: Path) -> None:
    """Make the three option-present JavaScript sites newer than the straggler."""
    assert _run("git", "init", cwd=host).returncode == 0
    assert _run("git", "config", "user.email", "fixture@example.test", cwd=host).returncode == 0
    assert _run("git", "config", "user.name", "Fixture", cwd=host).returncode == 0
    assert _run("git", "add", "src", "jsconfig.json", "package.json", "package-lock.json", cwd=host).returncode == 0
    first = _run(
        "git", "commit", "-m", "old JavaScript request shapes", cwd=host, env={
            **os.environ,
            "GIT_AUTHOR_DATE": "2025-01-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2025-01-01T00:00:00Z",
        },
    )
    assert first.returncode == 0, first.stdout + first.stderr

    calls = host / "src" / "alpha.js"
    current = calls.read_text(encoding="utf-8")
    swept = current.replace("send({ notify: true });\n", "send({ notify: true }); // swept\n", 3)
    assert swept != current
    calls.write_text(swept, encoding="utf-8")
    assert _run("git", "add", "src/alpha.js", cwd=host).returncode == 0
    second = _run(
        "git", "commit", "-m", "sweep JavaScript notify option", cwd=host, env={
            **os.environ,
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
        },
    )
    assert second.returncode == 0, second.stdout + second.stderr


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
    assert "checked JavaScript v1" in (sweep_dir / "findings.md").read_text(encoding="utf-8")

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


def test_checked_javascript_gated_candidate_reaches_scout_verdict_and_triage(tmp_path: Path) -> None:
    host = _host(tmp_path)
    _prepare_javascript_git_trajectory(host)
    before = _hashes(host / "src")
    report_dir = host / "reports" / "find-incomplete-sweep" / "javascript-gated"

    detected = _node(
        SKILLS / "find-incomplete-sweep" / "scripts" / "detect_typescript_sweep.mjs",
        "--target", "src", "--project-root", str(host), "--tsconfig", "jsconfig.json",
        "--report-dir", str(report_dir), "--language", "javascript", cwd=host,
    )
    assert detected.returncode == 0, detected.stdout + detected.stderr
    manifest = json.loads((report_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["language"] == "javascript"
    assert manifest["analyzer"] == "typescript-compiler-api-checked-javascript"
    assert len(manifest["findings"]) == 1
    assert manifest["findings"][0]["gated_in"] is True

    scouted = _run(
        str(TEST_PYTHON), str(SKILLS / "find-incomplete-sweep" / "scripts" / "scout.py"),
        "--scan-dir", str(report_dir), "--project-root", str(host), cwd=host,
    )
    assert scouted.returncode == 0, scouted.stdout + scouted.stderr
    packets = json.loads((report_dir / "scout_packets.json").read_text(encoding="utf-8"))
    assert packets["language"] == "javascript"
    assert packets["packet_count"] == 1
    assert packets["packets"][0]["callee"] == "send"
    assert packets["packets"][0]["present_sites"]

    (report_dir / "scout_verdicts.json").write_text(json.dumps({
        "scan_dir": str(report_dir),
        "verdicts": [{
            "id": packets["packets"][0]["id"],
            "verdict": "forgotten",
            "rationale": "The three newer checked-JavaScript siblings consistently override notify.",
            "completion": "add `notify: true` to the straggler options object",
        }],
    }, indent=2), encoding="utf-8")
    triaged = _run(
        str(TEST_PYTHON), str(SKILLS / "find-incomplete-sweep" / "scripts" / "triage.py"),
        "--scan-dir", str(report_dir), cwd=host,
    )
    assert triaged.returncode == 0, triaged.stdout + triaged.stderr
    rendered = (report_dir / "triaged.md").read_text(encoding="utf-8")
    assert "## Forgotten (1)" in rendered
    assert "/fix-workflow cluster:SW-01" in rendered
    assert _hashes(host / "src") == before


def test_checked_javascript_documented_commands_resolve_each_installed_layout(tmp_path: Path) -> None:
    command_specs = {
        "find-dormant": ("javascript-scan", "reports/find-dormant/javascript-command/findings.json"),
        "find-incomplete-sweep": ("javascript-scan", "reports/find-incomplete-sweep/javascript-command/scout_packets.json"),
        "find-semantic-duplication": ("javascript-scan", "reports/semantic-duplication/javascript-command/findings.json"),
        "map-subsystem": ("javascript-map", "reports/map/javascript-command/javascript-map.json"),
        "find-implicit-state": ("javascript-state", "reports/implicit-state/javascript.manifest.json"),
    }

    for layout in (".agents/skills/on-demand", ".agents/skills", ".claude/skills"):
        host = _host(tmp_path / layout.replace("/", "-"))
        skill_root = host / layout
        skill_root.mkdir(parents=True)
        for skill_name in command_specs:
            shutil.copytree(SKILLS / skill_name, skill_root / skill_name)

        for skill_name, (command_name, expected_output) in command_specs.items():
            command = _documented_command(skill_root / skill_name, command_name)
            result = _run(
                "bash", "-c", command, cwd=host, env={
                    **os.environ,
                    "TARGET": "src",
                    "MAP_TARGET": "src",
                    "JSCONFIG": "jsconfig.json",
                    "REPORT_NAME": "javascript-command",
                    "MAP_NAME": "javascript-command",
                    "SKILL_ROOT": "/must-not-be-used",
                    "PATH": f"{TEST_PYTHON.parent}{os.pathsep}{os.environ['PATH']}",
                },
            )
            assert result.returncode == 0, f"{layout}/{skill_name}: {result.stdout}{result.stderr}"
            assert (host / expected_output).is_file(), f"{layout}/{skill_name} did not create {expected_output}"
