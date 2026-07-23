"""Focused A4 contract for five accepted-evidence-only Ruby consumers."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv/bin/python"
RUBY = Path.home() / ".local/bin/ruby"
BUNDLER = Path.home() / ".local/bin/bundle"
RBS = Path(shutil.which("rbs") or "")
SEMANTIC_FIXTURE = ROOT / "tests/fixtures/ruby-semantic-family/host"
SYNTAX_FIXTURE = ROOT / "tests/fixtures/ruby-syntax-family/host"
LEXICAL_FIXTURE = ROOT / "tests/fixtures/ruby-project-lexical-family/host"
FACTS = ROOT / ".claude/skills/_ruby-semantic/ruby_semantic_facts.py"
STATE = ROOT / ".claude/skills/find-implicit-state/scripts/detect_ruby_state.py"
DUPLICATION = ROOT / ".claude/skills/find-semantic-duplication/scripts/detect_ruby_semantic.py"
OMNIBUS = ROOT / ".claude/skills/find-omnibus/scripts/run_ruby.py"
FOLDER = ROOT / ".claude/skills/find-folder-topology-drift/scripts/detect_ruby.py"
HELPER = ROOT / ".claude/skills/_ruby-semantic/ruby_proposal_evidence.py"
CONSUMERS = {
    "extract": ROOT / ".claude/skills/extract-enum/scripts/collect_ruby_state.py",
    "guard": ROOT / ".claude/skills/prevent-regression/scripts/generate_ruby_state_guard.py",
    "boundary": ROOT / ".claude/skills/propose-boundary/scripts/propose_ruby.py",
    "folder": ROOT / ".claude/skills/propose-folder-reorganization/scripts/propose_ruby.py",
    "unify": ROOT / ".claude/skills/unify-shadows/scripts/propose_ruby.py",
}
pytestmark = pytest.mark.skipif(
    not all(path.is_file() for path in (PYTHON, RUBY, BUNDLER, RBS)),
    reason="Ruby 3.4, Bundler 2.6, RBS 3.4, and worktree .venv Python are required",
)


def _run(*argv: str, cwd: Path, expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False, timeout=180)
    assert result.returncode == expected, result.stdout + result.stderr
    return result


def _copy(source: Path, target: Path) -> Path:
    shutil.copytree(source, target)
    return target


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_state(root: Path) -> dict[str, tuple[str, str]]:
    rows = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] == "reports":
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = ("symlink", os.readlink(path))
        elif path.is_file():
            rows[relative.as_posix()] = ("file", _hash(path))
    return rows


def _accept(
    host: Path,
    artifact: Path,
    producer: str,
    decision: str,
    *,
    candidate_sha256: str | None = None,
    selection_id: str | None = None,
    selection_sha256: str | None = None,
) -> Path:
    path = artifact.with_name(f"{producer}-acceptance.json")
    payload = {
        "schema_version": "ruby-a4-human-acceptance-v1",
        "producer": producer,
        "artifact": artifact.relative_to(host).as_posix(),
        "artifact_sha256": _hash(artifact),
        "decision": decision,
        "reviewer": "fixture-reviewer",
        "reviewed_boundaries": ["Ruby dynamic dispatch", "Rails/Zeitwerk", "metaprogramming"],
    }
    if candidate_sha256 is not None:
        payload["candidate_sha256"] = candidate_sha256
    if selection_id is not None:
        payload["selection_id"] = selection_id
    if selection_sha256 is not None:
        payload["selection_sha256"] = selection_sha256
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _semantic(host: Path) -> tuple[Path, Path, Path]:
    facts = host / "reports/ruby-semantic/facts.json"
    _run(
        str(PYTHON), str(FACTS), "--project-root", str(host), "--target", "lib",
        "--output", str(facts), "--ruby", str(RUBY), "--bundler", str(BUNDLER),
        "--rbs", str(RBS), "--test", "test/semantic_test.rb", "--smoke", "bin/semantic-kit-smoke",
        cwd=host,
    )
    state_dir = host / "reports/find-implicit-state/ruby"
    _run(
        str(PYTHON), str(STATE), "--project-root", str(host), "--target", "lib",
        "--facts", str(facts), "--output-dir", str(state_dir), cwd=host,
    )
    duplicate_dir = host / "reports/semantic-duplication/ruby"
    _run(
        str(PYTHON), str(DUPLICATION), "--project-root", str(host), "--target", "lib",
        "--facts", str(facts), "--output-dir", str(duplicate_dir), cwd=host,
    )
    return facts, state_dir / "findings.json", duplicate_dir / "analysis.json"


def _extract(host: Path, facts: Path, state: Path, acceptance: Path, script: Path | None = None, *, expected: int = 0) -> Path:
    output = host / "reports/extract-enum/ruby/job-phase"
    _run(
        str(PYTHON), "-I", "-S", str(script or CONSUMERS["extract"]),
        "--project-root", str(host), "--evidence", str(state), "--facts", str(facts),
        "--acceptance", str(acceptance), "--output-dir", str(output), cwd=host, expected=expected,
    )
    return output


def test_five_consumers_reach_distinct_positive_outcomes_and_preserve_sources(tmp_path: Path) -> None:
    semantic = _copy(SEMANTIC_FIXTURE, tmp_path / "semantic")
    semantic_before = _source_state(semantic)
    facts, state, duplication = _semantic(semantic)
    state_payload = _json(state)
    state_acceptance = _accept(
        semantic, state, "find-implicit-state", "accept-enum",
        candidate_sha256=state_payload["candidate_sha256"],
    )
    extract = _extract(semantic, facts, state, state_acceptance)
    targets = _json(extract / "targets.json")
    assert targets["outcome"] == "proposal_ready"
    assert targets["target"]["literals"] == ["done", "queued", "running"]
    assert targets["dynamic_boundaries"][0]["name"] == "public_send"
    assert targets["native_checks"]["test"]["stdout"] == "ruby-semantic-native-test:ok\n"
    review = extract / "accepted-review.json"
    review.write_text(
        json.dumps({
            "schema_version": "ruby-enum-proposal-review-v1",
            "decision": "approve-exact-rbs-guard",
            "targets_sha256": _hash(extract / "targets.json"),
            "reviewer": "fixture-reviewer",
            "reviewed_boundaries": ["exact RBS declaration only", "Rails enum excluded"],
        }) + "\n",
        encoding="utf-8",
    )
    guard = semantic / "reports/prevent-regression/ruby/job-phase"
    _run(
        str(PYTHON), "-I", "-S", str(CONSUMERS["guard"]),
        "--project-root", str(semantic), "--targets", str(extract / "targets.json"),
        "--accepted-review", str(review), "--output-dir", str(guard), "--ruby", str(RUBY), cwd=semantic,
    )
    assert _json(guard / "guard.json")["outcome"] == "guard_staged"
    verification = _json(guard / "verification.json")
    assert (verification["good_rc"], verification["bad_rc"]) == (0, 1)
    job_source = semantic / "lib/semantic/job.rb"
    job_original = job_source.read_text(encoding="utf-8")
    job_source.write_text(job_original + "\n# stale guard input\n", encoding="utf-8")
    _run(
        str(PYTHON), "-I", "-S", str(CONSUMERS["guard"]),
        "--project-root", str(semantic), "--targets", str(extract / "targets.json"),
        "--accepted-review", str(review), "--output-dir", str(guard), "--ruby", str(RUBY),
        cwd=semantic, expected=2,
    )
    assert _json(guard / "guard.json")["failure_kind"] == "stale_accepted_evidence"
    job_source.write_text(job_original, encoding="utf-8")
    _run(
        str(PYTHON), "-I", "-S", str(CONSUMERS["guard"]),
        "--project-root", str(semantic), "--targets", str(extract / "targets.json"),
        "--accepted-review", str(review), "--output-dir", str(guard), "--ruby", str(RUBY), cwd=semantic,
    )
    assert _json(guard / "verification.json")["status"] == "complete"
    duplication_payload = _json(duplication)
    duplicate_acceptance = _accept(
        semantic, duplication, "find-semantic-duplication", "share_utilities",
        candidate_sha256=duplication_payload["candidate_sha256"], selection_id="RRSD-01",
    )
    unify = semantic / "reports/unify-shadows/ruby/RRSD-01"
    _run(
        str(PYTHON), "-I", "-S", str(CONSUMERS["unify"]),
        "--project-root", str(semantic), "--evidence", str(duplication), "--facts", str(facts),
        "--acceptance", str(duplicate_acceptance), "--output-dir", str(unify), cwd=semantic,
    )
    assert set(path.name for path in unify.iterdir()) == {"proposal.md", "evidence.json", "scope.json"}
    assert _json(unify / "evidence.json")["outcome"] == "proposal_ready"
    assert semantic_before == _source_state(semantic)

    syntax = _copy(SYNTAX_FIXTURE, tmp_path / "syntax")
    syntax_before = _source_state(syntax)
    omnibus_dir = syntax / "reports/omnibus/ruby"
    _run(
        str(PYTHON), str(OMNIBUS), "--project-root", str(syntax), "--target", "lib",
        "--output-dir", str(omnibus_dir), "--scout-dir", str(syntax / "ruby-scouts"),
        "--ruby", str(RUBY), "--bundler", str(BUNDLER), "--test", "test/syntax_native_test.rb",
        "--smoke", "bin/ruby-syntax-smoke", cwd=syntax,
    )
    omnibus = omnibus_dir / "findings.json"
    omnibus_acceptance = _accept(syntax, omnibus, "find-omnibus", "split-boundary", selection_id="candidate-001")
    boundary = syntax / "reports/propose-boundary/ruby/omnibus"
    _run(
        str(PYTHON), "-I", "-S", str(CONSUMERS["boundary"]), "--project-root", str(syntax),
        "--evidence", str(omnibus), "--acceptance", str(omnibus_acceptance), "--output-dir", str(boundary), cwd=syntax,
    )
    assert _json(boundary / "inspection.json")["outcome"] == "proposal_ready"
    assert syntax_before == _source_state(syntax)

    lexical = _copy(LEXICAL_FIXTURE, tmp_path / "lexical")
    lexical_before = _source_state(lexical)
    detections = lexical / "reports/folder/ruby/detections.jsonl"
    _run(
        str(PYTHON), str(FOLDER), "--project-root", str(lexical), "--ruby-root", "lib/billing",
        "--output", str(detections), "--ruby", str(RUBY), "--bundler", str(BUNDLER),
        "--test", "test/invoice_test.rb", "--smoke", "bin/ruby-lexical-smoke", cwd=lexical,
    )
    folder_evidence = detections.with_name("findings.json")
    finding = _json(folder_evidence)["findings"][0]
    folder_acceptance = _accept(
        lexical, folder_evidence, "find-folder-topology-drift", "split-folder",
        selection_sha256=finding["evidence_sha256"],
    )
    folder = lexical / "reports/propose-folder-reorganization/ruby/billing"
    _run(
        str(PYTHON), "-I", "-S", str(CONSUMERS["folder"]), "--project-root", str(lexical),
        "--evidence", str(folder_evidence), "--acceptance", str(folder_acceptance), "--output-dir", str(folder), cwd=lexical,
    )
    assert len(_json(folder / "inspection.json")["moves"]) == 3
    assert lexical_before == _source_state(lexical)


def test_clean_defer_keep_separate_and_refusal_lifecycle(tmp_path: Path) -> None:
    host = _copy(SEMANTIC_FIXTURE, tmp_path / "host")
    facts, state, duplication = _semantic(host)
    state_payload = _json(state)
    acceptance = _accept(host, state, "find-implicit-state", "defer", candidate_sha256=state_payload["candidate_sha256"])
    output = _extract(host, facts, state, acceptance)
    assert _json(output / "targets.json")["outcome"] == "safely_deferred"
    acceptance = _accept(host, state, "find-implicit-state", "accept-enum", candidate_sha256=state_payload["candidate_sha256"])
    output = _extract(host, facts, state, acceptance)
    assert _json(output / "targets.json")["outcome"] == "proposal_ready"
    source = host / "lib/semantic/job.rb"
    original = source.read_text(encoding="utf-8")
    source.write_text(original + "\n# stale evidence\n", encoding="utf-8")
    _extract(host, facts, state, acceptance, expected=2)
    refused = _json(output / "targets.json")
    assert refused["outcome"] == "refused"
    assert refused["failure_kind"] == "stale_accepted_evidence"
    source.write_text(original, encoding="utf-8")
    _extract(host, facts, state, acceptance)
    assert _json(output / "targets.json")["outcome"] == "proposal_ready"
    acceptance_payload = _json(acceptance)
    acceptance_payload["artifact_sha256"] = "0" * 64
    acceptance.write_text(json.dumps(acceptance_payload), encoding="utf-8")
    _extract(host, facts, state, acceptance, expected=2)
    assert _json(output / "targets.json")["failure_kind"] == "invalid_accepted_evidence"
    acceptance_payload["artifact_sha256"] = _hash(state)
    acceptance_payload["decision"] = "pending"
    acceptance.write_text(json.dumps(acceptance_payload), encoding="utf-8")
    _extract(host, facts, state, acceptance, expected=2)
    assert _json(output / "targets.json")["failure_kind"] == "unaccepted_evidence"

    duplication_payload = _json(duplication)
    keep = _accept(
        host, duplication, "find-semantic-duplication", "keep_separate_document_why",
        candidate_sha256=duplication_payload["candidate_sha256"], selection_id="RRSD-01",
    )
    unify = host / "reports/unify-shadows/ruby/RRSD-01"
    _run(
        str(PYTHON), "-I", "-S", str(CONSUMERS["unify"]), "--project-root", str(host),
        "--evidence", str(duplication), "--facts", str(facts), "--acceptance", str(keep),
        "--output-dir", str(unify), cwd=host,
    )
    assert _json(unify / "evidence.json")["outcome"] == "keep_separate_documented"
    assert "No consolidation or caller-move plan" in (unify / "proposal.md").read_text(encoding="utf-8")


def test_missing_evidence_tools_and_copied_on_demand_closure(tmp_path: Path) -> None:
    host = _copy(SEMANTIC_FIXTURE, tmp_path / "host")
    facts, state, duplication = _semantic(host)
    state_payload = _json(state)
    acceptance = _accept(host, state, "find-implicit-state", "accept-enum", candidate_sha256=state_payload["candidate_sha256"])
    output = host / "reports/extract-enum/ruby/missing"
    _run(
        str(PYTHON), "-I", "-S", str(CONSUMERS["extract"]), "--project-root", str(host),
        "--evidence", str(state), "--facts", str(host / "missing-facts.json"),
        "--acceptance", str(acceptance), "--output-dir", str(output), cwd=host, expected=2,
    )
    assert _json(output / "targets.json")["failure_kind"] == "evidence_unavailable"
    missing_rbs = host / "reports/ruby-semantic/missing-tool.json"
    _run(
        str(PYTHON), str(FACTS), "--project-root", str(host), "--target", "lib", "--output", str(missing_rbs),
        "--ruby", str(RUBY), "--bundler", str(BUNDLER), "--rbs", str(tmp_path / "missing-rbs"), cwd=host, expected=2,
    )
    assert _json(missing_rbs)["failure_kind"] == "rbs_missing"

    install = tmp_path / "outside-checkout/.agents/skills"
    copied_helper = install / "_ruby-semantic/ruby_proposal_evidence.py"
    copied_helper.parent.mkdir(parents=True)
    shutil.copy2(HELPER, copied_helper)
    copied = {}
    for name, source in CONSUMERS.items():
        destination = install / source.parents[1].name / "scripts" / source.name
        destination.parent.mkdir(parents=True)
        shutil.copy2(source, destination)
        copied[name] = destination
    _extract(host, facts, state, acceptance, copied["extract"])
    assert _json(host / "reports/extract-enum/ruby/job-phase/targets.json")["outcome"] == "proposal_ready"
    targets = host / "reports/extract-enum/ruby/job-phase/targets.json"
    review = targets.with_name("accepted-review.json")
    review.write_text(
        json.dumps({
            "schema_version": "ruby-enum-proposal-review-v1",
            "decision": "approve-exact-rbs-guard",
            "targets_sha256": _hash(targets),
            "reviewer": "fixture-reviewer",
            "reviewed_boundaries": ["exact RBS declaration only"],
        }),
        encoding="utf-8",
    )
    copied_guard = host / "reports/prevent-regression/ruby/copied"
    _run(
        str(PYTHON), "-I", "-S", str(copied["guard"]), "--project-root", str(host),
        "--targets", str(targets), "--accepted-review", str(review),
        "--output-dir", str(copied_guard), "--ruby", str(RUBY), cwd=host,
    )
    assert _json(copied_guard / "verification.json")["bad_rc"] == 1
    duplicate_payload = _json(duplication)
    duplicate_acceptance = _accept(
        host, duplication, "find-semantic-duplication", "keep_separate_document_why",
        candidate_sha256=duplicate_payload["candidate_sha256"], selection_id="RRSD-01",
    )
    copied_unify = host / "reports/unify-shadows/ruby/copied"
    _run(
        str(PYTHON), "-I", "-S", str(copied["unify"]), "--project-root", str(host),
        "--evidence", str(duplication), "--facts", str(facts), "--acceptance", str(duplicate_acceptance),
        "--output-dir", str(copied_unify), cwd=host,
    )
    assert _json(copied_unify / "evidence.json")["outcome"] == "keep_separate_documented"

    syntax = _copy(SYNTAX_FIXTURE, tmp_path / "copied-syntax")
    omnibus_dir = syntax / "reports/omnibus/ruby"
    _run(
        str(PYTHON), str(OMNIBUS), "--project-root", str(syntax), "--target", "lib",
        "--output-dir", str(omnibus_dir), "--scout-dir", str(syntax / "ruby-scouts"),
        "--ruby", str(RUBY), "--bundler", str(BUNDLER), "--test", "test/syntax_native_test.rb",
        "--smoke", "bin/ruby-syntax-smoke", cwd=syntax,
    )
    omnibus = omnibus_dir / "findings.json"
    omnibus_acceptance = _accept(syntax, omnibus, "find-omnibus", "keep-cohesive", selection_id="candidate-001")
    copied_boundary = syntax / "reports/propose-boundary/ruby/copied"
    _run(
        str(PYTHON), "-I", "-S", str(copied["boundary"]), "--project-root", str(syntax),
        "--evidence", str(omnibus), "--acceptance", str(omnibus_acceptance),
        "--output-dir", str(copied_boundary), cwd=syntax,
    )
    assert _json(copied_boundary / "inspection.json")["outcome"] == "safely_deferred"

    lexical = _copy(LEXICAL_FIXTURE, tmp_path / "copied-lexical")
    detections = lexical / "reports/folder/ruby/detections.jsonl"
    _run(
        str(PYTHON), str(FOLDER), "--project-root", str(lexical), "--ruby-root", "lib/billing",
        "--output", str(detections), "--ruby", str(RUBY), "--bundler", str(BUNDLER),
        "--test", "test/invoice_test.rb", "--smoke", "bin/ruby-lexical-smoke", cwd=lexical,
    )
    folder_evidence = detections.with_name("findings.json")
    finding = _json(folder_evidence)["findings"][0]
    folder_acceptance = _accept(
        lexical, folder_evidence, "find-folder-topology-drift", "keep-flat",
        selection_sha256=finding["evidence_sha256"],
    )
    copied_folder = lexical / "reports/propose-folder-reorganization/ruby/copied"
    _run(
        str(PYTHON), "-I", "-S", str(copied["folder"]), "--project-root", str(lexical),
        "--evidence", str(folder_evidence), "--acceptance", str(folder_acceptance),
        "--output-dir", str(copied_folder), cwd=lexical,
    )
    assert _json(copied_folder / "inspection.json")["outcome"] == "safely_deferred"
    assert str(ROOT) not in copied["extract"].read_text(encoding="utf-8")
    for script in copied.values():
        assert "ruby_proposal_evidence" in script.read_text(encoding="utf-8")


def test_native_ruby_bundler_rbs_and_prism_contract(tmp_path: Path) -> None:
    host = _copy(SEMANTIC_FIXTURE, tmp_path / "native")
    assert _run(str(RUBY), "--version", cwd=host).stdout.startswith("ruby 3.4")
    assert _run(str(RUBY), "--disable-gems", "-rprism", "-e", "puts Prism::VERSION", cwd=host).stdout == "1.2.0\n"
    assert _run(str(BUNDLER), "--version", cwd=host).stdout == "Bundler version 2.6.2\n"
    assert _run(str(RBS), "--version", cwd=host).stdout == "rbs 3.4.0\n"
    assert _run(str(RBS), "--no-collection", "-I", "sig", "validate", cwd=host).returncode == 0
    assert _run(str(RUBY), "--disable-gems", "-c", "lib/semantic/job.rb", cwd=host).stdout == "Syntax OK\n"
    assert _run(str(BUNDLER), "check", cwd=host).returncode == 0
    assert _run(str(RUBY), "--disable-gems", f"-I{host / 'lib'}", "test/semantic_test.rb", cwd=host).stdout == "ruby-semantic-native-test:ok\n"
    assert _run(str(RUBY), "--disable-gems", f"-I{host / 'lib'}", "bin/semantic-kit-smoke", cwd=host).stdout == "invoice:INV-7\n"
