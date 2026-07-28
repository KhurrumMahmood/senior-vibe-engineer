"""Final-outcome contract for Dart D3 declaration/body consumers."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/dart-d3"
SNAPSHOT = ROOT / ".claude/skills/_dart/scripts/dart_d3_snapshot.py"
PROVIDER = ROOT / ".claude/skills/_dart/scripts/dart_syntax_facts.py"
TOOL = ROOT / ".claude/skills/_dart/tool"
ADAPTERS = {
    "explain": ROOT / ".claude/skills/explain-code/scripts/explain_dart.py",
    "complexity": ROOT / ".claude/skills/find-complexity-hotspots/scripts/run_dart.py",
    "duplication": ROOT / ".claude/skills/find-duplication/scripts/run_dart.py",
    "omnibus": ROOT / ".claude/skills/find-omnibus/scripts/run_dart.py",
}
DART = Path("/opt/homebrew/bin/dart")  # host-ref-allow: required frozen P7 runtime
PRODUCT_PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: required frozen P7 runtime
)
ACCEPTED_TOOL_SHA256 = "77486420178671884b4b0e409e44ad0d58080d6a29eaef41bd2bab56314acb6e"
CONSUMER_UNION = [
    "explain-code",
    "find-complexity-hotspots",
    "find-duplication",
    "find-omnibus",
]

pytestmark = pytest.mark.skipif(
    not DART.is_file() or not PRODUCT_PYTHON.is_file(),
    reason="the frozen product Python and Dart 3.12 SDK are required",
)


def _run(
    *argv: str | Path,
    cwd: Path,
    expected: int = 0,
    timeout: int = 240,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(item) for item in argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    return result


def _copy_host(tmp_path: Path, name: str) -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE / name, host)
    if name == "positive":
        (host / "lib/linked-external").symlink_to(
            FIXTURE / "symlink-target", target_is_directory=True
        )
    return host


def _state(root: Path) -> dict[str, tuple[str, str]]:
    rows: dict[str, tuple[str, str]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in {"reports", "scouts"}:
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = ("symlink", os.readlink(path))
        elif path.is_file():
            rows[relative.as_posix()] = (
                "file",
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
    return rows


def _facts(
    host: Path,
    destination: Path,
    *,
    snapshot: Path = SNAPSHOT,
    cwd: Path | None = None,
    expected: int = 0,
    smoke_stdout: str | None = None,
) -> dict:
    expected_stdout = smoke_stdout or (
        "dart-d3:42:ok\n" if host.name == "positive" else "dart-d3:clean:ok\n"
    )
    _run(
        PRODUCT_PYTHON,
        "-I",
        "-S",
        snapshot,
        "--project-root",
        host,
        "--target",
        "lib",
        "--output",
        destination,
        "--dart",
        DART,
        "--native-test",
        "tool/d3_native_test.dart",
        "--smoke",
        "bin/d3_smoke.dart",
        "--smoke-stdout",
        expected_stdout,
        cwd=cwd or host,
        expected=expected,
    )
    return json.loads(destination.read_text(encoding="utf-8"))


def _output(host: Path, kind: str) -> Path:
    return {
        "explain": host / "reports/explanations/dart.md",
        "complexity": host / "reports/find-complexity-hotspots/dart",
        "duplication": host / "reports/duplication/dart",
        "omnibus": host / "reports/omnibus/dart",
    }[kind]


def _invoke(
    host: Path,
    facts: Path,
    kind: str,
    *,
    adapter: Path | None = None,
    cwd: Path | None = None,
    expected: int = 0,
    scout_dir: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    target = "lib/public_surface.dart" if kind == "explain" and host.name == "positive" else "lib"
    argv: list[str | Path] = [
        PRODUCT_PYTHON,
        "-I",
        "-S",
        adapter or ADAPTERS[kind],
        "--project-root",
        host,
        "--target",
        target,
        "--facts",
        facts,
    ]
    if kind == "explain":
        argv.extend(["--output", _output(host, kind)])
    else:
        argv.extend(["--output-dir", _output(host, kind)])
    if kind == "omnibus":
        argv.extend(["--scout-dir", scout_dir or host / "scouts"])
    return _run(*argv, cwd=cwd or host, expected=expected)


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _final(host: Path, kind: str) -> dict:
    path = {
        "explain": host / "reports/explanations/dart/targets.json",
        "complexity": _output(host, kind) / "findings.json",
        "duplication": _output(host, kind) / "findings.json",
        "omnibus": _output(host, kind) / "findings.json",
    }[kind]
    return json.loads(path.read_text(encoding="utf-8"))


def _write_scouts(candidates: list[dict], directory: Path) -> None:
    verdicts = {
        "lib/omnibus.dart": (
            "confirmed_omnibus",
            "Four independently understandable invoice, payment, shipping, and audit domains.",
        ),
        "lib/cohesive_control.dart": (
            "facets_not_domains",
            "Header, body, footer, and checksum are cohesive facets of one control frame.",
        ),
    }
    directory.mkdir(parents=True, exist_ok=True)
    for candidate in candidates:
        bucket, rationale = verdicts[candidate["file"]]
        payload = {
            "schema_version": "dart-omnibus-scout-v1",
            "candidate_id": candidate["candidate_id"],
            "candidate_sha256": candidate["candidate_sha256"],
            "human_verdict": "accepted",
            "bucket": bucket,
            "rationale": rationale,
        }
        (directory / f"{candidate['candidate_id']}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _run_positive_consumers(
    host: Path,
    facts: Path,
    *,
    adapters: dict[str, Path] | None = None,
    cwd: Path | None = None,
) -> None:
    selected = adapters or ADAPTERS
    shutil.rmtree(host / "scouts", ignore_errors=True)
    for kind in ("explain", "complexity", "duplication"):
        _invoke(host, facts, kind, adapter=selected[kind], cwd=cwd)
    _invoke(host, facts, "omnibus", adapter=selected["omnibus"], cwd=cwd, expected=2)
    candidates = _jsonl(_output(host, "omnibus") / "candidates.jsonl")
    _write_scouts(candidates, host / "scouts")
    _invoke(host, facts, "omnibus", adapter=selected["omnibus"], cwd=cwd)


def test_union_snapshot_and_four_positive_final_outcomes(tmp_path: Path) -> None:
    host = _copy_host(tmp_path, "positive")
    before = _state(host)
    facts_path = tmp_path / "dart-d3-positive-facts.json"
    facts = _facts(host, facts_path)

    assert facts["schema_version"] == 1
    assert facts["analyzer"] == "dart-d3-union-syntax-snapshot-v1"
    assert facts["consumer_union"] == CONSUMER_UNION
    assert facts["status"] == "complete"
    assert facts["failure_kind"] == "none"
    assert facts["snapshot_key"]["tool_package_sha256"] == ACCEPTED_TOOL_SHA256
    assert facts["provider"]["tool_package"]["sha256"] == ACCEPTED_TOOL_SHA256
    assert facts["provider"]["source_manifest"]["preserved"] is True
    assert all(
        facts["provider"]["native"][name]["passed"]
        for name in ("dart_analyze", "dart_format", "direct_test", "smoke")
    )
    assert facts["provider"]["tool_package"]["setup"]["argv"][1:] == [
        "pub",
        "get",
        "--offline",
        "--enforce-lockfile",
    ]
    inventory = {row["file"]: row["role"] for row in facts["provider"]["inventory"]}
    assert inventory["test/excluded_test.dart"] == "test"
    assert inventory["example/excluded_example.dart"] == "example"
    assert inventory["generated/excluded_generated.dart"] == "generated"
    assert inventory["lib/src/generated.g.dart"] == "generated"
    assert inventory["vendor/excluded_vendor.dart"] == "vendor"
    assert inventory["build/excluded_build.dart"] == "build"
    assert inventory["lib/linked-external"] == "symlink"

    _run_positive_consumers(host, facts_path)

    explanation = _final(host, "explain")
    assert explanation["status"] == "complete"
    assert {row["name"] for row in explanation["selected"]} == {
        "InvoiceMapper",
        "PaymentState",
        "InvoiceService",
        "InvoiceFormatting",
        "calculateInvoice",
    }
    serialized_targets = json.dumps(explanation)
    for decoy in (
        "_adjust",
        "_privateLabel",
        "_invoiceOffset",
        "StringDecoy",
        "ReexportedInvoice",
        "GeneratedInvoice",
    ):
        assert decoy not in serialized_targets
    assert explanation["unexplained"] == [
        {
            "file": "lib/public_surface.dart",
            "kind": "re_export",
            "reason": "syntax-only export URI; alias and public binding resolution remain unexplained",
            "uri": "src/reexported.dart",
        }
    ]
    annotation_names = {
        path.stem for path in (host / "reports/explanations/dart/annotations").glob("*.md")
    }
    assert annotation_names == {row["symbol_key"] for row in explanation["selected"]}
    assert (host / "reports/explanations/dart/unexplained.txt").is_file()
    assert (host / "reports/explanations/dart/surprises.txt").read_text() == ""
    for row in explanation["selected"]:
        source = (host / row["file"]).read_bytes()[row["span"]["offset"] : row["span"]["end"]]
        assert hashlib.sha256(source).hexdigest() == row["spelling_sha256"]

    complexity = _final(host, "complexity")
    assert complexity["status"] == "complete"
    assert [(row["function"], row["branch_score"]) for row in complexity["findings"]] == [
        ("routeInvoice", 18)
    ]
    hotspot = complexity["findings"][0]
    assert {row["kind"] for row in hotspot["branch_events"]} == {
        "if",
        "for",
        "while",
        "do",
        "switch_case",
        "catch",
        "logical_and",
        "logical_or",
    }
    assert "nestedClosureDecoy" not in json.dumps(complexity["findings"])
    assert "localFunctionDecoy" not in json.dumps(complexity["findings"])
    assert (_output(host, "complexity").parent / "latest").resolve() == _output(
        host, "complexity"
    ).resolve()

    duplication = _final(host, "duplication")
    assert duplication["scan_meta"]["status"] == "complete"
    assert len(duplication["findings"]) == 1
    clone = duplication["findings"][0]
    assert {site["symbol"] for site in clone["sites"]} == {
        "normalizeInvoice",
        "normalizePayment",
    }
    assert clone["multiplicity"] == 2
    assert clone["shared_lines_min"] == 6
    assert "behaviorallySimilar" not in json.dumps(duplication)
    assert "CloneShapeDecoy" not in json.dumps(duplication)
    assert "tinyOne" not in json.dumps(duplication)
    for site in clone["sites"]:
        source = (host / site["file"]).read_bytes()
        body = source[site["body_span"]["offset"] : site["body_span"]["end"]]
        spelling = source[site["declaration_span"]["offset"] : site["declaration_span"]["end"]]
        assert hashlib.sha256(body).hexdigest() == site["body_sha256"]
        assert hashlib.sha256(spelling).hexdigest() == site["spelling_sha256"]
    assert {path.name for path in _output(host, "duplication").iterdir()} == {
        "collapsed.json",
        "ranked.json",
        "triage.md",
        "findings.json",
        "scan.json",
    }

    omnibus = _final(host, "omnibus")
    candidates = _jsonl(_output(host, "omnibus") / "candidates.jsonl")
    assert {row["file"] for row in candidates} == {
        "lib/omnibus.dart",
        "lib/cohesive_control.dart",
    }
    assert omnibus["status"] == "complete"
    assert omnibus["human_scout_accounting"] == {
        "candidates_total": 2,
        "graded": 2,
        "ungraded": 0,
    }
    assert [(row["file"], row["bucket"]) for row in omnibus["scout_verdicts"]] == [
        ("lib/cohesive_control.dart", "facets_not_domains"),
        ("lib/omnibus.dart", "confirmed_omnibus"),
    ]
    assert [(row["file"], row["bucket"]) for row in omnibus["findings"]] == [
        ("lib/omnibus.dart", "confirmed_omnibus")
    ]
    assert len(_jsonl(_output(host, "omnibus") / "omnibus.jsonl")) == 1
    assert len(list((_output(host, "omnibus") / "scout").glob("*.json"))) == 2
    for candidate in candidates:
        assert candidate["candidate_sha256"]
        assert all(row["spelling_sha256"] for row in candidate["declarations"])
    assert "omnibus_decoys" not in json.dumps(candidates)
    assert "excluded_" not in json.dumps(candidates)

    assert _state(host) == before
    assert not (host / ".dart_tool").exists()
    assert not (host / "pubspec.lock").exists()


def test_clean_and_private_only_outcomes_are_explicit(tmp_path: Path) -> None:
    host = _copy_host(tmp_path, "clean")
    before = _state(host)
    facts_path = tmp_path / "dart-d3-clean-facts.json"
    facts = _facts(host, facts_path)
    assert facts["status"] == "complete"

    for kind in ADAPTERS:
        _invoke(host, facts_path, kind)

    explanation = _final(host, "explain")
    assert explanation["status"] == "complete"
    assert explanation["public_symbol_count"] == 0
    assert explanation["selected"] == []
    assert explanation["unexplained"] == []
    assert not list((host / "reports/explanations/dart/annotations").glob("*.md"))
    assert _final(host, "complexity")["findings"] == []
    assert _final(host, "duplication")["findings"] == []
    omnibus = _final(host, "omnibus")
    assert omnibus["findings"] == []
    assert omnibus["human_scout_accounting"] == {
        "candidates_total": 0,
        "graded": 0,
        "ungraded": 0,
    }
    assert _state(host) == before


def test_ungraded_omnibus_candidate_never_becomes_confirmed(tmp_path: Path) -> None:
    host = _copy_host(tmp_path, "positive")
    facts_path = tmp_path / "facts.json"
    _facts(host, facts_path)
    _invoke(host, facts_path, "omnibus", expected=2)
    final = _final(host, "omnibus")
    assert (final["status"], final["failure_kind"]) == (
        "partial",
        "human_scout_required",
    )
    assert final["findings"] == []
    assert final["human_scout_accounting"] == {
        "candidates_total": 2,
        "graded": 0,
        "ungraded": 2,
    }
    assert _jsonl(_output(host, "omnibus") / "omnibus.jsonl") == []


def test_complexity_keeps_source_bound_leads_when_only_native_contract_is_missing(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path, "positive")
    before = _state(host)
    facts_path = tmp_path / "partial-facts.json"
    _run(
        PRODUCT_PYTHON,
        "-I",
        "-S",
        SNAPSHOT,
        "--project-root",
        host,
        "--target",
        "lib",
        "--output",
        facts_path,
        "--dart",
        DART,
        cwd=host,
        expected=2,
    )
    external = tmp_path / "external-artifacts" / "dart"

    _run(
        PRODUCT_PYTHON,
        "-I",
        "-S",
        ADAPTERS["complexity"],
        "--project-root",
        host,
        "--target",
        "lib",
        "--facts",
        facts_path,
        "--output-dir",
        external,
        "--no-host-write",
        cwd=tmp_path,
        expected=2,
    )

    report = json.loads((external / "findings.json").read_text(encoding="utf-8"))
    assert (report["status"], report["outcome"]) == ("partial", "incomplete")
    assert [(row["function"], row["branch_score"]) for row in report["findings"]] == [
        ("routeInvoice", 18)
    ]
    assert "Incomplete evidence" in (external / "report.md").read_text(encoding="utf-8")
    assert _state(host) == before
    assert not (host / "reports").exists()


@pytest.mark.parametrize("kind", list(ADAPTERS))
def test_each_consumer_rejects_stale_snapshot_independently(tmp_path: Path, kind: str) -> None:
    host = _copy_host(tmp_path, "positive")
    facts_path = tmp_path / "facts.json"
    _facts(host, facts_path)
    source = host / "lib/public_surface.dart"
    source.write_bytes(source.read_bytes() + b"\n")
    _invoke(host, facts_path, kind, expected=2)
    final = _final(host, kind)
    status = final["status"] if kind != "duplication" else final["scan_meta"]["status"]
    failure = final["failure_kind"] if kind != "duplication" else final["scan_meta"]["failure_kind"]
    assert (status, failure) == ("failed", "dart_d3_snapshot_stale")


def test_same_destination_complete_failed_complete_clears_stale_success(tmp_path: Path) -> None:
    host = _copy_host(tmp_path, "positive")
    facts_path = tmp_path / "facts.json"
    _facts(host, facts_path)
    _run_positive_consumers(host, facts_path)

    source = host / "lib/complexity.dart"
    original = source.read_bytes()
    source.write_bytes(original + b"\nvoid malformed( {\n")
    failed_facts = _facts(host, facts_path, expected=2)
    assert (failed_facts["status"], failed_facts["failure_kind"]) == (
        "failed",
        "dart_parse_diagnostics",
    )
    for kind in ADAPTERS:
        _invoke(host, facts_path, kind, expected=2)
        final = _final(host, kind)
        if kind == "duplication":
            assert final["scan_meta"]["status"] == "failed"
            assert final["findings"] == []
        else:
            assert final["status"] == "failed"
            assert final.get("findings", []) == []
    assert not list((host / "reports/explanations/dart/annotations").glob("*.md"))
    assert not (_output(host, "complexity").parent / "latest").exists()

    source.write_bytes(original)
    recovered = _facts(host, facts_path)
    assert recovered["status"] == "complete"
    _run_positive_consumers(host, facts_path)
    assert _final(host, "explain")["selected"]
    assert _final(host, "complexity")["findings"]
    assert _final(host, "duplication")["findings"]
    assert _final(host, "omnibus")["findings"]


def test_copied_on_demand_closure_partial_recovery_and_source_preservation(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path, "positive")
    before = _state(host)
    installed = tmp_path / "installed/.agents/skills/on-demand"
    copied_adapters: dict[str, Path] = {}
    for kind, source in ADAPTERS.items():
        skill = source.parents[1]
        destination = installed / skill.name
        shutil.copytree(skill, destination)
        copied_adapters[kind] = destination / "scripts" / source.name
    shutil.copytree(ROOT / ".claude/skills/_dart", installed / "_dart")
    copied_snapshot = installed / "_dart/scripts/dart_d3_snapshot.py"
    copied_provider = installed / "_dart/scripts/dart_syntax_facts.py"
    unrelated = tmp_path / "unrelated-cwd"
    unrelated.mkdir()
    facts_path = tmp_path / "copied-facts.json"

    complete = _facts(host, facts_path, snapshot=copied_snapshot, cwd=unrelated)
    assert complete["status"] == "complete"
    _run_positive_consumers(host, facts_path, adapters=copied_adapters, cwd=unrelated)

    saved_provider = copied_provider.read_bytes()
    copied_provider.unlink()
    partial = _facts(
        host,
        facts_path,
        snapshot=copied_snapshot,
        cwd=unrelated,
        expected=2,
    )
    assert (partial["status"], partial["failure_kind"]) == (
        "partial",
        "dart_syntax_provider_missing",
    )
    for kind in ADAPTERS:
        _invoke(
            host,
            facts_path,
            kind,
            adapter=copied_adapters[kind],
            cwd=unrelated,
            expected=2,
        )
        final = _final(host, kind)
        status = final["status"] if kind != "duplication" else final["scan_meta"]["status"]
        assert status == "partial"
    assert not list((host / "reports/explanations/dart/annotations").glob("*.md"))
    assert not (_output(host, "complexity").parent / "latest").exists()

    copied_provider.write_bytes(saved_provider)
    recovered = _facts(host, facts_path, snapshot=copied_snapshot, cwd=unrelated)
    assert recovered["status"] == "complete"
    _run_positive_consumers(host, facts_path, adapters=copied_adapters, cwd=unrelated)
    assert _final(host, "omnibus")["findings"]
    assert _state(host) == before
    assert not (host / ".dart_tool").exists()
    assert not (host / "pubspec.lock").exists()


def test_one_union_provider_start_is_faster_than_four_starts(tmp_path: Path) -> None:
    union_host = _copy_host(tmp_path, "clean")
    started = time.perf_counter()
    union = _facts(union_host, tmp_path / "union.json")
    union_seconds = time.perf_counter() - started
    union_analyzer_seconds = union["provider"]["tool_package"]["execution"]["duration_seconds"]

    separate_seconds = 0.0
    observations: list[float] = []
    analyzer_observations: list[float] = []
    for index in range(4):
        host = _copy_host(tmp_path / f"separate-{index}", "clean")
        started = time.perf_counter()
        payload = _facts(host, tmp_path / f"separate-{index}.json")
        elapsed = time.perf_counter() - started
        observations.append(elapsed)
        analyzer_observations.append(
            payload["provider"]["tool_package"]["execution"]["duration_seconds"]
        )
        separate_seconds += elapsed
    print(
        json.dumps(
            {
                "union_seconds": round(union_seconds, 4),
                "four_start_observations": [round(value, 4) for value in observations],
                "four_start_seconds": round(separate_seconds, 4),
                "union_analyzer_seconds": union_analyzer_seconds,
                "four_start_analyzer_observations": analyzer_observations,
                "four_start_analyzer_seconds": round(sum(analyzer_observations), 4),
            },
            sort_keys=True,
        )
    )
    assert union_seconds < separate_seconds


def test_provider_and_locked_tool_are_consumed_unchanged() -> None:
    assert hashlib.sha256(PROVIDER.read_bytes()).hexdigest() == (
        "c162ad0393237ef9f5a1541768f24f14303ba9e66ee24762d21ddb1261bbf6e0"
    )
    assert hashlib.sha256((TOOL / "bin/dart_syntax_facts.dart").read_bytes()).hexdigest() == (
        "db03bb4f7a2b4914f8242641d44a7f29d3abb22324d576fc5a69f07fc1aab560"
    )
    assert "package:analyzer/src/" not in (TOOL / "bin/dart_syntax_facts.dart").read_text()
    for adapter in ADAPTERS.values():
        text = adapter.read_text(encoding="utf-8")
        assert "dart_syntax_facts" not in text
        assert "package:analyzer" not in text
