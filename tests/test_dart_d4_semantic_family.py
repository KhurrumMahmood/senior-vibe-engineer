from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/dart-d4"
PROVIDER = ROOT / ".claude/skills/map-subsystem/scripts/dart_lsp_facts.py"
MAP = ROOT / ".claude/skills/map-subsystem/scripts/map_dart.py"
DORMANT = ROOT / ".claude/skills/find-dormant/scripts/detect_dart_dormant.py"
RENAME = ROOT / ".claude/skills/rename-concept/scripts/assess_dart_rename.py"
DART = Path("/opt/homebrew/bin/dart")


def _load_provider():
    spec = importlib.util.spec_from_file_location("test_dart_lsp_facts", PROVIDER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(argv: list[str], cwd: Path, *, expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=90, check=False)
    assert result.returncode == expected, result.stdout + result.stderr
    return result


def _copy_fixture(tmp_path: Path, name: str) -> Path:
    destination = tmp_path / name
    shutil.copytree(
        FIXTURE / name, destination, ignore=shutil.ignore_patterns("reports", ".claude")
    )
    return destination


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and "reports" not in path.parts
        and ".claude" not in path.parts
    }


@pytest.fixture(scope="module")
def family_packs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, tuple[Path, Path]]:
    if not DART.is_file():
        pytest.skip("Dart 3.12 SDK is unavailable")
    base = tmp_path_factory.mktemp("dart-d4-packs")
    result: dict[str, tuple[Path, Path]] = {}
    for name, queries in {
        "positive": [
            "_dormant",
            "_used",
            "_registered",
            "_tearOff",
            "_conditionalDormant",
            "OldLedger",
            "NewLedger",
        ],
        "clean": ["_used", "OldLedger", "NewLedger"],
    }.items():
        project = _copy_fixture(base, name)
        output = project / "reports/dart-lsp-facts/family.json"
        _run(
            [
                sys.executable,
                str(PROVIDER),
                "--project-root",
                str(project),
                "--target",
                ".",
                "--dart",
                str(DART),
                "--output",
                "reports/dart-lsp-facts/family.json",
                *sum((["--query", query] for query in queries), []),
            ],
            ROOT,
        )
        result[name] = (project, output)
    return result


def test_provider_positive_clean_capabilities_lineage_cache_and_configuration(
    family_packs: dict[str, tuple[Path, Path]],
) -> None:
    positive = json.loads(family_packs["positive"][1].read_text())
    clean = json.loads(family_packs["clean"][1].read_text())
    assert positive["status"] == "partial"
    assert clean["status"] == "complete"
    assert positive["package_config"]["state"] == "current"
    assert positive["package_config"]["sha256"]
    assert positive["query_plan_sha256"]
    assert positive["fact_pack_sha256"]
    assert positive["missing_capabilities"] == []
    assert positive["diagnostics"] == []
    assert positive["cache"] == {
        "cleanup_verified": True,
        "external": True,
        "owned": True,
        "path_kind": "temporary",
    }
    assert positive["server"]["lifecycle"]["shutdown_acknowledged"] is True
    assert positive["server"]["lifecycle"]["exited_cleanly"] is True
    methods = {row["method"] for row in positive["definition_queries"]}
    assert methods == {"textDocument/definition"}
    assert any(
        row["specifier"].startswith("package:") and row["targets"]
        for row in positive["module_edges"]
    )
    assert any(row["kind"] == "conditional-directive" for row in positive["boundaries"])
    assert not any(str(row).startswith("dart:") for row in positive["workspace_symbols"])
    assert all(
        not target["path"].startswith("/")
        for row in positive["definition_queries"]
        for target in row["targets"]
    )


def test_three_final_outcomes_positive_clean_exclusions_and_hash_agreement(
    family_packs: dict[str, tuple[Path, Path]],
) -> None:
    for name in ("positive", "clean"):
        project, facts = family_packs[name]
        before = _snapshot(project)
        dormant_dir = project / "reports/find-dormant/dart"
        _run(
            [
                sys.executable,
                str(DORMANT),
                "--project-root",
                str(project),
                "--target",
                "lib",
                "--output-dir",
                str(dormant_dir),
                "--facts",
                str(facts),
            ],
            ROOT,
        )
        _run(
            [
                sys.executable,
                str(MAP),
                "--project-root",
                str(project),
                "--target",
                "lib/core",
                "--name",
                f"{name}-core",
                "--output",
                f".claude/docs/subsystems/{name}-core.md",
                "--evidence",
                f"reports/map/{name}-core/dart-map.json",
                "--facts",
                str(facts),
            ],
            ROOT,
        )
        _run(
            [
                sys.executable,
                str(RENAME),
                "OldLedger",
                "NewLedger",
                "--project-root",
                str(project),
                "--target",
                "lib",
                "--output",
                "reports/rename-concept/assessment.json",
                "--facts",
                str(facts),
            ],
            ROOT,
        )
        dormant = json.loads((dormant_dir / "findings.json").read_text())
        scan = json.loads((dormant_dir / "scan.json").read_text())
        mapped = json.loads((project / f"reports/map/{name}-core/dart-map.json").read_text())
        markdown = (project / f".claude/docs/subsystems/{name}-core.md").read_text()
        assessment = json.loads((project / "reports/rename-concept/assessment.json").read_text())
        assert dormant["summary"]["certain_delete"] == 0
        assert scan["certain_delete"] == 0
        assert (dormant_dir / "report.md").is_file()
        assert (dormant_dir / "facts.json").is_file()
        assert mapped["markdown_sha256"] == hashlib.sha256(markdown.encode()).hexdigest()
        assert mapped["map_content_sha256"] in markdown
        assert (
            mapped["query_plan_sha256"]
            == dormant["query_plan_sha256"]
            == assessment["query_plan_sha256"]
        )
        assert _snapshot(project) == before
        assert not any(
            row["path"].startswith(("test/", "generated/", "vendor/", "bin/"))
            for row in mapped["selected_files"]
        )
        assert all(
            any("no Flutter" in item for item in payload["limits"])
            for payload in (dormant, mapped, assessment)
        )
        if name == "positive":
            assert [(row["name"], row["file"]) for row in dormant["candidates"]] == [
                ("_dormant", "lib/core/service.dart")
            ]
            assert dormant["status"] == "partial"
            assert mapped["status"] == "partial"
            assert not any(
                row["source"] == "lib/core/platform.dart" for row in mapped["outbound_edges"]
            )
            assert {row["specifier"] for row in mapped["inbound_edges"]} >= {
                "core/platform_stub.dart",
                "core/models.dart",
                "core/service.dart",
            }
            assert assessment["verdict"] == "HALF-APPLIED / INCOMPLETE"
            assert assessment["strict_text"]["deferred_evidence"]
            assert assessment["assess_only"] is True
        else:
            assert dormant["status"] == "complete"
            assert dormant["candidates"] == []
            assert mapped["status"] == "complete"
            assert assessment["status"] == "complete"
            assert assessment["verdict"] == "COMPLETE"


def test_package_config_missing_stale_and_symlink_are_never_clean(tmp_path: Path) -> None:
    provider = _load_provider()
    for variant in ("missing", "stale", "symlink"):
        project = tmp_path / variant
        shutil.copytree(
            FIXTURE / "clean", project, ignore=shutil.ignore_patterns("reports", ".claude")
        )
        config = project / ".dart_tool/package_config.json"
        if variant == "missing":
            config.unlink()
        elif variant == "stale":
            payload = json.loads(config.read_text())
            payload["packages"][0]["rootUri"] = "../absent-root/"
            config.write_text(json.dumps(payload))
        else:
            external = tmp_path / "external-package-config.json"
            external.write_text(config.read_text())
            config.unlink()
            config.symlink_to(external)
        facts = provider.collect(project, ".", ["NewLedger"], dart=str(DART), timeout=20)
        assert facts["status"] != "complete"
        assert facts["package_config"]["state"] in {"missing", "stale", "invalid"}
        if variant == "symlink":
            assert "symbolic link" in " ".join(facts["package_config"]["problems"])


def test_symlink_directory_and_file_are_recorded_without_traversal(tmp_path: Path) -> None:
    provider = _load_provider()
    project = _copy_fixture(tmp_path, "clean")
    external = tmp_path / "outside"
    external.mkdir()
    (external / "Hidden.dart").write_text("class Hidden {}\n")
    (project / "lib/linked_tree").symlink_to(external, target_is_directory=True)
    (project / "lib/linked_file.dart").symlink_to(external / "Hidden.dart")
    inventory = provider._inventory(project.resolve(), (project / "lib").resolve())
    symlinks = {
        (row["path"], row.get("entry_kind"))
        for row in inventory
        if row["role"] == "symlink-excluded"
    }
    assert symlinks == {("lib/linked_tree", "directory"), ("lib/linked_file.dart", "file")}
    assert not any(row["path"].endswith("Hidden.dart") for row in inventory)


def _fake_dart(path: Path, version: str, server_body: str) -> Path:
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        f"  printf '%s\\n' '{version}' >&2\n"
        "  exit 0\n"
        "fi\n"
        f"{server_body}\n"
    )
    path.chmod(0o755)
    return path


def _fake_capability_lsp(path: Path) -> Path:
    path.write_text(
        """#!/usr/bin/env python3
import json
import sys

if len(sys.argv) > 1 and sys.argv[1] == "--version":
    print("Dart SDK version: 3.12.2 (stable)", file=sys.stderr)
    raise SystemExit(0)

def send(payload):
    body = json.dumps(payload, separators=(",", ":")).encode()
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\\r\\n\\r\\n".encode() + body)
    sys.stdout.buffer.flush()

while True:
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            raise SystemExit(0)
        if line in {b"\\r\\n", b"\\n"}:
            break
        key, value = line.decode().split(":", 1)
        headers[key.lower()] = value.strip()
    message = json.loads(sys.stdin.buffer.read(int(headers["content-length"])))
    method = message.get("method")
    if method == "exit":
        raise SystemExit(0)
    if "id" not in message:
        continue
    if method == "initialize":
        result = {"capabilities": {}}
    elif method == "shutdown":
        result = None
    else:
        result = []
    send({"jsonrpc": "2.0", "id": message["id"], "result": result})
"""
    )
    path.chmod(0o755)
    return path


def test_missing_old_broken_protocol_and_valid_failed_valid_replacement(tmp_path: Path) -> None:
    project = _copy_fixture(tmp_path, "clean")
    output = project / "reports/dart-lsp-facts/reused.json"
    base = [
        sys.executable,
        str(PROVIDER),
        "--project-root",
        str(project),
        "--target",
        ".",
        "--query",
        "NewLedger",
        "--query",
        "_used",
        "--output",
        "reports/dart-lsp-facts/reused.json",
    ]
    _run([*base, "--dart", str(DART)], ROOT)
    assert json.loads(output.read_text())["status"] == "complete"
    assert len(json.loads(output.read_text())["call_hierarchy_queries"]) == 2
    missing = _run([*base, "--dart", str(tmp_path / "missing-dart")], ROOT, expected=2)
    assert "wrote Dart semantic fact pack" in missing.stdout
    assert json.loads(output.read_text())["failure_kind"] == "dart_missing_or_broken"
    assert json.loads(output.read_text())["call_hierarchy_queries"] == []
    old = _fake_dart(tmp_path / "old-dart", "Dart SDK version: 2.19.0 (stable)", "exit 0")
    _run([*base, "--dart", str(old)], ROOT, expected=2)
    assert json.loads(output.read_text())["failure_kind"] == "dart_too_old"
    assert json.loads(output.read_text())["call_hierarchy_queries"] == []
    broken = _fake_dart(
        tmp_path / "broken-dart",
        "Dart SDK version: 3.12.2 (stable)",
        "printf '%s\\n' 'not-an-lsp-frame'; exit 7",
    )
    _run([*base, "--dart", str(broken), "--timeout", "0.2"], ROOT, expected=2)
    assert json.loads(output.read_text())["failure_kind"] == "lsp_protocol_or_process_failure"
    assert json.loads(output.read_text())["call_hierarchy_queries"] == []
    sleepy = _fake_dart(
        tmp_path / "sleepy-dart",
        "Dart SDK version: 3.12.2 (stable)",
        "sleep 1; exit 0",
    )
    _run([*base, "--dart", str(sleepy), "--timeout", "0.1"], ROOT, expected=2)
    assert "timed out" in json.loads(output.read_text())["failure_detail"]
    assert json.loads(output.read_text())["call_hierarchy_queries"] == []
    _run([*base, "--dart", str(DART)], ROOT)
    assert json.loads(output.read_text())["status"] == "complete"
    assert len(json.loads(output.read_text())["call_hierarchy_queries"]) == 2


def test_missing_lsp_capabilities_are_partial(tmp_path: Path) -> None:
    provider = _load_provider()
    project = _copy_fixture(tmp_path, "clean")
    fake = _fake_capability_lsp(tmp_path / "capability-dart")
    facts = provider.collect(project, ".", ["NewLedger"], dart=str(fake), timeout=2)
    assert facts["status"] == "partial"
    assert set(facts["missing_capabilities"]) == {
        "call_hierarchy",
        "definition",
        "document_symbol",
        "references",
        "rename",
        "workspace_symbol",
    }


def test_stale_fact_pack_and_package_hash_are_rejected(
    family_packs: dict[str, tuple[Path, Path]],
) -> None:
    provider = _load_provider()
    project, facts_path = family_packs["clean"]
    source = project / "lib/core/models.dart"
    original = source.read_text()
    source.write_text(f"{original}\n")
    with pytest.raises(provider.DartFactError, match="stale"):
        provider.load_or_collect(
            facts=facts_path,
            project_root=project,
            target="lib",
            queries=["NewLedger"],
            dart=str(DART),
            packages=None,
            cache_dir=None,
            timeout=5,
        )
    source.write_text(original)
    config = project / ".dart_tool/package_config.json"
    original_config = config.read_text()
    config.write_text(original_config + "\n")
    with pytest.raises(provider.DartFactError, match="configuration is stale"):
        provider.load_or_collect(
            facts=facts_path,
            project_root=project,
            target="lib",
            queries=["NewLedger"],
            dart=str(DART),
            packages=None,
            cache_dir=None,
            timeout=5,
        )
    config.write_text(original_config)


def test_copied_isolated_closure_and_provider_sharing_economics(
    tmp_path: Path,
) -> None:
    project = _copy_fixture(tmp_path, "clean")
    closure = tmp_path / "installed/.agents/skills"
    for script, relative in (
        (PROVIDER, "map-subsystem/scripts/dart_lsp_facts.py"),
        (MAP, "map-subsystem/scripts/map_dart.py"),
        (DORMANT, "find-dormant/scripts/detect_dart_dormant.py"),
        (RENAME, "rename-concept/scripts/assess_dart_rename.py"),
    ):
        destination = closure / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(script, destination)
    facts = project / "reports/dart-lsp-facts/copied.json"
    _run(
        [
            sys.executable,
            str(closure / "map-subsystem/scripts/dart_lsp_facts.py"),
            "--project-root",
            str(project),
            "--target",
            ".",
            "--query",
            "_used",
            "--query",
            "OldLedger",
            "--query",
            "NewLedger",
            "--output",
            "reports/dart-lsp-facts/copied.json",
            "--dart",
            str(DART),
        ],
        tmp_path,
    )
    _run(
        [
            sys.executable,
            str(closure / "find-dormant/scripts/detect_dart_dormant.py"),
            "--project-root",
            str(project),
            "--target",
            "lib",
            "--output-dir",
            "reports/find-dormant/copied",
            "--facts",
            str(facts),
        ],
        tmp_path,
    )
    _run(
        [
            sys.executable,
            str(closure / "map-subsystem/scripts/map_dart.py"),
            "--project-root",
            str(project),
            "--target",
            "lib/core",
            "--name",
            "copied",
            "--output",
            ".claude/docs/subsystems/copied.md",
            "--evidence",
            "reports/map/copied/dart-map.json",
            "--facts",
            str(facts),
        ],
        tmp_path,
    )
    _run(
        [
            sys.executable,
            str(closure / "rename-concept/scripts/assess_dart_rename.py"),
            "OldLedger",
            "NewLedger",
            "--project-root",
            str(project),
            "--target",
            "lib",
            "--output",
            "reports/rename-concept/copied.json",
            "--facts",
            str(facts),
        ],
        tmp_path,
    )
    assert (
        json.loads((project / "reports/rename-concept/copied.json").read_text())["verdict"]
        == "COMPLETE"
    )
    provider_loc = sum(1 for line in PROVIDER.read_text().splitlines() if line.strip())
    consumer_loc = sum(
        sum(1 for line in path.read_text().splitlines() if line.strip())
        for path in (MAP, DORMANT, RENAME)
    )
    duplicated = consumer_loc + 3 * provider_loc
    shared = consumer_loc + provider_loc
    savings = (duplicated - shared) / duplicated
    assert savings >= 0.25


def test_native_analyze_format_direct_test_and_smoke() -> None:
    if not DART.is_file():
        pytest.skip("Dart 3.12 SDK is unavailable")
    for name in ("positive", "clean"):
        project = FIXTURE / name
        _run([str(DART), "analyze", "--fatal-infos", "--fatal-warnings", "."], project)
        _run(
            [str(DART), "format", "--output=none", "--set-exit-if-changed", "lib", "bin", "test"],
            project,
        )
        _run([str(DART), "test/native_test.dart"], project)
        smoke = _run([str(DART), "bin/smoke.dart"], project)
        assert smoke.stdout.strip() == "42"
