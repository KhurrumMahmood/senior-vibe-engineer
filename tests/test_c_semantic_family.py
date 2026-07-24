"""Final-outcome proof for the bounded Clang-backed C semantic family."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: required frozen cohort runtime
)
FIXTURE = ROOT / "tests/fixtures/c-semantic-family/host"
SKILLS = ROOT / ".claude/skills"
PROVIDER = SKILLS / "_c-semantic/c_semantic_facts.py"
CLANG = shutil.which("clang")
MAKE = shutil.which("make")
SCRIPTS = {
    "dormant": SKILLS / "find-dormant/scripts/detect_c_dormant.py",
    "state": SKILLS / "find-implicit-state/scripts/detect_c_state.py",
    "sweep": SKILLS / "find-incomplete-sweep/scripts/detect_c_incomplete_sweep.py",
    "duplicate": SKILLS / "find-semantic-duplication/scripts/detect_c_semantic.py",
    "rename": SKILLS / "rename-concept/scripts/assess_c_rename.py",
}
OUTPUTS = {
    "dormant": "reports/find-dormant/c/findings.json",
    "state": "reports/implicit-state/c/findings.json",
    "sweep": "reports/find-incomplete-sweep/c/manifest.json",
    "duplicate": "reports/semantic-duplication/c/analysis.json",
    "rename": "reports/rename-concept/c/assessment.json",
}

pytestmark = pytest.mark.skipif(
    not PYTHON.is_file() or CLANG is None or MAKE is None,
    reason="product Python, Clang 21, and Make are required",
)


def _run(*argv: str | Path, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(item) for item in argv], cwd=cwd, env=env, capture_output=True,
        text=True, check=False, timeout=120,
    )


def _host(tmp_path: Path, *, history: bool = True) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    if history:
        semantic = host / "src/semantic.c"
        current = semantic.read_text(encoding="utf-8")
        old = current.replace('.region = "us", ', "")
        semantic.write_text(old, encoding="utf-8")
        _run("git", "init", "-q", cwd=host)
        _run("git", "config", "user.email", "fixture@example.test", cwd=host)
        _run("git", "config", "user.name", "Fixture", cwd=host)
        old_env = {
            **os.environ,
            "GIT_AUTHOR_DATE": "2024-01-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2024-01-01T00:00:00Z",
        }
        assert _run("git", "add", ".", cwd=host, env=old_env).returncode == 0
        assert _run("git", "commit", "-qm", "initial option shape", cwd=host, env=old_env).returncode == 0
        semantic.write_text(current, encoding="utf-8")
        new_env = {
            **os.environ,
            "GIT_AUTHOR_DATE": "2024-02-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2024-02-01T00:00:00Z",
        }
        assert _run("git", "add", "src/semantic.c", cwd=host, env=new_env).returncode == 0
        assert _run("git", "commit", "-qm", "sweep region through newer options", cwd=host, env=new_env).returncode == 0
    result = _run(MAKE, "clean", "compile-db", f"CC={CLANG}", cwd=host)
    assert result.returncode == 0, result.stdout + result.stderr
    return host


def _native(host: Path) -> None:
    result = _run(MAKE, "test", f"CC={CLANG}", cwd=host)
    assert result.returncode == 0, result.stdout + result.stderr
    smoke = _run(host / ".native-build/c-semantic-smoke", cwd=host)
    assert smoke.returncode == 0
    assert smoke.stdout == "semantic:running:us:112:1:legacy_status\n"


def _snapshot(host: Path) -> dict[str, str]:
    rows = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if any(part in {".git", ".native-build", "reports", ".agents"} for part in relative.parts):
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            rows[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return rows


def _collect(host: Path, *, output: str = "reports/c-semantic/facts.json", clang: str | Path = str(CLANG)) -> subprocess.CompletedProcess[str]:
    return _run(
        PYTHON, PROVIDER, "--project-root", host, "--output", output,
        "--clang", clang, cwd=host,
    )


def _consume(
    host: Path,
    kind: str,
    *,
    target: str = "src",
    facts: str | None = "reports/c-semantic/facts.json",
    scripts: dict[str, Path] = SCRIPTS,
    output_suffix: str = "c",
    old: str = "legacy_status",
    new: str = "canonical_status",
    verdict: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    output = OUTPUTS[kind].replace("/c/", f"/{output_suffix}/")
    argv: list[str | Path] = [PYTHON, scripts[kind]]
    if kind == "rename":
        argv.extend([old, new])
    argv.extend(["--project-root", host, "--target", target, "--output", output, "--clang", str(CLANG)])
    if facts is not None:
        argv.extend(["--facts", facts])
    if verdict is not None:
        argv.extend(["--verdict", verdict])
    return _run(*argv, cwd=host)


def _payload(host: Path, kind: str, suffix: str = "c") -> dict:
    path = OUTPUTS[kind].replace("/c/", f"/{suffix}/")
    return json.loads((host / path).read_text(encoding="utf-8"))


def test_c_semantic_pack_reaches_five_conservative_final_outcomes_and_native_smoke(tmp_path: Path) -> None:
    host = _host(tmp_path)
    (host / "src/LinkedDecoy.c").symlink_to("semantic.c")
    _native(host)
    before = _snapshot(host)
    collected = _collect(host)
    assert collected.returncode == 0, collected.stdout + collected.stderr
    facts = json.loads((host / "reports/c-semantic/facts.json").read_text())
    assert facts["status"] == "complete"
    assert facts["compile_database"]["state"] == "valid-current-complete-c17"
    assert facts["direct_references"]
    assert facts["compound_literals"]
    assert any(row["kind"] == "function_pointer_call" for row in facts["boundaries"])
    roles = {row["path"]: row["role"] for row in facts["source_inventory"]}
    assert roles["generated/GeneratedDecoy.c"] == "generated"
    assert roles["vendor/VendorDecoy.c"] == "vendor"
    assert roles["tests/SweepDecoy.c"] == "test"
    assert roles["build/DuplicateDecoy.c"] == "build"
    assert roles["src/LinkedDecoy.c"] == "symlink"

    for kind in SCRIPTS:
        result = _consume(host, kind)
        assert result.returncode == 0, kind + result.stdout + result.stderr

    dormant = _payload(host, "dormant")
    assert dormant["summary"] == {"certain_delete": 0, "review_required": 1}
    assert [(row["name"], row["classification"]) for row in dormant["candidates"]] == [
        ("dormant_adjustment", "review_required")
    ]
    assert any(row["reason"] == "function_pointer_or_dynamic_registration" for row in dormant["deferred"])

    state = _payload(host, "state")
    assert [(row["owner"], row["field"]) for row in state["candidates"]] == [("job", "state")]
    assert state["candidates"][0]["literals"] == ["done", "queued", "running"]
    assert state["candidates"][0]["classification"] == "enum_review_only"
    assert state["candidates"][0]["human_verdict"] == "required"

    sweep = _payload(host, "sweep")
    assert sweep["summary"] == {"deferred": 0, "gated_in": 1, "gated_out": 0}
    assert sweep["findings"][0]["record"] == "request_options"
    assert sweep["findings"][0]["field"] == "region"
    assert sweep["findings"][0]["present_count"] == 3
    assert sweep["findings"][0]["group_size"] == 4
    assert sweep["findings"][0]["human_verdict"] == "required"
    assert "AFTER the straggler" in sweep["findings"][0]["trajectory"]
    verdict = tmp_path / "sweep-verdict.json"
    verdict.write_text(json.dumps({
        "candidate_sha256": sweep["findings"][0]["candidate_sha256"],
        "verdict": "forgotten",
        "rationale": "The later region sweep missed the older initializer.",
    }), encoding="utf-8")
    reviewed = _consume(host, "sweep", verdict=verdict)
    assert reviewed.returncode == 0, reviewed.stdout + reviewed.stderr
    assert _payload(host, "sweep")["human_review"]["state"] == "bound"

    duplicate = _payload(host, "duplicate")
    assert len(duplicate["leads"]) == 1
    assert [row["name"] for row in duplicate["leads"][0]["functions"]] == [
        "build_statement", "summarize_invoice"
    ]
    assert duplicate["leads"][0]["classification"] == "static_review_lead"
    assert "never behavioral equivalence" in duplicate["leads"][0]["boundary"]

    rename = _payload(host, "rename")
    assert rename["assess_only"] is True and rename["source_mutated"] is False
    assert rename["verdict"] == "HALF-APPLIED / INCOMPLETE"
    assert {row["name"] for row in rename["declarations"]["old"]} == {"legacy_status"}
    assert {row["name"] for row in rename["declarations"]["new"]} == {"canonical_status"}
    assert {row["kind"] for row in rename["unresolved_residue"]} >= {
        "macro_or_inactive_variant", "string_literal", "external_consumers"
    }
    assert _snapshot(host) == before
    _native(host)


def test_c_semantic_clean_target_and_compile_database_lifecycle(tmp_path: Path) -> None:
    host = _host(tmp_path, history=False)
    assert _collect(host).returncode == 0
    for kind in ("dormant", "state", "sweep", "duplicate"):
        result = _consume(host, kind, target="src/clean.c", output_suffix="clean")
        assert result.returncode == 0, kind + result.stdout + result.stderr
    rename = _consume(
        host, "rename", target="src/clean.c", output_suffix="clean",
        old="retired_state", new="stable_state",
    )
    assert rename.returncode == 0, rename.stdout + rename.stderr
    assert _payload(host, "dormant", "clean")["candidates"] == []
    assert _payload(host, "state", "clean")["candidates"] == []
    assert _payload(host, "sweep", "clean")["findings"] == []
    assert _payload(host, "duplicate", "clean")["leads"] == []
    assert _payload(host, "rename", "clean")["verdict"] == "CANDIDATE COMPLETE — EXTERNAL REVIEW REQUIRED"

    database = host / "compile_commands.json"
    rows = json.loads(database.read_text())
    database.write_text(json.dumps(rows[:-1]), encoding="utf-8")
    for kind in SCRIPTS:
        result = _consume(host, kind, target="src/clean.c", output_suffix="clean", facts=None,
                          old="retired_state", new="stable_state")
        assert result.returncode == 2, kind + result.stdout + result.stderr
        assert _payload(host, kind, "clean")["status"] == "partial"
    incomplete = _collect(host, output="reports/c-semantic/reused.json")
    assert incomplete.returncode == 2
    partial = json.loads((host / "reports/c-semantic/reused.json").read_text())
    assert partial["status"] == "partial"
    assert partial["failure_kind"] == "compile_database_incomplete"
    assert partial["declarations"] == []

    database.write_text("{", encoding="utf-8")
    malformed = _collect(host, output="reports/c-semantic/reused.json")
    assert malformed.returncode == 1
    failed = json.loads((host / "reports/c-semantic/reused.json").read_text())
    assert failed["status"] == "failed"
    assert failed["failure_kind"] == "compile_database_malformed"
    assert failed["declarations"] == []

    assert _run(MAKE, "compile-db", f"CC={CLANG}", cwd=host).returncode == 0
    recovered = _collect(host, output="reports/c-semantic/reused.json")
    assert recovered.returncode == 0
    assert json.loads((host / "reports/c-semantic/reused.json").read_text())["status"] == "complete"
    for kind in SCRIPTS:
        result = _consume(host, kind, target="src/clean.c", output_suffix="clean",
                          old="retired_state", new="stable_state")
        assert result.returncode == 0, kind + result.stdout + result.stderr
        assert _payload(host, kind, "clean")["status"] == "complete"


def test_c_semantic_missing_old_tool_and_malformed_source_are_visible(tmp_path: Path) -> None:
    host = _host(tmp_path, history=False)
    before = _snapshot(host)
    missing = _collect(host, output="reports/c-semantic/tool.json", clang=tmp_path / "missing-clang")
    assert missing.returncode == 2
    assert json.loads((host / "reports/c-semantic/tool.json").read_text())["failure_kind"] == "clang_missing"
    old = tmp_path / "old-clang"
    old.write_text("#!/bin/sh\necho 'Apple clang version 20.0.0'\n", encoding="utf-8")
    old.chmod(0o755)
    aged = _collect(host, output="reports/c-semantic/tool.json", clang=old)
    assert aged.returncode == 2
    assert json.loads((host / "reports/c-semantic/tool.json").read_text())["failure_kind"] == "clang_version_too_old"

    semantic = host / "src/semantic.c"
    semantic.write_text(semantic.read_text().replace("return amount + 7;", "return ;"), encoding="utf-8")
    assert _run(MAKE, "compile-db", f"CC={CLANG}", cwd=host).returncode == 0
    broken = _collect(host, output="reports/c-semantic/tool.json")
    assert broken.returncode == 1
    payload = json.loads((host / "reports/c-semantic/tool.json").read_text())
    assert payload["status"] == "failed"
    assert payload["failure_kind"] == "clang_ast_failed"
    assert payload["declarations"] == []
    expected = dict(before)
    expected["src/semantic.c"] = hashlib.sha256(semantic.read_bytes()).hexdigest()
    assert _snapshot(host) == expected


def test_c_semantic_copied_external_library_closure_reaches_each_artifact(tmp_path: Path) -> None:
    host = _host(tmp_path)
    assert _collect(host).returncode == 0
    before = _snapshot(host)
    copied = tmp_path / "library/.agents/skills"
    shutil.copytree(SKILLS / "_c-semantic", copied / "_c-semantic")
    installed = {}
    for kind, script in SCRIPTS.items():
        skill = script.parents[1].name
        destination = copied / skill / "scripts" / script.name
        destination.parent.mkdir(parents=True)
        shutil.copy2(script, destination)
        installed[kind] = destination
    for kind in installed:
        result = _consume(host, kind, scripts=installed, output_suffix="copied")
        assert result.returncode == 0, kind + result.stdout + result.stderr
        assert _payload(host, kind, "copied")["status"] == "complete"
        assert str(ROOT) not in installed[kind].read_text(encoding="utf-8")
    assert _snapshot(host) == before
