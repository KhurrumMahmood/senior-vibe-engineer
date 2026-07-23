"""Final-artifact contract tests for the bounded Dart D5 family."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/dart-d5"
PROVIDER = ROOT / ".claude/skills/map-subsystem/scripts/dart_lsp_facts.py"
STATE = ROOT / ".claude/skills/find-implicit-state/scripts/detect_dart_state.py"
SWEEP = ROOT / ".claude/skills/find-incomplete-sweep/scripts/detect_dart_incomplete_sweep.py"
DUPLICATE = ROOT / ".claude/skills/find-semantic-duplication/scripts/detect_dart_semantic.py"
SCOUT = ROOT / ".claude/skills/find-incomplete-sweep/scripts/scout.py"
TRIAGE = ROOT / ".claude/skills/find-incomplete-sweep/scripts/triage.py"
DART = Path("/opt/homebrew/bin/dart")  # host-ref-allow: required frozen P7 runtime
PRODUCT_PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: required frozen P7 runtime
)

UNION_QUERIES = [
    "charge",
    "phase",
    "state",
    "status",
]

pytestmark = pytest.mark.skipif(
    not DART.is_file() or not PRODUCT_PYTHON.is_file(),
    reason="the frozen product Python and Dart 3.12 SDK are required",
)


def _run(
    *argv: str | Path,
    cwd: Path,
    expected: int = 0,
    env: dict[str, str] | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(item) for item in argv],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    return result


def _provider():
    spec = importlib.util.spec_from_file_location("test_dart_d5_lsp_facts", PROVIDER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copy_fixture(tmp_path: Path, name: str) -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE / name, host, ignore=shutil.ignore_patterns("reports", ".claude"))
    return host


def _history_host(tmp_path: Path) -> Path:
    host = _copy_fixture(tmp_path, "positive")
    present = [host / f"lib/sweep/present_{name}.dart" for name in "abc"]
    final = [path.read_text(encoding="utf-8") for path in present]
    for path in present:
        path.write_text(path.read_text(encoding="utf-8").replace("audit: true", "audit: false"))
    _run("git", "init", "-q", cwd=host)
    _run("git", "config", "user.email", "fixture@example.com", cwd=host)
    _run("git", "config", "user.name", "Fixture", cwd=host)
    old_env = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2024-01-01T00:00:00Z",
        "GIT_COMMITTER_DATE": "2024-01-01T00:00:00Z",
    }
    _run("git", "add", ".", cwd=host, env=old_env)
    _run("git", "commit", "-qm", "initial call shape", cwd=host, env=old_env)
    for path, content in zip(present, final, strict=True):
        path.write_text(content, encoding="utf-8")
    new_env = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2024-02-01T00:00:00Z",
        "GIT_COMMITTER_DATE": "2024-02-01T00:00:00Z",
    }
    _run("git", "add", *[path.relative_to(host) for path in present], cwd=host, env=new_env)
    _run("git", "commit", "-qm", "thread audit option through callers", cwd=host, env=new_env)
    return host


def _snapshot(host: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if any(part in {".git", ".claude", "reports"} for part in relative.parts):
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            rows[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return rows


def _write_json(payload: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _collect(host: Path, queries: list[str] = UNION_QUERIES, **kwargs: str) -> dict:
    return _provider().collect(
        host,
        ".",
        queries,
        dart=kwargs.get("dart", str(DART)),
        timeout=30,
    )


def _state_review(candidates_path: Path, review_dir: Path) -> Path:
    candidate = json.loads(candidates_path.read_text().strip())
    return _write_json(
        {
            "schema_version": "dart-implicit-state-review-v1",
            "candidate_id": candidate["candidate_id"],
            "candidate_sha256": candidate["candidate_sha256"],
            "bucket": "extract_enum_candidate",
            "confidence": "high",
            "human_verdict": "accepted",
            "notes": "The resolved Job.state operations warrant enum proposal review; the domain remains open.",
        },
        review_dir / f"{candidate['candidate_id']}.json",
    )


def _run_consumers(
    host: Path,
    facts: Path,
    *,
    state_scan: str = "dart",
    sweep_scan: str = "dart",
    duplicate_scan: str = "dart",
    reviews: Path | None = None,
    expected: int = 0,
    scripts: dict[str, Path] | None = None,
) -> None:
    scripts = scripts or {"state": STATE, "sweep": SWEEP, "duplicate": DUPLICATE}
    state_argv: list[str | Path] = [
        PRODUCT_PYTHON,
        scripts["state"],
        "--project-root",
        host,
        "--target",
        "lib",
        "--output-dir",
        f"reports/implicit-state/{state_scan}",
        "--facts",
        facts,
    ]
    if reviews is not None:
        state_argv.extend(["--reviews-dir", reviews])
    _run(*state_argv, cwd=host, expected=expected)
    _run(
        PRODUCT_PYTHON,
        scripts["sweep"],
        "--project-root",
        host,
        "--target",
        "lib",
        "--report-dir",
        f"reports/find-incomplete-sweep/{sweep_scan}",
        "--facts",
        facts,
        cwd=host,
        expected=expected,
    )
    _run(
        PRODUCT_PYTHON,
        scripts["duplicate"],
        "--project-root",
        host,
        "--target",
        "lib",
        "--output-dir",
        f"reports/semantic-duplication/{duplicate_scan}",
        "--facts",
        facts,
        cwd=host,
        expected=0 if expected == 0 else expected,
    )


@pytest.fixture(scope="module")
def family_packs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, tuple[Path, Path]]:
    base = tmp_path_factory.mktemp("dart-d5-family")
    result: dict[str, tuple[Path, Path]] = {}
    for name in ("positive", "clean"):
        host = _history_host(base / name) if name == "positive" else _copy_fixture(base, name)
        queries = UNION_QUERIES if name == "positive" else ["charge", "phase"]
        facts = _collect(host, queries)
        assert facts["status"] == "complete"
        assert facts["query_plan"]["queries"] == sorted(queries)
        path = _write_json(facts, base / f"{name}-facts.json")
        result[name] = (host, path)
    return result


def test_union_pack_drives_state_sweep_and_honest_duplication_stop(
    family_packs: dict[str, tuple[Path, Path]], tmp_path: Path
) -> None:
    host, facts_path = family_packs["positive"]
    before = _snapshot(host)

    _run_consumers(host, facts_path)
    pending = json.loads((host / "reports/implicit-state/dart/findings.json").read_text())
    assert pending["status"] == "partial"
    assert pending["failure_kind"] == "human_review_required"
    assert pending["findings"] == []
    assert pending["summary"]["pending_review"] == 1

    reviews = tmp_path / "reviews"
    _state_review(host / "reports/implicit-state/dart/candidates.jsonl", reviews)
    _run_consumers(host, facts_path, reviews=reviews)

    state_dir = host / "reports/implicit-state/dart"
    state = json.loads((state_dir / "findings.json").read_text())
    state_facts = json.loads((state_dir / "facts.json").read_text())
    state_scan = json.loads((state_dir / "scan.json").read_text())
    assert state["schema_version"] == "dart-implicit-state-v1"
    assert state["status"] == "complete"
    assert [(row["owner"], row["field"]) for row in state["findings"]] == [("Job", "state")]
    assert state["findings"][0]["literals"] == ["done", "queued", "running"]
    assert state["findings"][0]["bucket"] == "extract_enum_candidate"
    assert state["findings"][0]["human_verdict"] == "accepted"
    assert all(operation["definition_targets"] for operation in state["findings"][0]["operations"])
    assert state_facts["fact_pack_sha256"] == state["fact_pack_sha256"]
    assert state_scan["findings_sha256"] == hashlib.sha256(
        (state_dir / "findings.json").read_bytes()
    ).hexdigest()
    assert (state_dir / "scout/dart-implicit-state-0001.json").is_file()
    assert {row["classification"] for row in state["classifications"]} >= {
        "typed_state_authority",
        "insufficient_bounded_literals",
        "serialization_or_wire_boundary",
    }

    sweep_dir = host / "reports/find-incomplete-sweep/dart"
    manifest = json.loads((sweep_dir / "manifest.json").read_text())
    assert manifest["language"] == "dart" and manifest["status"] == "complete"
    assert manifest["summary"] == {"deferred": 0, "gated_in": 1, "gated_out": 0}
    assert manifest["findings"][0]["callee"] == "charge"
    assert manifest["findings"][0]["kwarg"] == "audit"
    assert manifest["findings"][0]["group_size"] == 4
    assert manifest["findings"][0]["present_count"] == 3
    assert "AFTER the straggler" in manifest["findings"][0]["trajectory"]
    assert all(site["definition_targets"] for site in manifest["findings"][0]["present_sites"])
    _run(PRODUCT_PYTHON, SCOUT, "--scan-dir", sweep_dir, cwd=host)
    packets = json.loads((sweep_dir / "scout_packets.json").read_text())
    assert packets["language"] == "dart" and packets["packet_count"] == 1
    _write_json(
        {
            "verdicts": [
                {
                    "id": "SW-01",
                    "verdict": "forgotten",
                    "rationale": "The newer audit-option sweep missed the older direct call.",
                    "completion": "Pass audit explicitly after separate approval.",
                }
            ]
        },
        sweep_dir / "scout_verdicts.json",
    )
    _run(PRODUCT_PYTHON, TRIAGE, "--scan-dir", sweep_dir, cwd=host)
    assert "human-verdict handoff" in (sweep_dir / "triaged.md").read_text()

    duplicate_dir = host / "reports/semantic-duplication/dart"
    duplicate = json.loads((duplicate_dir / "analysis.json").read_text())
    assert duplicate["schema_version"] == "dart-semantic-duplication-v1"
    assert duplicate["status"] == "partial"
    assert duplicate["failure_kind"] == "accepted_provider_fact_gap"
    assert duplicate["confirmed"] == []
    assert duplicate["missing_required_facts"] == [
        "per-function outgoing call-hierarchy results with source and target lineage"
    ]
    assert "textDocument/prepareCallHierarchy" in duplicate["provider_query_plan"]["requests"]
    assert "callHierarchy/outgoingCalls" in duplicate["provider_query_plan"]["requests"]
    assert "callHierarchy/incomingCalls" not in duplicate["provider_query_plan"]["requests"]
    assert "No Dart lead was promoted" in (duplicate_dir / "triage.md").read_text()
    assert not list(duplicate_dir.glob("capability-matrix-*.md"))

    pack_hash = json.loads(facts_path.read_text())["fact_pack_sha256"]
    assert state["fact_pack_sha256"] == manifest["fact_pack_sha256"] == duplicate["fact_pack_sha256"] == pack_hash
    assert _snapshot(host) == before


def test_clean_and_must_not_fire_outcomes(
    family_packs: dict[str, tuple[Path, Path]],
) -> None:
    host, facts_path = family_packs["clean"]
    before = _snapshot(host)
    _run_consumers(host, facts_path)
    state = json.loads((host / "reports/implicit-state/dart/findings.json").read_text())
    sweep = json.loads((host / "reports/find-incomplete-sweep/dart/manifest.json").read_text())
    duplicate = json.loads((host / "reports/semantic-duplication/dart/analysis.json").read_text())
    assert state["status"] == "complete" and state["findings"] == []
    assert state["summary"]["raw_candidates"] == 0
    assert sweep["status"] == "complete" and sweep["findings"] == []
    assert sweep["gated_out"] == []
    assert duplicate["status"] == "partial" and duplicate["confirmed"] == []
    assert _snapshot(host) == before


def test_partial_failed_valid_lifecycle_replaces_stale_reports(
    tmp_path: Path,
) -> None:
    host = _history_host(tmp_path)
    valid_payload = _collect(host)
    valid = _write_json(valid_payload, tmp_path / "valid.json")
    _run_consumers(host, valid, state_scan="reuse", sweep_scan="reuse", duplicate_scan="reuse")

    barrel = host / "lib/dart_d5_positive.dart"
    barrel_text = barrel.read_text()
    barrel.write_text(
        barrel_text.replace(
            "export 'state.dart';",
            "export 'state.dart' if (dart.library.io) 'state.dart';",
        ),
        encoding="utf-8",
    )
    partial_payload = _collect(host)
    assert partial_payload["status"] == "partial"
    partial = _write_json(partial_payload, tmp_path / "partial.json")
    _run_consumers(
        host, partial, state_scan="reuse", sweep_scan="reuse", duplicate_scan="reuse"
    )
    barrel.write_text(barrel_text, encoding="utf-8")
    assert json.loads((host / "reports/implicit-state/reuse/findings.json").read_text())[
        "status"
    ] == "partial"
    assert json.loads(
        (host / "reports/find-incomplete-sweep/reuse/manifest.json").read_text()
    )["status"] == "partial"

    failed_payload = _collect(host, dart=str(tmp_path / "missing-dart"))
    assert failed_payload["status"] == "failed"
    failed = _write_json(failed_payload, tmp_path / "failed.json")
    _run_consumers(
        host,
        failed,
        state_scan="reuse",
        sweep_scan="reuse",
        duplicate_scan="reuse",
        expected=2,
    )
    assert json.loads((host / "reports/implicit-state/reuse/findings.json").read_text())[
        "status"
    ] == "failed"
    assert json.loads(
        (host / "reports/find-incomplete-sweep/reuse/manifest.json").read_text()
    )["status"] == "failed"
    assert json.loads(
        (host / "reports/semantic-duplication/reuse/analysis.json").read_text()
    )["status"] == "failed"

    reviews = tmp_path / "reviews"
    _run_consumers(
        host,
        valid,
        state_scan="reuse",
        sweep_scan="reuse",
        duplicate_scan="reuse",
    )
    _state_review(host / "reports/implicit-state/reuse/candidates.jsonl", reviews)
    _run_consumers(
        host,
        valid,
        state_scan="reuse",
        sweep_scan="reuse",
        duplicate_scan="reuse",
        reviews=reviews,
    )
    restored = json.loads((host / "reports/implicit-state/reuse/findings.json").read_text())
    assert restored["status"] == "complete" and len(restored["findings"]) == 1
    assert not (host / "reports/find-incomplete-sweep/reuse/scout_packets.json").exists()


def test_state_review_hash_and_pack_lineage_are_mandatory(tmp_path: Path) -> None:
    host = _history_host(tmp_path)
    facts = _write_json(_collect(host), tmp_path / "facts.json")
    _run_consumers(host, facts)
    review_dir = tmp_path / "reviews"
    review = _state_review(host / "reports/implicit-state/dart/candidates.jsonl", review_dir)
    payload = json.loads(review.read_text())
    payload["candidate_sha256"] = "0" * 64
    _write_json(payload, review)
    _run(
        PRODUCT_PYTHON,
        STATE,
        "--project-root",
        host,
        "--target",
        "lib",
        "--output-dir",
        "reports/implicit-state/bad-review",
        "--facts",
        facts,
        "--reviews-dir",
        review_dir,
        cwd=host,
        expected=2,
    )
    result = json.loads((host / "reports/implicit-state/bad-review/findings.json").read_text())
    assert result["status"] == "failed"
    assert result["failure_kind"] == "invalid_human_review"
    assert result["findings"] == []

    source = host / "lib/state.dart"
    original = source.read_text()
    source.write_text(original + "\n", encoding="utf-8")
    stale = _run(
        PRODUCT_PYTHON,
        STATE,
        "--project-root",
        host,
        "--target",
        "lib",
        "--output-dir",
        "reports/implicit-state/stale",
        "--facts",
        facts,
        cwd=host,
        expected=2,
    )
    assert "stale" in stale.stderr.lower()
    source.write_text(original, encoding="utf-8")


def test_copied_closure_runs_from_outside_repository_and_provider_is_shared(
    tmp_path: Path,
) -> None:
    host = _history_host(tmp_path / "fixture")
    before = _snapshot(host)
    closure = tmp_path / "installed/.agents/skills/on-demand"
    copied = {
        "provider": closure / "map-subsystem/scripts/dart_lsp_facts.py",
        "state": closure / "find-implicit-state/scripts/detect_dart_state.py",
        "sweep": closure / "find-incomplete-sweep/scripts/detect_dart_incomplete_sweep.py",
        "scout": closure / "find-incomplete-sweep/scripts/scout.py",
        "triage": closure / "find-incomplete-sweep/scripts/triage.py",
        "duplicate": closure / "find-semantic-duplication/scripts/detect_dart_semantic.py",
    }
    for source, destination in (
        (PROVIDER, copied["provider"]),
        (STATE, copied["state"]),
        (SWEEP, copied["sweep"]),
        (SCOUT, copied["scout"]),
        (TRIAGE, copied["triage"]),
        (DUPLICATE, copied["duplicate"]),
    ):
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    facts = host / "reports/dart-lsp-facts/copied.json"
    _run(
        PRODUCT_PYTHON,
        copied["provider"],
        "--project-root",
        host,
        "--target",
        ".",
        "--output",
        "reports/dart-lsp-facts/copied.json",
        "--dart",
        DART,
        *sum((["--query", query] for query in UNION_QUERIES), []),
        cwd=tmp_path,
    )
    _run_consumers(host, facts, scripts={key: copied[key] for key in ("state", "sweep", "duplicate")})
    assert json.loads((host / "reports/implicit-state/dart/findings.json").read_text())[
        "status"
    ] == "partial"
    assert json.loads(
        (host / "reports/find-incomplete-sweep/dart/manifest.json").read_text()
    )["summary"]["gated_in"] == 1
    sweep_dir = host / "reports/find-incomplete-sweep/dart"
    _run(PRODUCT_PYTHON, copied["scout"], "--scan-dir", sweep_dir, cwd=tmp_path)
    _write_json(
        {
            "verdicts": [
                {
                    "id": "SW-01",
                    "verdict": "forgotten",
                    "rationale": "The copied closure preserves the explicit human-review seam.",
                    "completion": "Pass audit explicitly after separate approval.",
                }
            ]
        },
        sweep_dir / "scout_verdicts.json",
    )
    _run(PRODUCT_PYTHON, copied["triage"], "--scan-dir", sweep_dir, cwd=tmp_path)
    assert (sweep_dir / "triaged.md").is_file()
    assert json.loads(
        (host / "reports/semantic-duplication/dart/analysis.json").read_text()
    )["failure_kind"] == "accepted_provider_fact_gap"
    assert _snapshot(host) == before

    provider_loc = len(PROVIDER.read_text().splitlines())
    adapter_test_loc = sum(
        len(path.read_text().splitlines()) for path in (STATE, SWEEP, DUPLICATE, Path(__file__))
    )
    duplicated = adapter_test_loc + 3 * provider_loc
    shared = adapter_test_loc + provider_loc
    assert (duplicated - shared) / duplicated >= 0.25
    for script in (STATE, SWEEP, DUPLICATE):
        text = script.read_text()
        assert "load_or_collect" in text
        assert "language-server" not in text
        assert "Content-Length" not in text


def test_actual_union_pack_startup_is_faster_than_two_separate_runs(tmp_path: Path) -> None:
    host = _history_host(tmp_path)
    started = time.perf_counter()
    union = _collect(host)
    union_seconds = time.perf_counter() - started
    separate_seconds = 0.0
    for queries in (["state", "status", "phase"], ["charge"]):
        started = time.perf_counter()
        payload = _collect(host, list(queries))
        separate_seconds += time.perf_counter() - started
        assert payload["status"] == "complete"
    assert union["status"] == "complete"
    assert union_seconds < separate_seconds


def test_native_analyze_format_direct_test_and_smoke() -> None:
    for name, stdout in (("positive", "42"), ("clean", "42")):
        host = FIXTURE / name
        _run(DART, "analyze", "--fatal-infos", "--fatal-warnings", ".", cwd=host)
        _run(
            DART,
            "format",
            "--output=none",
            "--set-exit-if-changed",
            "lib",
            "bin",
            "test",
            cwd=host,
        )
        _run(DART, "test/native_test.dart", cwd=host)
        smoke = _run(DART, "bin/smoke.dart", cwd=host)
        assert smoke.stdout.strip() == stdout
