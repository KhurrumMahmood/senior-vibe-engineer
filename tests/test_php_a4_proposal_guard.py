"""PHP A4 accepted-evidence proposal and exact-guard outcomes."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".claude" / "skills"
PHP = Path(shutil.which("php") or "/opt/homebrew/bin/php")
COMPOSER = Path(shutil.which("composer") or "/usr/local/bin/composer")

_A3_SPEC = importlib.util.spec_from_file_location(
    "php_a3", ROOT / "tests" / "test_php_a3_semantic_family.py"
)
assert _A3_SPEC and _A3_SPEC.loader
A3 = importlib.util.module_from_spec(_A3_SPEC)
_A3_SPEC.loader.exec_module(A3)

ADAPTERS = {
    "extract-enum": SKILLS / "extract-enum/scripts/collect_php_state.py",
    "propose-boundary": SKILLS / "propose-boundary/scripts/propose_php.py",
    "propose-folder-reorganization": SKILLS
    / "propose-folder-reorganization/scripts/propose_php.py",
    "unify-shadows": SKILLS / "unify-shadows/scripts/propose_php.py",
}


def _run(*args: str | Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(arg) for arg in args], cwd=cwd, capture_output=True, text=True, check=False
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): _sha(path)
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and not ({"reports", "reviews"} & set(path.relative_to(host).parts))
        and ".git" not in path.relative_to(host).parts
    }


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _accepted(
    host: Path,
    *,
    consumer: str,
    evidence: Path,
    decision: str,
    selection: dict,
) -> Path:
    payload = _json(evidence)
    path = host / "reviews" / "php-a4" / f"{consumer}.json"
    _write_json(
        path,
        {
            "schema_version": "php-a4-acceptance-v1",
            "language": "php",
            "status": "accepted",
            "consumer": consumer,
            "evidence_sha256": _sha(evidence),
            "decision": decision,
            "selection": selection,
            "accepted_limits": payload.get("limits", payload.get("nonclaims", [])),
            "native": {
                "lint": "tests/lint.php",
                "smoke": "tests/smoke.php",
                "smoke_stdout": "php-semantic-ok",
            },
        },
    )
    return path


def _prepare(host: Path) -> dict[str, Path]:
    A3._git_history(host)
    state_first = A3._invoke(host, "state")
    assert state_first.returncode == 2
    state_reviews = A3._state_reviews(host, A3._payload(host, "state"))
    state = A3._invoke(host, "state", reviews=state_reviews)
    assert state.returncode == 0, state.stdout + state.stderr
    semantic_first = A3._invoke(host, "semantic")
    assert semantic_first.returncode == 2
    semantic_reviews = A3._semantic_reviews(host, A3._payload(host, "semantic"))
    semantic = A3._invoke(host, "semantic", reviews=semantic_reviews)
    assert semantic.returncode == 0, semantic.stdout + semantic.stderr
    dormant = A3._invoke(host, "dormant")
    assert dormant.returncode == 0, dormant.stdout + dormant.stderr
    clean = A3._invoke(host, "state", scan="clean", target="src/Clean")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    return {
        "state": host / "reports/implicit-state/php/findings.json",
        "clean_state": host / "reports/implicit-state/clean/findings.json",
        "semantic": host / "reports/semantic-duplication/php/findings.json",
        "facts": host / "reports/find-dormant/php/facts.json",
    }


def _selection(evidence: dict, consumer: str) -> tuple[str, dict]:
    if consumer == "extract-enum":
        candidate = evidence["findings"][0]
        return "propose", {"candidate_id": candidate["candidate_id"]}
    if consumer == "propose-boundary":
        return "propose", {
            "boundary_name": "summary",
            "target_namespace": "Acme\\Domain",
            "proposed_namespace": "Acme\\Summary",
            "members": [
                "Acme\\Domain\\Summary",
                "Acme\\Domain\\AlternativeSummary",
                "Acme\\Domain\\SummaryFactory",
            ],
            "public_api": [
                "Acme\\Domain\\SummaryFactory::summarizeByRange",
                "Acme\\Domain\\SummaryFactory::summarizeByIndex",
            ],
            "compatibility": "retain old FQCN adapters during migration",
        }
    if consumer == "propose-folder-reorganization":
        return "propose", {
            "parent": "src/Domain",
            "cluster": "summary",
            "proposed_namespace": "Acme\\Domain\\Summary",
            "moves": {
                "src/Domain/Summary.php": "src/Domain/Summary/Summary.php",
                "src/Domain/AlternativeSummary.php": "src/Domain/Summary/AlternativeSummary.php",
                "src/Domain/SummaryFactory.php": "src/Domain/Summary/SummaryFactory.php",
            },
            "compatibility": "retain old FQCN shims until direct consumers migrate",
            "convention": "three cohesive production siblings earn a directory package",
        }
    candidate = evidence["confirmed"][0]
    return "propose", {
        "candidate_id": candidate["candidate_id"],
        "canonical": "Acme\\Domain\\SummaryFactory::summarizeByRange",
        "shape": "delegate_to_canonical",
    }


def _invoke(
    host: Path,
    consumer: str,
    evidence: Path,
    acceptance: Path,
    output: Path,
    *,
    skills: Path = SKILLS,
    php: Path | str = PHP,
    composer: Path | str = COMPOSER,
) -> subprocess.CompletedProcess[str]:
    script = {
        name: skills / path.relative_to(SKILLS) for name, path in ADAPTERS.items()
    }[consumer]
    return _run(
        ROOT / ".venv/bin/python",
        script,
        "--project-root",
        host,
        "--evidence",
        evidence,
        "--acceptance",
        acceptance,
        "--output-dir",
        output,
        "--php",
        php,
        "--composer",
        composer,
        cwd=host,
    )


def _migrate_job(host: Path) -> None:
    (host / "src/Domain/JobState.php").write_text(
        """<?php

declare(strict_types=1);

namespace Acme\\Domain;

enum JobState: string
{
    case Queued = 'queued';
    case Running = 'running';
    case Done = 'done';
}
""",
        encoding="utf-8",
    )
    job = host / "src/Domain/Job.php"
    text = job.read_text(encoding="utf-8")
    text = text.replace("private string $state = 'queued';", "private JobState $state = JobState::Queued;")
    text = text.replace("$this->state === 'queued'", "$this->state === JobState::Queued")
    text = text.replace("$this->state = 'running'", "$this->state = JobState::Running")
    text = text.replace("$this->state = 'done'", "$this->state = JobState::Done")
    job.write_text(text, encoding="utf-8")
    smoke = host / "tests/smoke.php"
    smoke.write_text(
        smoke.read_text(encoding="utf-8").replace(
            "require dirname(__DIR__) . '/src/Domain/Job.php';",
            "require dirname(__DIR__) . '/src/Domain/JobState.php';\n"
            "require dirname(__DIR__) . '/src/Domain/Job.php';",
        ),
        encoding="utf-8",
    )


def _guard_acceptance(host: Path, targets: Path, *, decision: str = "stage_guard") -> Path:
    selection = {
        "enum_type": "Acme\\Domain\\JobState",
        "enum_file": "src/Domain/JobState.php",
        "enum_sha256": _sha(host / "src/Domain/JobState.php"),
        "authority_file": "src/Domain/Job.php",
        "authority_sha256": _sha(host / "src/Domain/Job.php"),
        "guard_destination": "tests/guards/job_state_guard.php",
    }
    return _accepted(
        host,
        consumer="prevent-regression",
        evidence=targets,
        decision=decision,
        selection=selection,
    )


def test_php_a4_positive_final_outcomes_native_guard_and_safe_defers(tmp_path: Path) -> None:
    host = A3._host(tmp_path)
    evidence = _prepare(host)
    before = _hashes(host)
    outputs: dict[str, Path] = {}
    for consumer in ADAPTERS:
        source = evidence["state"] if consumer == "extract-enum" else (
            evidence["semantic"] if consumer == "unify-shadows" else evidence["facts"]
        )
        decision, selection = _selection(_json(source), consumer)
        acceptance = _accepted(
            host, consumer=consumer, evidence=source, decision=decision, selection=selection
        )
        output = host / "reports" / consumer / "php-a4"
        result = _invoke(host, consumer, source, acceptance, output)
        assert result.returncode == 0, consumer + result.stdout + result.stderr
        inspection = _json(output / "inspection.json")
        assert inspection["status"] in {"review_required", "ready_for_human_review"}
        assert inspection["source_preserved"] is True
        assert (output / "proposal.md").is_file()
        outputs[consumer] = output

    enum_targets = outputs["extract-enum"] / "targets.json"
    _migrate_job(host)
    guard_acceptance = _guard_acceptance(host, enum_targets)
    guard_stage = host / "reports/prevent-regression/php-a4"
    generated = _run(
        ROOT / ".venv/bin/python",
        SKILLS / "prevent-regression/scripts/generate_php_state_guard.py",
        "--project-root", host,
        "--evidence", enum_targets,
        "--acceptance", guard_acceptance,
        "--output-dir", guard_stage,
        "--php", PHP,
        "--composer", COMPOSER,
        cwd=host,
    )
    assert generated.returncode == 0, generated.stdout + generated.stderr
    assert _json(guard_stage / "authority.json")["status"] == "staged"
    verified = _run(
        ROOT / ".venv/bin/python",
        SKILLS / "prevent-regression/scripts/verify_php_state_guard.py",
        "--project-root", host,
        "--stage", guard_stage,
        "--php", PHP,
        "--composer", COMPOSER,
        cwd=host,
    )
    assert verified.returncode == 0, verified.stdout + verified.stderr
    verification = _json(guard_stage / "verification.json")
    assert verification["outcome"] == "guard_proved"
    assert verification["seeded_regression"]["without_guard_passed"] is True
    assert verification["seeded_regression"]["caught_by_guard"] is True

    # The later defer runs consume a fresh accepted upstream fact pack for the
    # now-migrated source; the proposal consumers themselves never re-detect.
    refreshed = A3._invoke(host, "dormant", scan="post-migration")
    assert refreshed.returncode == 0, refreshed.stdout + refreshed.stderr
    fresh_facts = host / "reports/find-dormant/post-migration/facts.json"

    # Each family retains an explicit non-positive outcome instead of forcing work.
    clean_acceptance = _accepted(
        host,
        consumer="extract-enum",
        evidence=evidence["clean_state"],
        decision="defer_no_candidate",
        selection={},
    )
    clean = _invoke(
        host,
        "extract-enum",
        evidence["clean_state"],
        clean_acceptance,
        host / "reports/extract-enum/php-clean",
    )
    assert clean.returncode == 0
    assert _json(host / "reports/extract-enum/php-clean/inspection.json")["outcome"] == "clean"

    for consumer, decision in (
        ("propose-boundary", "defer_cohesive_target"),
        ("propose-folder-reorganization", "defer_no_convention"),
    ):
        acceptance = _accepted(
            host,
            consumer=consumer,
            evidence=fresh_facts,
            decision=decision,
            selection={},
        )
        output = host / "reports" / consumer / "php-defer"
        result = _invoke(host, consumer, fresh_facts, acceptance, output)
        assert result.returncode == 0
        assert _json(output / "inspection.json")["status"] == "deferred"

    semantic = _json(evidence["semantic"])
    kept = semantic["uncertain"][0]
    keep_acceptance = _accepted(
        host,
        consumer="unify-shadows",
        evidence=evidence["semantic"],
        decision="keep_separate",
        selection={"candidate_id": kept["candidate_id"]},
    )
    keep_output = host / "reports/unify-shadows/php-keep"
    kept_result = _invoke(
        host, "unify-shadows", evidence["semantic"], keep_acceptance, keep_output
    )
    assert kept_result.returncode == 0
    assert _json(keep_output / "inspection.json")["outcome"] == "keep_separate"

    defer_guard = _guard_acceptance(host, enum_targets, decision="defer_no_guard_policy")
    deferred_stage = host / "reports/prevent-regression/php-defer"
    deferred = _run(
        ROOT / ".venv/bin/python",
        SKILLS / "prevent-regression/scripts/generate_php_state_guard.py",
        "--project-root", host,
        "--evidence", enum_targets,
        "--acceptance", defer_guard,
        "--output-dir", deferred_stage,
        "--php", PHP,
        "--composer", COMPOSER,
        cwd=host,
    )
    assert deferred.returncode == 0
    assert _json(deferred_stage / "authority.json")["status"] == "deferred"
    assert _hashes(host) == before | {
        "src/Domain/Job.php": _sha(host / "src/Domain/Job.php"),
        "src/Domain/JobState.php": _sha(host / "src/Domain/JobState.php"),
        "tests/smoke.php": _sha(host / "tests/smoke.php"),
    }


@pytest.mark.parametrize("consumer", list(ADAPTERS))
def test_php_a4_tampered_unaccepted_and_valid_invalid_valid_lifecycle(
    tmp_path: Path, consumer: str
) -> None:
    host = A3._host(tmp_path)
    evidence = _prepare(host)
    source = evidence["state"] if consumer == "extract-enum" else (
        evidence["semantic"] if consumer == "unify-shadows" else evidence["facts"]
    )
    decision, selection = _selection(_json(source), consumer)
    acceptance = _accepted(
        host, consumer=consumer, evidence=source, decision=decision, selection=selection
    )
    output = host / "reports" / consumer / "lifecycle"
    first = _invoke(host, consumer, source, acceptance, output)
    assert first.returncode == 0, first.stdout + first.stderr
    assert (output / "proposal.md").is_file()

    accepted = _json(acceptance)
    accepted["evidence_sha256"] = "0" * 64
    _write_json(acceptance, accepted)
    invalid = _invoke(host, consumer, source, acceptance, output)
    assert invalid.returncode == 2
    assert not (output / "proposal.md").exists()
    refusal = _json(output / "refusal.json")
    assert refusal["status"] == "refused"
    assert "stale" in refusal["failure_kind"] or "tampered" in refusal["failure_kind"]

    accepted["evidence_sha256"] = _sha(source)
    _write_json(acceptance, accepted)
    recovered = _invoke(host, consumer, source, acceptance, output)
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert (output / "proposal.md").is_file()
    assert not (output / "refusal.json").exists()


def test_php_a4_guard_lifecycle_missing_tools_partial_evidence_and_copied_closure(
    tmp_path: Path,
) -> None:
    host = A3._host(tmp_path)
    evidence = _prepare(host)
    state = _json(evidence["state"])
    decision, selection = _selection(state, "extract-enum")
    enum_acceptance = _accepted(
        host,
        consumer="extract-enum",
        evidence=evidence["state"],
        decision=decision,
        selection=selection,
    )
    enum_output = host / "reports/extract-enum/copied"

    copied = tmp_path / "outside-checkout/.agents/skills"
    for skill in ADAPTERS:
        shutil.copytree(SKILLS / skill, copied / skill)
    shutil.copytree(SKILLS / "prevent-regression", copied / "prevent-regression")
    shutil.copytree(SKILLS / "_php-proposal", copied / "_php-proposal")

    copied_enum = _invoke(
        host,
        "extract-enum",
        evidence["state"],
        enum_acceptance,
        enum_output,
        skills=copied,
    )
    assert copied_enum.returncode == 0, copied_enum.stdout + copied_enum.stderr
    for consumer in ("propose-boundary", "propose-folder-reorganization", "unify-shadows"):
        source = evidence["semantic"] if consumer == "unify-shadows" else evidence["facts"]
        decision, selection = _selection(_json(source), consumer)
        acceptance = _accepted(
            host, consumer=consumer, evidence=source, decision=decision, selection=selection
        )
        result = _invoke(
            host,
            consumer,
            source,
            acceptance,
            host / "reports" / consumer / "copied",
            skills=copied,
        )
        assert result.returncode == 0, consumer + result.stdout + result.stderr

    _migrate_job(host)
    targets = enum_output / "targets.json"
    guard_acceptance = _guard_acceptance(host, targets)
    stage = host / "reports/prevent-regression/copied"
    generate = _run(
        ROOT / ".venv/bin/python",
        copied / "prevent-regression/scripts/generate_php_state_guard.py",
        "--project-root", host,
        "--evidence", targets,
        "--acceptance", guard_acceptance,
        "--output-dir", stage,
        "--php", PHP,
        "--composer", COMPOSER,
        cwd=host,
    )
    assert generate.returncode == 0, generate.stdout + generate.stderr
    verify = _run(
        ROOT / ".venv/bin/python",
        copied / "prevent-regression/scripts/verify_php_state_guard.py",
        "--project-root", host,
        "--stage", stage,
        "--php", PHP,
        "--composer", COMPOSER,
        cwd=host,
    )
    assert verify.returncode == 0, verify.stdout + verify.stderr
    for script in copied.rglob("*.py"):
        assert str(ROOT) not in script.read_text(encoding="utf-8")

    accepted = _json(guard_acceptance)
    accepted["status"] = "draft"
    _write_json(guard_acceptance, accepted)
    refused = _run(
        ROOT / ".venv/bin/python",
        copied / "prevent-regression/scripts/generate_php_state_guard.py",
        "--project-root", host,
        "--evidence", targets,
        "--acceptance", guard_acceptance,
        "--output-dir", stage,
        "--php", PHP,
        "--composer", COMPOSER,
        cwd=host,
    )
    assert refused.returncode == 2
    assert (stage / "refusal.json").is_file()
    assert not (stage / "guard/exact_field_type_guard.php").exists()
    accepted["status"] = "accepted"
    _write_json(guard_acceptance, accepted)
    recovered = _run(
        ROOT / ".venv/bin/python",
        copied / "prevent-regression/scripts/generate_php_state_guard.py",
        "--project-root", host,
        "--evidence", targets,
        "--acceptance", guard_acceptance,
        "--output-dir", stage,
        "--php", PHP,
        "--composer", COMPOSER,
        cwd=host,
    )
    assert recovered.returncode == 0

    refreshed = A3._invoke(host, "dormant", scan="copied-post-migration")
    assert refreshed.returncode == 0, refreshed.stdout + refreshed.stderr
    fresh_facts = host / "reports/find-dormant/copied-post-migration/facts.json"

    missing = _invoke(
        host,
        "propose-boundary",
        fresh_facts,
        _accepted(
            host,
            consumer="propose-boundary",
                evidence=fresh_facts,
            decision="defer_cohesive_target",
            selection={},
        ),
        host / "reports/propose-boundary/missing-tool",
        php=tmp_path / "missing-php",
    )
    assert missing.returncode == 2
    assert _json(host / "reports/propose-boundary/missing-tool/refusal.json")[
        "failure_kind"
    ] == "php_missing"

    missing_composer = _invoke(
        host,
        "propose-boundary",
        fresh_facts,
        _accepted(
            host,
            consumer="propose-boundary",
            evidence=fresh_facts,
            decision="defer_cohesive_target",
            selection={},
        ),
        host / "reports/propose-boundary/missing-composer",
        composer=tmp_path / "missing-composer",
    )
    assert missing_composer.returncode == 2
    assert _json(host / "reports/propose-boundary/missing-composer/refusal.json")[
        "failure_kind"
    ] == "composer_missing"

    partial_path = host / "reports/semantic-duplication/partial/findings.json"
    partial = _json(evidence["semantic"])
    partial["status"] = "partial"
    _write_json(partial_path, partial)
    partial_acceptance = _accepted(
        host,
        consumer="unify-shadows",
        evidence=partial_path,
        decision="keep_separate",
        selection={"candidate_id": partial["uncertain"][0]["candidate_id"]},
    )
    incomplete = _invoke(
        host,
        "unify-shadows",
        partial_path,
        partial_acceptance,
        host / "reports/unify-shadows/partial",
    )
    assert incomplete.returncode == 2
    assert _json(host / "reports/unify-shadows/partial/refusal.json")[
        "failure_kind"
    ] == "evidence_incomplete"
