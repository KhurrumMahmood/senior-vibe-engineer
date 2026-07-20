"""Final-outcome JavaScript proof for the four syntax-level skills."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / ".claude" / "skills"
SEED = REPO_ROOT / "tests" / "fixtures" / "audit-decisions-typescript" / "host"
SUFFIXES = ("js", "jsx", "mjs", "cjs")


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def _host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(SEED, host)
    install = _run("npm", "ci", "--offline", "--ignore-scripts", cwd=host)
    assert install.returncode == 0, install.stdout + install.stderr
    return host


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file() and "reports" not in path.parts
    }


def _hot_function(name: str, *, jsx: bool = False, commonjs: bool = False) -> str:
    branches = "\n".join(f"  if (value > {index}) value -= 1;" for index in range(18))
    returned = "<div>{value}</div>" if jsx else "value"
    prefix = "" if commonjs else "export "
    exported = f"\nmodule.exports = {{ {name} }};" if commonjs else ""
    return f"{prefix}function {name}(value) {{\n{branches}\n  return {returned};\n}}{exported}\n"


def _omnibus_source(*, commonjs: bool = False, jsx: bool = False) -> str:
    names = [
        "invoiceCreate", "invoiceUpdate", "shipmentCreate", "shipmentUpdate",
        "customerCreate", "customerUpdate", "inventoryCreate", "inventoryUpdate",
    ]
    declarations = []
    for name in names:
        returned = "<span />" if jsx and name == names[0] else "null"
        prefix = "" if commonjs else "export "
        declarations.append(f"{prefix}function {name}() {{ return {returned}; }}")
    if commonjs:
        declarations.append("module.exports = { " + ", ".join(names) + " };")
    return "\n".join(declarations) + "\n"


def test_javascript_syntax_cohort_reaches_final_artifacts_for_all_suffixes(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    for suffix in SUFFIXES:
        _write(
            host / "audit" / f"references.{suffix}",
            "// decision:0001\nconst prose = 'decision:9999';\n",
        )
        _write(
            host / "syntax" / "complexity" / f"hot.{suffix}",
            _hot_function(
                f"hot{suffix.upper()}",
                jsx=suffix == "jsx",
                commonjs=suffix == "cjs",
            ),
        )
        _write(
            host / "syntax" / "omnibus" / f"domains.{suffix}",
            _omnibus_source(commonjs=suffix == "cjs", jsx=suffix == "jsx"),
        )
        _write(
            host / "syntax" / "standard" / f"parse.{suffix}",
            ("" if suffix == "cjs" else "export ")
            + "function unsafe(value) { return JSON.parse(value); }\n"
            + ("" if suffix == "cjs" else "export ")
            + "function safe(value) { try { return JSON.parse(value); } catch { return null; } }\n"
            + ("module.exports = { unsafe, safe };\n" if suffix == "cjs" else ""),
        )
    _write(host / "syntax" / "complexity" / "ignored.test.js", _hot_function("ignored"))
    _write(host / "syntax" / "omnibus" / "ignored.min.js", _omnibus_source())
    jsconfig = host / "jsconfig.syntax.json"
    jsconfig.write_text(json.dumps({
        "compilerOptions": {
            "allowJs": True,
            "checkJs": False,
            "jsx": "preserve",
            "module": "NodeNext",
            "moduleResolution": "NodeNext",
            "noEmit": True,
            "target": "ES2022",
        },
        "include": ["audit/**/*", "syntax/**/*"],
    }), encoding="utf-8")
    package_json = host / "package.json"
    package = json.loads(package_json.read_text(encoding="utf-8"))
    package.setdefault("scripts", {})["check-js"] = (
        "tsc --project jsconfig.syntax.json"
    )
    package_json.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    native = _run(
        "npm", "run", "check-js",
        cwd=host,
    )
    assert native.returncode == 0, native.stdout + native.stderr
    before = _hashes(host)

    audit_out = host / "reports" / "audit-decisions" / "javascript"
    audit = _run(
        sys.executable,
        str(SKILLS / "audit-decisions" / "scripts" / "audit.py"),
        "--project-root", str(host),
        "--target", "audit",
        "--output-dir", str(audit_out),
        cwd=host,
    )
    assert audit.returncode in {0, 1}, audit.stdout + audit.stderr
    raw = json.loads((audit_out / "raw-drift.json").read_text(encoding="utf-8"))
    js_refs = [row for row in raw["references"] if row["language"] == "javascript"]
    assert {row["path"] for row in js_refs} == {
        f"audit/references.{suffix}" for suffix in SUFFIXES
    }
    assert {row["id"] for row in js_refs} == {"0001"}

    complexity = _run(
        sys.executable,
        str(SKILLS / "find-complexity-hotspots" / "scripts" / "run.py"),
        "--project-root", str(host),
        "--language", "javascript",
        "--skip-effectiveness-log",
        "syntax/complexity",
        cwd=host,
    )
    assert complexity.returncode == 0, complexity.stdout + complexity.stderr
    complexity_dir = (host / "reports" / "find-complexity-hotspots" / "latest").resolve()
    findings = json.loads((complexity_dir / "findings.json").read_text(encoding="utf-8"))["findings"]
    assert {row["file"] for row in findings} == {
        f"syntax/complexity/hot.{suffix}" for suffix in SUFFIXES
    }
    assert {row["language"] for row in findings} == {"javascript"}
    assert {row["analyzer"] for row in findings} == {"typescript-compiler-api"}

    omnibus_out = host / "reports" / "omnibus.jsonl"
    omnibus = _run(
        sys.executable,
        str(SKILLS / "find-omnibus" / "scripts" / "detect.py"),
        "--target", str(host / "syntax" / "omnibus"),
        "--project-root", str(host),
        "--output", str(omnibus_out),
        "--language", "javascript",
        cwd=host,
    )
    assert omnibus.returncode == 0, omnibus.stdout + omnibus.stderr
    omnibus_rows = [json.loads(line) for line in omnibus_out.read_text().splitlines()]
    assert {row["file"] for row in omnibus_rows} == {
        f"syntax/omnibus/domains.{suffix}" for suffix in SUFFIXES
    }
    assert {row["analyzer"] for row in omnibus_rows} == {"typescript-compiler-api"}

    ideas = host / "javascript-standards.json"
    ideas.write_text(json.dumps({"ideas": [{
        "id": "checked-json-parse",
        "label": "JSON parsing is protected",
        "activation": {"baseline": True},
        "contract": {"detector": {
            "kind": "ast",
            "call_matches": "^JSON\\.parse$",
            "enclosed_by": "try",
            "paths": ["syntax/standard/**/*"],
        }},
    }]}), encoding="utf-8")
    standards_out = host / "reports" / "standard-gaps" / "javascript"
    standards = _run(
        sys.executable,
        str(SKILLS / "find-standard-gaps" / "scripts" / "scan_coverage.py"),
        "--ideas", str(ideas),
        "--project-root", str(host),
        "--output-dir", str(standards_out),
        cwd=host,
    )
    assert standards.returncode == 0, standards.stdout + standards.stderr
    result = json.loads((standards_out / "coverage.json").read_text())["results"][0]
    assert result["status"] == "scanned"
    assert result["scanned_files"] == 4
    assert result["situation_sites"] == 8
    assert len(result["gaps"]) == 4
    assert {Path(row["file"]).suffix for row in result["gaps"]} == {
        ".js", ".jsx", ".mjs", ".cjs"
    }

    assert _hashes(host) == before | {
        "javascript-standards.json": hashlib.sha256(ideas.read_bytes()).hexdigest()
    }


def test_javascript_syntax_errors_and_missing_local_parser_are_not_clean(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    broken = host / "broken.jsx"
    broken.write_text("export function broken( { return <div>; }\n", encoding="utf-8")
    parsed = _run(
        "node",
        str(SKILLS / "audit-decisions" / "scripts" / "detect_typescript_comments.mjs"),
        "--file", str(broken),
        "--project-root", str(host),
        cwd=host,
    )
    assert parsed.returncode == 2
    assert "syntax error" in parsed.stderr

    missing = tmp_path / "missing-tool"
    _write(missing / "package.json", '{"name":"missing-tool"}\n')
    _write(missing / "src" / "hot.js", _hot_function("missingTool"))
    result = _run(
        sys.executable,
        str(SKILLS / "find-complexity-hotspots" / "scripts" / "detect.py"),
        "--project-root", str(missing),
        "--language", "javascript",
        "--output", str(missing / "out.jsonl"),
        "src",
        cwd=missing,
    )
    assert result.returncode == 2
    assert "project-local TypeScript package is unavailable" in result.stderr
