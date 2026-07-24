"""Outcome, content-addressing, and copied-closure proof for C++ proposals."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path("/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python")  # host-ref-allow: frozen product runtime
FIXTURE = ROOT / "tests/fixtures/cpp-semantic-family/host"
SKILLS = ROOT / ".claude/skills"
PROVIDER = SKILLS / "_cpp-semantic/cpp_semantic_facts.py"
TOOLS = SKILLS / "_cpp-semantic/cpp_proposal_tools.py"
STATE = SKILLS / "find-implicit-state/scripts/detect_cpp_state.py"
DUPLICATE = SKILLS / "find-semantic-duplication/scripts/detect_cpp_semantic.py"
EXTRACT = SKILLS / "extract-enum/scripts/collect_cpp_state.py"
GUARD = SKILLS / "prevent-regression/scripts/stage_cpp_state_guard.py"
UNIFY = SKILLS / "unify-shadows/scripts/propose_cpp.py"
CLANGXX = shutil.which("clang++")
MAKE = shutil.which("make")
SUFFIXES = {".cc", ".cpp", ".cxx", ".c++", ".C", ".ii", ".hpp", ".hh", ".hxx", ".h++", ".ipp", ".inl", ".tpp", ".h", ".inc"}

pytestmark = pytest.mark.skipif(
    not PYTHON.is_file() or CLANGXX is None or MAKE is None,
    reason="product Python, Clang++ 21, and Make are required",
)


def _run(*argv: str | Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(item) for item in argv], cwd=cwd, capture_output=True, text=True,
        check=False, timeout=240,
    )


def _host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host, ignore=shutil.ignore_patterns(".native-build", "compile_commands.json", "reports"))
    result = _run(MAKE, "clean", "compile-db", f"CXX={CLANGXX}", cwd=host)
    assert result.returncode == 0, result.stdout + result.stderr
    return host


def _snapshot(host: Path) -> dict[str, str]:
    rows = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if any(part in {".git", ".native-build", "reports"} for part in relative.parts):
            continue
        if relative.as_posix() == "compile_commands.json":
            continue
        if path.is_file() and not path.is_symlink():
            rows[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return rows


def _source_rows(host: Path) -> list[dict[str, str]]:
    rows = []
    for path in host.rglob("*"):
        relative = path.relative_to(host)
        if any(part in {".agents", ".claude", ".engineering", ".git", "reports"} for part in relative.parts):
            continue
        if path.is_file() and path.suffix in SUFFIXES:
            rows.append({"path": relative.as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return sorted(rows, key=lambda row: row["path"])


def _prepare(host: Path, *, provider: Path = PROVIDER, state: Path = STATE, duplicate: Path = DUPLICATE) -> None:
    result = _run(PYTHON, provider, "--project-root", host, "--output", "reports/cpp-semantic/facts.json", "--clangxx", CLANGXX, cwd=host)
    assert result.returncode == 0, result.stdout + result.stderr
    result = _run(PYTHON, state, "--project-root", host, "--target", "src", "--facts", "reports/cpp-semantic/facts.json", "--output", "reports/implicit-state/cpp/findings.json", "--clangxx", CLANGXX, cwd=host)
    assert result.returncode == 0, result.stdout + result.stderr
    result = _run(PYTHON, duplicate, "--project-root", host, "--target", "src", "--facts", "reports/cpp-semantic/facts.json", "--output", "reports/semantic-duplication/cpp/analysis.json", "--clangxx", CLANGXX, cwd=host)
    assert result.returncode == 0, result.stdout + result.stderr


def _extract(host: Path, script: Path = EXTRACT, suffix: str = "cpp") -> subprocess.CompletedProcess[str]:
    return _run(
        PYTHON, script, "--project-root", host,
        "--facts", "reports/cpp-semantic/facts.json",
        "--findings", "reports/implicit-state/cpp/findings.json",
        "--selector", "cppsemantic::Job.state",
        "--output-dir", f"reports/extract-enum/{suffix}",
        "--clangxx", CLANGXX, "--make", MAKE, cwd=host,
    )


def _unify(host: Path, script: Path = UNIFY, suffix: str = "cpp") -> subprocess.CompletedProcess[str]:
    return _run(
        PYTHON, script, "--project-root", host,
        "--facts", "reports/cpp-semantic/facts.json",
        "--analysis", "reports/semantic-duplication/cpp/analysis.json",
        "--choice", "share_utilities",
        "--output-dir", f"reports/unify-shadows/{suffix}",
        "--clangxx", CLANGXX, "--make", MAKE, cwd=host,
    )


def _verify_hash(payload: dict) -> None:
    claimed = payload.pop("artifact_sha256")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    assert claimed == hashlib.sha256(encoded).hexdigest()


def _apply_plan(host: Path, proposal: dict) -> None:
    by_path = {}
    for row in proposal["mutation_plan"]:
        by_path.setdefault(row["path"], []).append(row)
    for relative, rows in by_path.items():
        path = host / relative
        text = path.read_text(encoding="utf-8")
        for row in rows:
            assert text.count(row["before"]) == 1
            text = text.replace(row["before"], row["after"], 1)
        path.write_text(text, encoding="utf-8")


def _accept(host: Path, proposal_path: Path, proposal: dict) -> Path:
    acceptance = {
        "schema_version": "cpp-enum-migration-acceptance-v1",
        "language": "cpp",
        "status": "accepted",
        "decision": "approve_exact_field_guard",
        "proposal_sha256": hashlib.sha256(proposal_path.read_bytes()).hexdigest(),
        "authority": proposal["authority"],
        "approvals": {key: "approved" for key in ("abi", "external", "storage", "wire", "odr")},
        "migrated_source_files": _source_rows(host),
    }
    path = host / "reports/extract-enum/cpp/accepted-migration.json"
    path.write_text(json.dumps(acceptance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _guard(host: Path, accepted: Path, script: Path = GUARD, suffix: str = "cpp") -> subprocess.CompletedProcess[str]:
    return _run(
        PYTHON, script, "--project-root", host,
        "--proposal", "reports/extract-enum/cpp/proposal.json",
        "--accepted-migration", accepted.relative_to(host),
        "--output-dir", f"reports/prevent-regression/{suffix}",
        "--clangxx", CLANGXX, "--make", MAKE, cwd=host,
    )


def test_cpp_enum_proposal_guard_and_shadow_proposal_reach_native_outcomes(tmp_path: Path) -> None:
    host = _host(tmp_path)
    _prepare(host)
    original = _snapshot(host)

    extracted = _extract(host)
    assert extracted.returncode == 0, extracted.stdout + extracted.stderr
    proposal_path = host / "reports/extract-enum/cpp/proposal.json"
    proposal = json.loads(proposal_path.read_text())
    _verify_hash(dict(proposal))
    assert proposal["status"] == "review_required"
    assert proposal["read_only"] is True and proposal["source_mutations"] == 0
    assert proposal["proposed_enum"] == {"name": "JobState", "values": ["done", "queued", "running"]}
    assert proposal["native_proof"]["smoke_preserved"] is True
    assert set(proposal["approval_gates"]) == {"abi", "external", "storage", "wire", "odr"}

    bad_findings = json.loads((host / "reports/implicit-state/cpp/findings.json").read_text())
    bad_findings["fact_pack_sha256"] = "0" * 64
    (host / "reports/implicit-state/cpp/tampered.json").write_text(json.dumps(bad_findings), encoding="utf-8")
    refused_extract = _run(
        PYTHON, EXTRACT, "--project-root", host,
        "--facts", "reports/cpp-semantic/facts.json",
        "--findings", "reports/implicit-state/cpp/tampered.json",
        "--selector", "cppsemantic::Job.state",
        "--output-dir", "reports/extract-enum/refused", cwd=host,
    )
    assert refused_extract.returncode == 2 and "evidence_invalid" in refused_extract.stderr

    unified = _unify(host)
    assert unified.returncode == 0, unified.stdout + unified.stderr
    scope = json.loads((host / "reports/unify-shadows/cpp/scope.json").read_text())
    evidence = json.loads((host / "reports/unify-shadows/cpp/evidence.json").read_text())
    _verify_hash(dict(scope))
    _verify_hash(dict(evidence))
    assert scope["selected_choice"] == "share_utilities"
    assert scope["source_mutations"] == 0
    assert {row["qualified_name"] for row in scope["functions"]} == {
        "cppsemantic::build_statement", "cppsemantic::summarize_invoice"
    }
    assert all(count > 0 for count in scope["boundary_counts"].values())
    assert evidence["native_proof"]["passed"] is True
    assert evidence["human_acceptance"] == "required"
    assert _snapshot(host) == original

    tampered = json.loads((host / "reports/semantic-duplication/cpp/analysis.json").read_text())
    tampered["fact_pack_sha256"] = "0" * 64
    (host / "reports/semantic-duplication/cpp/tampered.json").write_text(json.dumps(tampered), encoding="utf-8")
    refused = _run(
        PYTHON, UNIFY, "--project-root", host, "--facts", "reports/cpp-semantic/facts.json",
        "--analysis", "reports/semantic-duplication/cpp/tampered.json",
        "--output-dir", "reports/unify-shadows/refused", cwd=host,
    )
    assert refused.returncode == 2 and "analysis_invalid" in refused.stderr

    _apply_plan(host, proposal)
    migrated = _run(MAKE, "clean", "compile-db", "test", f"CXX={CLANGXX}", cwd=host)
    assert migrated.returncode == 0, migrated.stdout + migrated.stderr
    accepted = _accept(host, proposal_path, proposal)
    migrated_snapshot = _snapshot(host)
    guarded = _guard(host, accepted)
    assert guarded.returncode == 0, guarded.stdout + guarded.stderr
    guard_text = (host / "reports/prevent-regression/cpp/guard.cpp").read_text()
    guard_evidence = json.loads((host / "reports/prevent-regression/cpp/evidence.json").read_text())
    _verify_hash(dict(guard_evidence))
    assert "std::is_same_v" in guard_text
    assert guard_evidence["status"] == "verified"
    assert guard_evidence["verification"]["current_guard"]["returncode"] == 0
    assert guard_evidence["verification"]["seeded_regression"]["returncode"] != 0
    assert guard_evidence["verification"]["regression_rejected"] is True
    assert _snapshot(host) == migrated_snapshot

    bad_acceptance = json.loads(accepted.read_text())
    bad_acceptance["proposal_sha256"] = "f" * 64
    bad = host / "reports/extract-enum/cpp/bad-acceptance.json"
    bad.write_text(json.dumps(bad_acceptance), encoding="utf-8")
    refused_guard = _guard(host, bad, suffix="refused")
    assert refused_guard.returncode == 2 and "acceptance_invalid" in refused_guard.stderr

    stale_acceptance = json.loads(accepted.read_text())
    stale_acceptance["migrated_source_files"][0]["sha256"] = "0" * 64
    stale = host / "reports/extract-enum/cpp/stale-acceptance.json"
    stale.write_text(json.dumps(stale_acceptance), encoding="utf-8")
    stale_guard = _guard(host, stale, suffix="stale")
    assert stale_guard.returncode == 2 and "evidence_stale" in stale_guard.stderr


def test_cpp_phase_b_consumers_run_from_one_copied_closure(tmp_path: Path) -> None:
    host = _host(tmp_path / "project")
    _prepare(host)
    assembled = tmp_path / "assembled"
    assembled.mkdir()
    for path in (PROVIDER, TOOLS, EXTRACT, GUARD, UNIFY):
        shutil.copy2(path, assembled / path.name)
    copied_extract = assembled / EXTRACT.name
    copied_guard = assembled / GUARD.name
    copied_unify = assembled / UNIFY.name

    extracted = _extract(host, copied_extract, "copied")
    assert extracted.returncode == 0, extracted.stdout + extracted.stderr
    unified = _unify(host, copied_unify, "copied")
    assert unified.returncode == 0, unified.stdout + unified.stderr
    assert json.loads((host / "reports/unify-shadows/copied/evidence.json").read_text())["status"] == "proposal_ready"

    copied_proposal_path = host / "reports/extract-enum/copied/proposal.json"
    copied_proposal = json.loads(copied_proposal_path.read_text())
    canonical_proposal = host / "reports/extract-enum/cpp/proposal.json"
    canonical_proposal.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(copied_proposal_path, canonical_proposal)
    _apply_plan(host, copied_proposal)
    assert _run(MAKE, "clean", "compile-db", "test", f"CXX={CLANGXX}", cwd=host).returncode == 0
    accepted = _accept(host, canonical_proposal, copied_proposal)
    guarded = _guard(host, accepted, copied_guard, "copied")
    assert guarded.returncode == 0, guarded.stdout + guarded.stderr
    assert json.loads((host / "reports/prevent-regression/copied/evidence.json").read_text())["status"] == "verified"
