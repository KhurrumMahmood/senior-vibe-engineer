"""PHP A3 semantic-read-only final artifacts and copied-closure proof."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "php-semantic-family" / "host"
PHP = Path(shutil.which("php") or "/opt/homebrew/bin/php")
COMPOSER = Path(shutil.which("composer") or "/usr/local/bin/composer")
SKILLS = ROOT / ".claude" / "skills"

CONSUMERS = {
    "dormant": ("find-dormant", "scripts/detect_php_dormant.php"),
    "state": ("find-implicit-state", "scripts/detect_php_state.php"),
    "sweep": ("find-incomplete-sweep", "scripts/detect_php_incomplete_sweep.php"),
    "semantic": ("find-semantic-duplication", "scripts/detect_php_semantic.php"),
    "rename": ("rename-concept", "scripts/assess_php.php"),
}


def _run(*args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    return host


def _hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and "reports" not in path.relative_to(host).parts
        and "reviews" not in path.relative_to(host).parts
        and ".git" not in path.relative_to(host).parts
    }


def _native(host: Path) -> None:
    validate = _run(str(COMPOSER), "validate", "--no-check-publish", "--no-interaction", cwd=host)
    assert validate.returncode == 0, validate.stdout + validate.stderr
    lint = _run(str(PHP), "tests/lint.php", cwd=host)
    assert lint.returncode == 0, lint.stdout + lint.stderr
    smoke = _run(str(PHP), "tests/smoke.php", cwd=host)
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr
    assert smoke.stdout.strip() == "php-semantic-ok"


def _script(name: str, skills: Path = SKILLS) -> Path:
    skill, relative = CONSUMERS[name]
    return skills / skill / relative


def _artifact(host: Path, name: str, scan: str = "php") -> Path:
    return {
        "dormant": host / "reports" / "find-dormant" / scan / "findings.json",
        "state": host / "reports" / "implicit-state" / scan / "findings.json",
        "sweep": host / "reports" / "find-incomplete-sweep" / scan / "manifest.json",
        "semantic": host / "reports" / "semantic-duplication" / scan / "findings.json",
        "rename": host / "reports" / "rename-concept" / f"{scan}.json",
    }[name]


def _payload(host: Path, name: str, scan: str = "php") -> dict:
    return json.loads(_artifact(host, name, scan).read_text(encoding="utf-8"))


def _status(payload: dict, name: str) -> str:
    if name == "rename":
        return "complete" if payload["php_identifier_evidence"]["status"] == "resolved" else "partial"
    return str(payload["status"])


def _invoke(
    host: Path,
    name: str,
    *,
    scan: str = "php",
    skills: Path = SKILLS,
    php: str | Path = PHP,
    composer: str | Path = COMPOSER,
    target: str = "src",
    reviews: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    common = [
        str(PHP), str(_script(name, skills)), "--project-root", str(host), "--target", target,
        "--php", str(php), "--composer", str(composer),
    ]
    if name == "dormant":
        common.extend(("--report-dir", f"reports/find-dormant/{scan}"))
    elif name == "state":
        common.extend(("--output-dir", f"reports/implicit-state/{scan}"))
        if reviews is not None:
            common.extend(("--reviews-dir", str(reviews.relative_to(host))))
    elif name == "sweep":
        common.extend(("--report-dir", f"reports/find-incomplete-sweep/{scan}"))
    elif name == "semantic":
        common.extend(("--report-dir", f"reports/semantic-duplication/{scan}"))
        if reviews is not None:
            common.extend(("--reviews-dir", str(reviews.relative_to(host))))
    else:
        common.extend(("--old", "legacy-status", "--new", "canonical-status", "--output", f"reports/rename-concept/{scan}.json"))
    return _run(*common, cwd=host)


def _git_history(host: Path) -> None:
    initial_env = {**os.environ, "GIT_AUTHOR_DATE": "2023-01-01T00:00:00+0000", "GIT_COMMITTER_DATE": "2023-01-01T00:00:00+0000"}
    later_env = {**os.environ, "GIT_AUTHOR_DATE": "2024-01-01T00:00:00+0000", "GIT_COMMITTER_DATE": "2024-01-01T00:00:00+0000"}
    for command in (("git", "init", "--quiet"), ("git", "config", "user.email", "fixture@example.test"), ("git", "config", "user.name", "Fixture"), ("git", "add", "."), ("git", "commit", "--quiet", "-m", "old request shapes")):
        result = _run(*command, cwd=host, env=initial_env)
        assert result.returncode == 0, result.stdout + result.stderr
    factory = host / "src" / "Domain" / "RequestFactory.php"
    text = factory.read_text(encoding="utf-8").replace("region: 'us', stage", "region: 'us', /* newer sweep */ stage")
    factory.write_text(text, encoding="utf-8")
    assert _run("git", "add", "src/Domain/RequestFactory.php", cwd=host, env=later_env).returncode == 0
    committed = _run("git", "commit", "--quiet", "-m", "add region to newer request shapes", cwd=host, env=later_env)
    assert committed.returncode == 0, committed.stdout + committed.stderr


def _state_reviews(host: Path, payload: dict) -> Path:
    reviews = host / "reviews" / "state"
    reviews.mkdir(parents=True)
    candidate = payload["candidates"][0]
    (reviews / "job-state.json").write_text(json.dumps({
        "schema_version": "php-implicit-state-review-v1", "candidate_id": candidate["candidate_id"],
        "candidate_sha256": candidate["candidate_sha256"], "human_verdict": "extract_enum_candidate", "reviewed_at": "fixture",
    }), encoding="utf-8")
    return reviews


def _semantic_reviews(host: Path, payload: dict) -> Path:
    reviews = host / "reviews" / "semantic"
    reviews.mkdir(parents=True)
    for index, candidate in enumerate(payload["candidates"]):
        names = {member["fqmn"] for member in candidate["members"]}
        verdict = "confirm_candidate" if names == {
            "Acme\\Domain\\SummaryFactory::summarizeByRange", "Acme\\Domain\\SummaryFactory::summarizeByIndex",
        } else "keep_separate"
        (reviews / f"{index}.json").write_text(json.dumps({
            "schema_version": "php-semantic-duplication-review-v1", "candidate_id": candidate["candidate_id"],
            "candidate_sha256": candidate["candidate_sha256"], "human_verdict": verdict, "rationale": "fixture review",
        }), encoding="utf-8")
    return reviews


def _sweep_verdict(host: Path, payload: dict) -> Path:
    path = host / "reviews" / "sweep-verdicts.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    candidate = payload["findings"][0]
    path.write_text(json.dumps({"verdicts": [{
        "candidate_id": candidate["candidate_id"], "candidate_sha256": candidate["candidate_sha256"],
        "verdict": "forgotten", "rationale": "The older direct construction omits a later required sweep field.",
        "completion": "add region: 'us'",
    }]}), encoding="utf-8")
    return path


def _fake_composer(tmp_path: Path, version: str, *, fail_validate: bool = False) -> Path:
    path = tmp_path / f"composer-{version.replace('.', '-')}{'-fail' if fail_validate else ''}"
    path.write_text(
        "#!/bin/sh\n"
        f"if [ \"$1\" = \"--version\" ]; then echo 'Composer version {version} fixture'; exit 0; fi\n"
        + ("exit 1\n" if fail_validate else "exit 0\n"),
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _failing_php(tmp_path: Path) -> Path:
    path = tmp_path / "php-fails-lint"
    path.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then echo 'PHP 8.4.2 fixture'; exit 0; fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _assert_no_positive(payload: dict, name: str) -> None:
    if name == "dormant":
        assert payload["candidates"] == []
    elif name == "state":
        assert payload["candidates"] == [] and payload["findings"] == []
    elif name == "sweep":
        assert payload["findings"] == []
    elif name == "semantic":
        assert payload["candidates"] == [] and payload["confirmed"] == []
    else:
        assert payload["php_identifier_evidence"]["declarations"] == {"old": [], "new": []}


def test_php_a3_positive_human_gates_native_checks_and_source_preservation(tmp_path: Path) -> None:
    host = _host(tmp_path)
    _native(host)
    _git_history(host)
    before = _hashes(host)
    os.symlink(host / "src" / "Domain" / "Job.php", host / "src" / "LinkedJob.php")

    dormant = _invoke(host, "dormant")
    assert dormant.returncode == 0, dormant.stdout + dormant.stderr
    dormant_payload = _payload(host, "dormant")
    assert dormant_payload["status"] == "complete"
    assert [row["fqmn"] for row in dormant_payload["candidates"]] == ["Acme\\Domain\\Job::unusedPrivate"]
    assert dormant_payload["summary"]["certain_delete"] == 0
    assert any("dynamic_member_dispatch" in row["reason"] for row in dormant_payload["uncertain"])
    roles = {row["file"]: row["role"] for row in json.loads((host / "reports/find-dormant/php/facts.json").read_text(encoding="utf-8"))["source_inventory"]["inventory"]}
    assert roles["tests/StateDecoyTest.php"] == "excluded"
    assert roles["generated/GeneratedDecoy.php"] == "excluded"
    assert roles["vendor/example/package/VendorDecoy.php"] == "excluded"
    assert roles["src/LinkedJob.php"] == "excluded"

    unreviewed_state = _invoke(host, "state")
    assert unreviewed_state.returncode == 2
    state_payload = _payload(host, "state")
    assert state_payload["failure_kind"] == "human_review_required"
    state_reviews = _state_reviews(host, state_payload)
    state = _invoke(host, "state", reviews=state_reviews)
    assert state.returncode == 0, state.stdout + state.stderr
    state_payload = _payload(host, "state")
    assert state_payload["status"] == "complete"
    assert state_payload["findings"][0]["authority"]["fqcn"] == "Acme\\Domain\\Job"
    assert state_payload["findings"][0]["literals"] == ["done", "queued", "running"]

    sweep = _invoke(host, "sweep")
    assert sweep.returncode == 0, sweep.stdout + sweep.stderr
    sweep_payload = _payload(host, "sweep")
    assert sweep_payload["status"] == "complete"
    assert len(sweep_payload["findings"]) == 1
    assert sweep_payload["findings"][0]["parameter"] == "region"
    assert sweep_payload["findings"][0]["human_verdict"] == "required"
    verdicts = _sweep_verdict(host, sweep_payload)
    triage = _run(str(PHP), str(_script("sweep").with_name("triage_php.php")), "--project-root", str(host), "--scan-dir", "reports/find-incomplete-sweep/php", "--verdicts", str(verdicts.relative_to(host)), cwd=host)
    assert triage.returncode == 0, triage.stdout + triage.stderr
    assert json.loads((host / "reports/find-incomplete-sweep/php/triaged.json").read_text(encoding="utf-8"))["triaged"][0]["human_verdict"] == "forgotten"

    unreviewed_semantic = _invoke(host, "semantic")
    assert unreviewed_semantic.returncode == 2
    semantic_reviews = _semantic_reviews(host, _payload(host, "semantic"))
    semantic = _invoke(host, "semantic", reviews=semantic_reviews)
    assert semantic.returncode == 0, semantic.stdout + semantic.stderr
    semantic_payload = _payload(host, "semantic")
    assert semantic_payload["status"] == "complete"
    assert [row["finding_id"] for row in semantic_payload["confirmed"]]
    assert {member["fqmn"] for member in semantic_payload["confirmed"][0]["members"]} == {
        "Acme\\Domain\\SummaryFactory::summarizeByRange", "Acme\\Domain\\SummaryFactory::summarizeByIndex",
    }
    assert any(row["human_verdict"] == "keep_separate" for row in semantic_payload["uncertain"])

    rename = _invoke(host, "rename")
    assert rename.returncode == 0, rename.stdout + rename.stderr
    rename_payload = _payload(host, "rename")
    evidence = rename_payload["php_identifier_evidence"]
    assert evidence["status"] == "resolved"
    assert rename_payload["verdict"] == "HALF-APPLIED / INCOMPLETE"
    assert {row["symbol"] for row in evidence["declarations"]["old"]} == {"Acme\\Rename\\LegacyStatus"}
    assert {row["symbol"] for row in evidence["declarations"]["new"]} == {"Acme\\Rename\\CanonicalStatus"}
    assert all(row["symbol"] != "legacy status" for row in evidence["occurrences"])
    (host / "src" / "LinkedJob.php").unlink()
    assert _hashes(host) == before


def test_php_a3_clean_decoys_tool_boundaries_and_artifact_lifecycle(tmp_path: Path) -> None:
    host = _host(tmp_path)
    _native(host)
    before = _hashes(host)

    for name in CONSUMERS:
        result = _invoke(host, name, scan="clean", target="src/Clean")
        assert result.returncode == 0, name + result.stdout + result.stderr
        payload = _payload(host, name, "clean")
        assert _status(payload, name) == "complete"
        _assert_no_positive(payload, name)

    # Every final artifact replaces a prior positive/clean result when native configuration fails,
    # rather than leaving a stale clean or finding report in place.
    failing = _fake_composer(tmp_path, "2.4.0", fail_validate=True)
    for name in CONSUMERS:
        result = _invoke(host, name, scan="clean", target="src/Clean", composer=failing)
        assert result.returncode == 1, name + result.stdout + result.stderr
        payload = _payload(host, name, "clean")
        assert _status(payload, name) in {"partial", "failed"}
        _assert_no_positive(payload, name)
        recovered = _invoke(host, name, scan="clean", target="src/Clean")
        assert recovered.returncode == 0, name + recovered.stdout + recovered.stderr
        assert _status(_payload(host, name, "clean"), name) == "complete"

    missing_php = tmp_path / "missing-php"
    old_composer = _fake_composer(tmp_path, "2.1.9")
    failed_php = _failing_php(tmp_path)
    for name in CONSUMERS:
        missing = _invoke(host, name, scan=f"missing-{name}", php=missing_php)
        assert missing.returncode == 2, name + missing.stdout + missing.stderr
        missing_payload = _payload(host, name, f"missing-{name}")
        assert _status(missing_payload, name) == "partial"
        _assert_no_positive(missing_payload, name)
        old = _invoke(host, name, scan=f"old-{name}", composer=old_composer)
        assert old.returncode == 2, name + old.stdout + old.stderr
        old_payload = _payload(host, name, f"old-{name}")
        assert _status(old_payload, name) == "partial"
        _assert_no_positive(old_payload, name)
        failed = _invoke(host, name, scan=f"failed-{name}", php=failed_php)
        assert failed.returncode == 1, name + failed.stdout + failed.stderr
        failed_payload = _payload(host, name, f"failed-{name}")
        assert _status(failed_payload, name) in {"partial", "failed"}
        _assert_no_positive(failed_payload, name)

    (host / "src" / "Broken.php").write_text("<?php\nfinal class Broken {\n", encoding="utf-8")
    for name in CONSUMERS:
        malformed = _invoke(host, name, scan=f"malformed-{name}")
        assert malformed.returncode == 2, name + malformed.stdout + malformed.stderr
        malformed_payload = _payload(host, name, f"malformed-{name}")
        assert _status(malformed_payload, name) == "partial"
        _assert_no_positive(malformed_payload, name)
    (host / "src" / "Broken.php").unlink()

    # A half-configured project analyzer is visible as a partial boundary, never an invented fact source.
    (host / "phpstan.neon").write_text("parameters:\n  level: 8\n", encoding="utf-8")
    for name in CONSUMERS:
        incomplete = _invoke(host, name, scan=f"configured-{name}")
        assert incomplete.returncode == 2, name + incomplete.stdout + incomplete.stderr
        payload = _payload(host, name, f"configured-{name}")
        assert _status(payload, name) == "partial"
        _assert_no_positive(payload, name)
    assert _hashes(host) == before | {"phpstan.neon": hashlib.sha256(b"parameters:\n  level: 8\n").hexdigest()}


def test_php_a3_copied_external_library_closure_reaches_each_final_artifact(tmp_path: Path) -> None:
    host = _host(tmp_path)
    _git_history(host)
    copied_skills = tmp_path / "on-demand" / ".agents" / "skills"
    for skill, _relative in CONSUMERS.values():
        shutil.copytree(SKILLS / skill, copied_skills / skill)
    shutil.copytree(SKILLS / "_php-semantic", copied_skills / "_php-semantic")
    shutil.copytree(SKILLS / "_php-project-lexical", copied_skills / "_php-project-lexical")

    dormant = _invoke(host, "dormant", scan="copied", skills=copied_skills)
    assert dormant.returncode == 0, dormant.stdout + dormant.stderr
    state_unreviewed = _invoke(host, "state", scan="copied", skills=copied_skills)
    assert state_unreviewed.returncode == 2
    state = _invoke(host, "state", scan="copied", skills=copied_skills, reviews=_state_reviews(host, _payload(host, "state", "copied")))
    assert state.returncode == 0, state.stdout + state.stderr
    sweep = _invoke(host, "sweep", scan="copied", skills=copied_skills)
    assert sweep.returncode == 0, sweep.stdout + sweep.stderr
    semantic_unreviewed = _invoke(host, "semantic", scan="copied", skills=copied_skills)
    assert semantic_unreviewed.returncode == 2
    semantic = _invoke(host, "semantic", scan="copied", skills=copied_skills, reviews=_semantic_reviews(host, _payload(host, "semantic", "copied")))
    assert semantic.returncode == 0, semantic.stdout + semantic.stderr
    rename = _invoke(host, "rename", scan="copied", skills=copied_skills)
    assert rename.returncode == 0, rename.stdout + rename.stderr

    for name in CONSUMERS:
        assert _artifact(host, name, "copied").is_file()
        runtime = _script(name, copied_skills).read_text(encoding="utf-8")
        assert str(ROOT) not in runtime
    assert (copied_skills / "_php-semantic" / "php_semantic_facts.php").is_file()
    assert (copied_skills / "_php-project-lexical" / "php_project_lexical.php").is_file()
