"""Final-outcome proof for the bounded Clang-backed C++ semantic family."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path("/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python")  # host-ref-allow: frozen product runtime
FIXTURE = ROOT / "tests/fixtures/cpp-semantic-family/host"
SKILLS = ROOT / ".claude/skills"
PROVIDER = SKILLS / "_cpp-semantic/cpp_semantic_facts.py"
CLANGXX = shutil.which("clang++")
MAKE = shutil.which("make")
SCRIPTS = {
    "dormant": SKILLS / "find-dormant/scripts/detect_cpp_dormant.py",
    "state": SKILLS / "find-implicit-state/scripts/detect_cpp_state.py",
    "sweep": SKILLS / "find-incomplete-sweep/scripts/detect_cpp_incomplete_sweep.py",
    "duplicate": SKILLS / "find-semantic-duplication/scripts/detect_cpp_semantic.py",
    "rename": SKILLS / "rename-concept/scripts/assess_cpp_rename.py",
}
OUTPUTS = {
    "dormant": "reports/find-dormant/cpp/findings.json",
    "state": "reports/implicit-state/cpp/findings.json",
    "sweep": "reports/find-incomplete-sweep/cpp/manifest.json",
    "duplicate": "reports/semantic-duplication/cpp/analysis.json",
    "rename": "reports/rename-concept/cpp/assessment.json",
}

pytestmark = pytest.mark.skipif(
    not PYTHON.is_file() or CLANGXX is None or MAKE is None,
    reason="product Python, Clang++ 21, and Make are required",
)


def _run(*argv: str | Path, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(item) for item in argv], cwd=cwd, env=env, capture_output=True,
        text=True, check=False, timeout=180,
    )


def _host(tmp_path: Path, *, history: bool = True) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host, ignore=shutil.ignore_patterns(".native-build", "compile_commands.json", "reports"))
    if history:
        semantic = host / "src/semantic.cpp"
        current = semantic.read_text(encoding="utf-8")
        old = current.replace('.region = "us", ', "")
        semantic.write_text(old, encoding="utf-8")
        assert _run("git", "init", "-q", cwd=host).returncode == 0
        assert _run("git", "config", "user.email", "fixture@example.test", cwd=host).returncode == 0
        assert _run("git", "config", "user.name", "Fixture", cwd=host).returncode == 0
        old_env = {
            **os.environ,
            "GIT_AUTHOR_DATE": "2024-01-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2024-01-01T00:00:00Z",
        }
        assert _run("git", "add", ".", cwd=host, env=old_env).returncode == 0
        assert _run("git", "commit", "-qm", "initial aggregate shape", cwd=host, env=old_env).returncode == 0
        semantic.write_text(current, encoding="utf-8")
        new_env = {
            **os.environ,
            "GIT_AUTHOR_DATE": "2024-02-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2024-02-01T00:00:00Z",
        }
        assert _run("git", "add", "src/semantic.cpp", cwd=host, env=new_env).returncode == 0
        assert _run("git", "commit", "-qm", "sweep region through current options", cwd=host, env=new_env).returncode == 0
    compiled = _run(MAKE, "clean", "compile-db", f"CXX={CLANGXX}", cwd=host)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    return host


def _native(host: Path) -> None:
    result = _run(MAKE, "test", f"CXX={CLANGXX}", cwd=host)
    assert result.returncode == 0, result.stdout + result.stderr
    smoke = _run(host / ".native-build/cpp-semantic-smoke", cwd=host)
    assert smoke.returncode == 0
    assert smoke.stdout == "cpp-semantic:running:us:112:1:LegacyStatus:41\n"


def _snapshot(host: Path) -> dict[str, str]:
    rows = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if any(part in {".git", ".native-build", "reports"} for part in relative.parts):
            continue
        if relative.as_posix() == "compile_commands.json":
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            rows[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return rows


def _collect(host: Path, *, output: str = "reports/cpp-semantic/facts.json", clangxx: str | Path = str(CLANGXX)) -> subprocess.CompletedProcess[str]:
    return _run(
        PYTHON, PROVIDER, "--project-root", host, "--output", output,
        "--clangxx", clangxx, cwd=host,
    )


def _consume(
    host: Path,
    kind: str,
    *,
    script: Path | None = None,
    facts: str | None = "reports/cpp-semantic/facts.json",
    output_suffix: str = "cpp",
    verdict: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    argv: list[str | Path] = [PYTHON, script or SCRIPTS[kind]]
    if kind == "rename":
        argv.extend(["LegacyStatus", "CanonicalStatus"])
    argv.extend([
        "--project-root", host,
        "--target", "src",
        "--output", OUTPUTS[kind].replace("/cpp/", f"/{output_suffix}/"),
        "--clangxx", str(CLANGXX),
    ])
    if facts is not None:
        argv.extend(["--facts", facts])
    if verdict is not None:
        argv.extend(["--verdict", verdict])
    return _run(*argv, cwd=host)


def _payload(host: Path, kind: str, suffix: str = "cpp") -> dict:
    return json.loads((host / OUTPUTS[kind].replace("/cpp/", f"/{suffix}/")).read_text(encoding="utf-8"))


def test_cpp_semantic_pack_reaches_five_conservative_outcomes_and_native_smoke(tmp_path: Path) -> None:
    host = _host(tmp_path)
    (host / "src/LinkedDecoy.cpp").symlink_to("semantic.cpp")
    _native(host)
    before = _snapshot(host)
    collected = _collect(host)
    assert collected.returncode == 0, collected.stdout + collected.stderr
    facts = json.loads((host / "reports/cpp-semantic/facts.json").read_text())
    assert facts["status"] == "complete"
    assert facts["compile_database"]["state"] == "valid-current-complete-c++20"
    assert facts["source_preservation"]["unchanged"] is True
    assert {row["kind"] for row in facts["boundaries"]} >= {
        "overload_set", "template", "operator", "virtual_dispatch",
        "function_pointer_or_dynamic_call", "odr_header_definition",
    }
    roles = {row["path"]: row["role"] for row in facts["source_inventory"]}
    assert roles["include/orphan.h"] == "ambiguous-header"
    assert roles["generated/Generated.cpp"] == "generated"
    assert roles["vendor/Vendor.cpp"] == "vendor"
    assert roles["tests/SemanticTest.cpp"] == "test"
    assert roles["src/LinkedDecoy.cpp"] == "symlink"

    for kind in SCRIPTS:
        result = _consume(host, kind)
        assert result.returncode == 0, kind + result.stdout + result.stderr

    dormant = _payload(host, "dormant")
    assert dormant["summary"] == {"certain_delete": 0, "review_required": 1}
    assert dormant["candidates"][0]["qualified_name"].endswith("dormant_adjustment")
    assert dormant["candidates"][0]["certain_delete"] is False
    assert {row["reason"] for row in dormant["deferred"]} >= {
        "function_pointer_callback_or_registration",
        "external_linkage_or_out_of_tree_consumers_unresolved",
    }

    state = _payload(host, "state")
    assert [(row["owner"], row["field"]) for row in state["candidates"]] == [
        ("cppsemantic::Job", "state")
    ]
    assert state["candidates"][0]["literals"] == ["done", "queued", "running"]
    assert state["candidates"][0]["classification"] == "enum_class_review_only"
    assert state["candidates"][0]["automatic_migration"] is False

    sweep = _payload(host, "sweep")
    assert sweep["summary"]["gated_in"] == 1
    assert sweep["findings"][0]["record"] == "cppsemantic::RequestOptions"
    assert sweep["findings"][0]["field"] == "region"
    assert sweep["findings"][0]["present_count"] == 3
    assert sweep["findings"][0]["group_size"] == 4
    assert "ODR" in sweep["findings"][0]["cpp_boundaries"]
    verdict = tmp_path / "sweep-verdict.json"
    verdict.write_text(json.dumps({
        "candidate_sha256": sweep["findings"][0]["candidate_sha256"],
        "verdict": "forgotten",
        "rationale": "The later region sweep missed the older aggregate return.",
    }), encoding="utf-8")
    reviewed = _consume(host, "sweep", verdict=verdict)
    assert reviewed.returncode == 0, reviewed.stdout + reviewed.stderr
    assert _payload(host, "sweep")["human_review"]["state"] == "bound"

    duplicate = _payload(host, "duplicate")
    assert len(duplicate["leads"]) == 1
    assert [row["qualified_name"] for row in duplicate["leads"][0]["functions"]] == [
        "cppsemantic::build_statement", "cppsemantic::summarize_invoice"
    ]
    assert duplicate["leads"][0]["classification"] == "static_structural_review_lead"
    assert "never establish behavioral equivalence" in duplicate["limits"][-1]

    rename = _payload(host, "rename")
    assert rename["assess_only"] is True and rename["source_mutated"] is False
    assert rename["verdict"] == "HALF-APPLIED / INCOMPLETE"
    assert {row["name"] for row in rename["declarations"]["old"]} == {"LegacyStatus"}
    assert {row["name"] for row in rename["declarations"]["new"]} == {"CanonicalStatus"}
    assert {row["kind"] for row in rename["unresolved_residue"]} >= {
        "macro_or_inactive_variant", "string_literal", "external_consumers_and_linkage",
        "overloads_templates_operators_adl", "odr_abi",
    }
    assert _snapshot(host) == before
    _native(host)


def test_cpp_semantic_compile_database_and_content_address_refusals(tmp_path: Path) -> None:
    host = _host(tmp_path, history=False)
    assert _collect(host).returncode == 0
    facts_path = host / "reports/cpp-semantic/facts.json"
    facts = json.loads(facts_path.read_text())
    facts["limits"].append("tampered")
    facts_path.write_text(json.dumps(facts), encoding="utf-8")
    tampered = _consume(host, "dormant")
    assert tampered.returncode == 2
    assert _payload(host, "dormant")["status"] == "partial"

    assert _collect(host).returncode == 0
    header = host / "include/cppsemantic/semantic.hpp"
    header.write_text(header.read_text() + "\n", encoding="utf-8")
    stale = _consume(host, "state")
    assert stale.returncode == 2
    assert _payload(host, "state")["deferred"] == [{"reason": "cpp_semantic_fact_pack_stale"}]

    assert _run(MAKE, "compile-db", f"CXX={CLANGXX}", cwd=host).returncode == 0
    database = host / "compile_commands.json"
    rows = json.loads(database.read_text())
    database.write_text(json.dumps(rows[:-1]), encoding="utf-8")
    incomplete = _collect(host, output="reports/cpp-semantic/refusal.json")
    assert incomplete.returncode == 2
    assert json.loads((host / "reports/cpp-semantic/refusal.json").read_text())["failure_kind"] == "compile_database_incomplete"
    database.write_text("{", encoding="utf-8")
    malformed = _collect(host, output="reports/cpp-semantic/refusal.json")
    assert malformed.returncode == 1
    assert json.loads((host / "reports/cpp-semantic/refusal.json").read_text())["failure_kind"] == "compile_database_malformed"


@pytest.mark.parametrize("kind", sorted(SCRIPTS))
def test_cpp_semantic_consumers_run_from_copied_closures(tmp_path: Path, kind: str) -> None:
    host = _host(tmp_path / "project")
    assert _collect(host).returncode == 0
    assembled = tmp_path / "assembled" / kind
    assembled.mkdir(parents=True)
    copied_script = assembled / SCRIPTS[kind].name
    shutil.copy2(SCRIPTS[kind], copied_script)
    shutil.copy2(PROVIDER, assembled / "cpp_semantic_facts.py")
    result = _consume(host, kind, script=copied_script, output_suffix=f"copied-{kind}")
    assert result.returncode == 0, result.stdout + result.stderr
    copied = _payload(host, kind, f"copied-{kind}")
    assert copied["status"] == "complete"
    assert copied["language"] == "cpp"
    assert copied["fact_pack_sha256"] == json.loads(
        (host / "reports/cpp-semantic/facts.json").read_text()
    )["fact_pack_sha256"]
