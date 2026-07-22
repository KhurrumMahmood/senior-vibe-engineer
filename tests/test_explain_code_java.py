"""Java inventory and copied-closure proof for /explain-code."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "explain-code"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "explain-code-java"


def _jdk_bin() -> Path:
    javac = shutil.which("javac")
    java = shutil.which("java")
    if javac is None or java is None:
        pytest.skip("JDK is unavailable")
    version = subprocess.run([javac, "-version"], capture_output=True, text=True, check=False)
    rendered = version.stdout + version.stderr
    if version.returncode != 0 or "javac " not in rendered:
        pytest.skip("JDK version is unavailable")
    if int(rendered.split("javac ", 1)[1].split(".", 1)[0]) < 17:
        pytest.skip("JDK 17+ is required")
    return Path(javac).parent


def _env(tmp_path: Path, *, path: str | None = None) -> dict[str, str]:
    jdk_bin = _jdk_bin()
    return {
        **os.environ,
        "PATH": path if path is not None else f"{jdk_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        "JAVA_TOOL_OPTIONS": "-Djava.io.tmpdir=" + str(tmp_path / "java-tmp"),
    }


def _run(*args: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _host(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    env = _env(tmp_path)
    (tmp_path / "java-tmp").mkdir()
    sources = sorted(str(path) for path in (host / "src/main/java").rglob("*.java"))
    native = _run("javac", "-d", str(tmp_path / "classes"), *sources, cwd=host, env=env)
    assert native.returncode == 0, native.stdout + native.stderr
    return host, env


def _inventory(skill: Path, host: Path, target: str, output: Path, env: dict[str, str]):
    return _run(
        sys.executable,
        "-I",
        "-S",
        str(skill / "scripts" / "inventory_symbols.py"),
        "--target",
        target,
        "--repo-root",
        str(host),
        "--output",
        str(output),
        cwd=host,
        env=env,
    )


def _fingerprints(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "reports" not in path.relative_to(root).parts
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
`{target['symbol']}` is a direct public Java declaration.

## Preconditions
The caller supplies values accepted by the declaration.

## Postconditions
- **Success:** provides the declared source behavior.
- **Failure:** inherited and generated behavior remains outside this inventory.
- **Side effects:** none proven by inventory alone.

## Invariants
- The declaration remains directly public in source.

## Callers (0 total)
No fixture callers beyond native compilation.

## Unexplained regions
No unexplained regions — the source declaration is directly represented.

## Surprising behavior
No surprises — inventory does not infer runtime behavior.
""",
        encoding="utf-8",
    )


def test_java_public_declarations_reach_final_explanation(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    before = _fingerprints(host)
    report_dir = host / "reports/explanations/java"
    targets = report_dir / "targets.json"

    collect = _inventory(SKILL, host, "src/main/java", targets, env)

    assert collect.returncode == 0, collect.stdout + collect.stderr
    payload = json.loads(targets.read_text(encoding="utf-8"))
    assert payload["language"] == "java"
    assert payload["status"] == "complete"
    assert payload["analysis"]["java"]["analyzer"] == "jdk-compiler-tree-api"
    assert payload["analysis"]["java"]["minimum_jdk_version"] == "17.0.0"
    assert {item["symbol"] for item in payload["targets"]} == {
        "PublicContract",
        "PublicContract.execute",
        "PublicContract.identity",
        "Service",
        "Service.Service",
        "Service.VERSION",
        "Service.render",
    }
    assert {item["kind"] for item in payload["targets"]} == {
        "type",
        "constructor",
        "method",
        "field",
    }
    assert "PackageOnly.misleading" not in {item["symbol"] for item in payload["targets"]}
    assert all("test" not in path.lower() for path in payload["files"])
    assert all("GeneratedFixture" not in path for path in payload["files"])

    annotations = report_dir / "annotations"
    annotations.mkdir(parents=True)
    for target in payload["targets"]:
        _write_annotation(annotations / f"{target['symbol_key']}.md", target)
    document = host / "reports/explanations/java.md"
    render = _run(
        sys.executable,
        "-I",
        "-S",
        str(SKILL / "scripts/render_explanation.py"),
        "--targets",
        str(targets),
        "--annotations-dir",
        str(annotations),
        "--output",
        str(document),
        "--summary",
        "Direct public Java declarations are annotated without claiming inheritance or generated behavior.",
        "--regenerated",
        "2026-07-21T00:00:00Z",
        "--project-root",
        str(host),
        cwd=host,
        env=env,
    )
    assert render.returncode == 0, render.stdout + render.stderr
    assert "### Service.render" in document.read_text(encoding="utf-8")
    assert (report_dir / "unexplained.txt").is_file()
    assert (report_dir / "surprises.txt").is_file()
    assert _fingerprints(host) == before


def test_mixed_partial_go_and_complete_java_stays_partial(tmp_path: Path) -> None:
    if shutil.which("go") is None:
        pytest.skip("Go is unavailable")
    host, env = _host(tmp_path)
    go_source = host / "src/main/go/alias.go"
    go_source.parent.mkdir(parents=True)
    go_source.write_text(
        'package service\n\nimport "strings"\n\ntype Remote = strings.Builder\n',
        encoding="utf-8",
    )
    output = host / "reports/explanations/mixed/targets.json"

    result = _inventory(SKILL, host, ".", output, env)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["language"] == "mixed"
    assert payload["status"] == "partial"
    assert payload["analysis"]["go"]["status"] == "partial"
    assert payload["analysis"]["java"]["status"] == "complete"


def test_java_inventory_analyzes_physical_source_once_through_internal_aliases(
    tmp_path: Path,
) -> None:
    host, env = _host(tmp_path)
    service = host / "src/main/java/example/Service.java"
    (host / "service-alias.java").symlink_to(service)
    (host / "java-directory-alias").symlink_to(
        host / "src/main/java", target_is_directory=True
    )
    output = host / "reports/explanations/aliases/targets.json"

    result = _inventory(SKILL, host, ".", output, env)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert "service-alias.java" not in payload["files"]
    assert not any(path.startswith("java-directory-alias/") for path in payload["files"])
    physical_files = [(host / path).resolve() for path in payload["files"]]
    assert len(physical_files) == len(set(physical_files))
    assert [item["symbol"] for item in payload["targets"]].count("Service.render") == 1


def test_java_malformed_missing_tool_and_copied_closure_are_honest(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    broken = host / "src/main/java/example/Broken.java"
    broken.write_text("package example; public class Broken { public void nope( { }\n", encoding="utf-8")
    stale = host / "reports/explanations/broken/targets.json"
    stale.parent.mkdir(parents=True)
    stale.write_text('{"status":"complete"}\n', encoding="utf-8")

    malformed = _inventory(SKILL, host, str(broken.relative_to(host)), stale, env)

    assert malformed.returncode == 2
    assert "status=failed" in malformed.stderr
    assert not stale.exists()

    missing_output = host / "reports/missing.json"
    missing = _inventory(
        SKILL,
        host,
        "src/main/java/example/Service.java",
        missing_output,
        _env(tmp_path / "missing", path=""),
    )
    assert missing.returncode == 2
    assert "status=unsupported" in missing.stderr
    assert not missing_output.exists()

    installed = tmp_path / "installed/explain-code"
    shutil.copytree(SKILL, installed)
    copied_output = host / "reports/copied.json"
    copied = _inventory(
        installed,
        host,
        "src/main/java/example/Service.java",
        copied_output,
        env,
    )
    assert copied.returncode == 0, copied.stdout + copied.stderr
    assert json.loads(copied_output.read_text(encoding="utf-8"))["status"] == "complete"
    assert (installed / "scripts/inventory_java.java").is_file()
    closure = "\n".join(path.read_text(encoding="utf-8") for path in (installed / "scripts").iterdir())
    assert "scripts/_lib" not in closure
    assert str(REPO_ROOT) not in closure


def test_java_explain_contract_declares_bounded_surface() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "Java v1 contract" in text
    assert "JDK 17" in text
    assert "inherited" in text
    assert "generated" in text
