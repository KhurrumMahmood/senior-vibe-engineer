"""Final-boundary proof for the checked-JavaScript mutation and guard cohort."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path("/Users/khurrummahmood/Projects/engineering-skills/.venv/bin/python")  # host-ref-allow: repository-prescribed venv path
MOVE = ROOT / ".claude" / "skills" / "move-path" / "scripts" / "move_path.py"
DETECT = ROOT / ".claude" / "skills" / "find-implicit-state" / "scripts" / "detect_typescript_state.mjs"
GENERATE = ROOT / ".claude" / "skills" / "prevent-regression" / "scripts" / "generate_javascript_state_guard.mjs"
VERIFY = ROOT / ".claude" / "skills" / "prevent-regression" / "scripts" / "verify_javascript_state_guard.mjs"
SEED = ROOT / "tests" / "fixtures" / "find-dormant-typescript" / "host"


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink() and "reports" not in path.relative_to(root).parts
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
                    "allowJs": True, "checkJs": True, "jsx": "preserve", "module": "NodeNext",
                    "moduleResolution": "NodeNext", "noEmit": True, "strict": False, "target": "ES2022",
                },
                "files": ["src/old.js", "src/consumer.js", "src/panel.jsx", "src/worker.mjs", "src/legacy.cjs"],
            },
            indent=2,
        ) + "\n",
    )
    _write(
        host / "src" / "old.js",
        """/** @typedef {\"queued\" | \"done\"} DeliveryState */
/** @type {{ state: DeliveryState }} */
export const delivery = { state: "queued" };
export const core = 1;
if (delivery.state === "queued") delivery.state = "done";
""",
    )
    _write(host / "src" / "consumer.js", 'import { core } from "./old.js";\nexport const use = core;\n')
    _write(host / "src" / "panel.jsx", '// @ts-nocheck\nimport { core } from "./old.js";\nexport const Panel = () => <main>{core}</main>;\n')
    _write(host / "src" / "worker.mjs", 'export const load = () => import("./old.js");\n')
    _write(host / "src" / "legacy.cjs", '// @ts-nocheck\nconst { core } = require("./old.js");\nexports.core = core;\n')
    assert _run("npm", "run", "typecheck", cwd=host).returncode == 0
    assert _run("npm", "test", cwd=host).returncode == 0
    return host


def _plan(host: Path, *, include_config: bool = True) -> Path:
    plan = {
        "moves": [
            {"from": "src/old.js", "to": "lib/new.js"},
            {"from": "src/consumer.js", "to": "app/consumer.js"},
            {"from": "src/panel.jsx", "to": "app/panel.jsx"},
            {"from": "src/worker.mjs", "to": "app/worker.mjs"},
            {"from": "src/legacy.cjs", "to": "app/legacy.cjs"},
        ],
        "reference_scope": {"include": ["jsconfig.json"] if include_config else ["not-selected.md"]},
        "rewrite": {"exact_text_paths": "update", "code_imports": "update-javascript"},
        "javascript": {"config": "jsconfig.json"},
    }
    path = host / "moves.json"
    _write(path, json.dumps(plan, indent=2) + "\n")
    return path


def _move(
    plan: Path, host: Path, mode: str, *, script: Path = MOVE
) -> subprocess.CompletedProcess[str]:
    return _run(
        str(PYTHON), str(script), "--plan", str(plan), "--project-root", str(host),
        "--report-dir", str(host / "reports" / "move-path"), f"--{mode}", "--json", cwd=host,
    )


def test_checked_javascript_move_proves_exact_changes_native_checks_and_guard(tmp_path: Path) -> None:
    host = _host(tmp_path)
    installed = tmp_path / "installed"
    shutil.copytree(MOVE.parents[1], installed / "move-path")
    shutil.copytree(GENERATE.parents[1], installed / "prevent-regression")
    copied_move = installed / "move-path" / "scripts" / "move_path.py"
    copied_generate = installed / "prevent-regression" / "scripts" / "generate_javascript_state_guard.mjs"
    copied_verify = installed / "prevent-regression" / "scripts" / "verify_javascript_state_guard.mjs"
    typescript_before = (host / "src" / "consumer.ts").read_bytes()
    applied = _move(_plan(host), host, "apply", script=copied_move)
    assert applied.returncode == 0, applied.stderr
    report = json.loads(applied.stdout)
    assert report["javascript"]["status"] == "complete"
    assert len(report["javascript"]["exact_changes"]) == 4
    assert (host / "app" / "consumer.js").read_text() == 'import { core } from "../lib/new.js";\nexport const use = core;\n'
    assert 'import("../lib/new.js")' in (host / "app" / "worker.mjs").read_text()
    assert 'require("../lib/new.js")' in (host / "app" / "legacy.cjs").read_text()
    assert (host / "src" / "consumer.ts").read_bytes() == typescript_before
    for source in [host / "lib" / "new.js", host / "app" / "worker.mjs", host / "app" / "legacy.cjs"]:
        result = _run("node", "--check", str(source), cwd=host)
        assert result.returncode == 0, result.stderr
    assert _run("npm", "run", "typecheck", cwd=host).returncode == 0
    assert _run("npm", "test", cwd=host).returncode == 0

    findings = host / "reports" / "implicit-state" / "findings.jsonl"
    manifest = host / "reports" / "implicit-state" / "manifest.json"
    detected = _run("node", str(DETECT), "--target", "lib", "--project-root", str(host), "--tsconfig", "jsconfig.json", "--output", str(findings), "--manifest", str(manifest), "--language", "javascript", cwd=host)
    assert detected.returncode == 0, detected.stderr
    stage = host / "reports" / "prevent-regression" / "javascript-state"
    generated = _run("node", str(copied_generate), "--id", "javascript-state", "--project-root", str(host), "--config", "jsconfig.json", "--findings", str(findings), "--manifest", str(manifest), "--output-root", str(stage), cwd=host)
    assert generated.returncode == 0, generated.stdout + generated.stderr
    guard = stage / "scripts" / "lint" / "no_stringly_state_javascript.mjs"
    bad = sorted((stage / "tests" / "lint").glob("no_stringly_state_bad.*"))
    good = sorted((stage / "tests" / "lint").glob("no_stringly_state_good.*"))
    verified = _run("node", str(copied_verify), "--rule", str(guard), *sum((["--bad", str(path)] for path in bad), []), *sum((["--good", str(path)] for path in good), []), cwd=host)
    assert verified.returncode == 0, verified.stdout + verified.stderr
    assert "PASS: BAD_RC=1, GOOD_RC=0" in verified.stdout
    assert _run("node", str(guard), "--project-root", str(host), "--config", str(host / "jsconfig.json"), str(host / "lib" / "new.js"), cwd=host).returncode == 1


def test_javascript_mutation_refuses_unsafe_partial_missing_malformed_and_symlink_inputs(tmp_path: Path) -> None:
    host = _host(tmp_path)
    rollback_plan = _plan(host, include_config=False)
    baseline = _hashes(host)
    rollback = _move(rollback_plan, host, "apply")
    assert rollback.returncode != 0
    assert _hashes(host) == baseline

    missing = _host(tmp_path / "missing")
    plan = _plan(missing)
    data = json.loads(plan.read_text())
    data["javascript"]["config"] = "missing.json"
    _write(plan, json.dumps(data) + "\n")
    outcome = _move(plan, missing, "dry-run")
    assert outcome.returncode == 0
    assert json.loads(outcome.stdout)["javascript"]["status"] == "unsupported"

    malformed = _host(tmp_path / "malformed")
    _write(malformed / "src" / "broken.js", "export function broken( {\n")
    config = json.loads((malformed / "jsconfig.json").read_text())
    config["files"].append("src/broken.js")
    _write(malformed / "jsconfig.json", json.dumps(config) + "\n")
    broken = _move(_plan(malformed), malformed, "dry-run")
    assert json.loads(broken.stdout)["javascript"]["status"] == "failed"

    symlinked = _host(tmp_path / "symlink")
    external = tmp_path / "outside.js"
    _write(external, "export const outside = 1;\n")
    (symlinked / "src" / "escape.js").symlink_to(external)
    config = json.loads((symlinked / "jsconfig.json").read_text())
    config["files"].append("src/escape.js")
    _write(symlinked / "jsconfig.json", json.dumps(config) + "\n")
    linked = _move(_plan(symlinked), symlinked, "dry-run")
    assert json.loads(linked.stdout)["javascript"]["status"] == "unsupported"

    unsafe = _host(tmp_path / "unsafe")
    _write(unsafe / "src" / "consumer.js", 'const path = "./old.js"; export const load = () => import(path);\n')
    unsafe_outcome = _move(_plan(unsafe), unsafe, "dry-run")
    payload = json.loads(unsafe_outcome.stdout)
    assert payload["javascript"]["status"] == "partial"
    assert any(item["kind"] == "javascript_dynamic_import" for item in payload["blocked"])
    with pytest.raises(AssertionError):
        assert _move(_plan(unsafe), unsafe, "apply").returncode == 0
