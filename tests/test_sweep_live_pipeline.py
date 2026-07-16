from __future__ import annotations

import hashlib
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sweep.commands import apply_ratchet, scan_profile
from sweep.native import (
    ProviderExecutionError,
    discover_executable,
    provider_contracts_from_registry,
)
from sweep.pipeline import (
    build_judgment,
    build_packet,
    render_judged_digest,
    run_scan_command,
    verify_packet,
)
from sweep.profile import load_sweep_profile
from sweep.schemas import packet_budget_ceiling, trusted_parser_run_context


ROOT = Path(__file__).resolve().parents[1]
HOSTS = ROOT / "tests/fixtures/sweep/hosts"
PROFILES = ROOT / "tests/fixtures/sweep/profiles"
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
LIVE_ORACLES = {
    "python": {
        "before": ["f2_306c3f8e0d679aa8de104cf7", "f2_79c0112b725363f5367a34d9"],
        "after": ["f2_2deb160996a2b02d7891da7c", "f2_306c3f8e0d679aa8de104cf7"],
        "fixed": ["f2_79c0112b725363f5367a34d9"],
        "new": ["f2_2deb160996a2b02d7891da7c"],
        "persisting": ["f2_306c3f8e0d679aa8de104cf7"],
    },
    "typescript": {
        "before": ["f2_485801a771ad1d85440ddbcd", "f2_6a4cc33709ec5b3b1f6dfb40"],
        "after": [],
        "fixed": ["f2_485801a771ad1d85440ddbcd", "f2_6a4cc33709ec5b3b1f6dfb40"],
        "new": [],
        "persisting": [],
    },
    "rust": {
        "before": ["f2_0a30d4b2ed757586e5b2af8a", "f2_2d64d3db8dba1ee27aeea997"],
        "after": [],
        "fixed": ["f2_0a30d4b2ed757586e5b2af8a", "f2_2d64d3db8dba1ee27aeea997"],
        "new": [],
        "persisting": [],
    },
    "go": {
        "before": ["f2_3ebb34b1a5167a9fcfa0599e"],
        "after": [],
        "fixed": ["f2_3ebb34b1a5167a9fcfa0599e"],
        "new": [],
        "persisting": [],
    },
    "mixed": {
        "before": [
            "f2_0a30d4b2ed757586e5b2af8a",
            "f2_1db54af1a533aac716464a57",
            "f2_2d64d3db8dba1ee27aeea997",
            "f2_3ebb34b1a5167a9fcfa0599e",
            "f2_a49b292322bd714e190d40d0",
            "f2_b2d8d610eed0a5b6c897960d",
        ],
        "after": [],
        "fixed": [
            "f2_0a30d4b2ed757586e5b2af8a",
            "f2_1db54af1a533aac716464a57",
            "f2_2d64d3db8dba1ee27aeea997",
            "f2_3ebb34b1a5167a9fcfa0599e",
            "f2_a49b292322bd714e190d40d0",
            "f2_b2d8d610eed0a5b6c897960d",
        ],
        "new": [],
        "persisting": [],
    },
}


def _source(revision: str, *, dirty: bool = False, dirty_bytes: bytes = b"") -> dict[str, object]:
    return {
        "revision": revision,
        "dirty": dirty,
        "dirty_state_hash": hashlib.sha256(dirty_bytes).hexdigest(),
    }


def _tools(profile_name: str, root: Path) -> dict[str, Path]:
    profile = load_sweep_profile(PROFILES / profile_name)
    resolved: dict[str, Path] = {}
    for language in profile.languages:
        for contract in provider_contracts_from_registry(language):
            executable = discover_executable(contract, root=root)
            if executable is None:
                if os.environ.get("SWEEP_LIVE_REQUIRED") == "1":
                    pytest.fail(f"required live provider is unavailable: {contract.provider}")
                pytest.skip(f"live provider is unavailable: {contract.provider}")
            prior = resolved.setdefault(contract.provider, executable)
            assert prior == executable
    return resolved


def _overlay_tree(source: Path, destination: Path) -> None:
    """Replace fixture bytes without preserving archive-equal stat metadata."""
    stamp = max(path.stat().st_mtime_ns for path in destination.rglob("*") if path.is_file())
    for index, source_path in enumerate(
        sorted(path for path in source.rglob("*") if path.is_file())
    ):
        relative = source_path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source_path.read_bytes())
        os.utime(target, ns=(stamp + index + 1, stamp + index + 1))


@pytest.mark.sweep_live
@pytest.mark.parametrize(
    ("host", "profile_name"),
    [
        ("python", "python-case-sensitive.json"),
        ("typescript", "typescript-case-sensitive.json"),
        ("rust", "rust-case-sensitive.json"),
        ("go", "go-case-sensitive.json"),
        ("mixed", "mixed-case-sensitive.json"),
    ],
)
def test_im_15_live_host_runs_scan_judgment_packet_harness_diff_and_ratchet(
    host: str,
    profile_name: str,
    tmp_path: Path,
) -> None:
    oracle = LIVE_ORACLES[host]
    work = tmp_path / host
    shutil.copytree(HOSTS / host / "before", work)
    work.joinpath(".gitignore").write_text(
        ".ruff_cache/\n__pycache__/\nnode_modules/\ntarget/\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=work, check=True)
    subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=work, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=work, check=True)
    subprocess.run(["git", "add", "."], cwd=work, check=True)
    subprocess.run(["git", "commit", "-qm", "before"], cwd=work, check=True)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=work,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    profile = load_sweep_profile(PROFILES / profile_name)
    tools = _tools(profile_name, work)
    parser_context = trusted_parser_run_context(work)

    before = scan_profile(
        root=work,
        profile=profile,
        source=_source(revision),
        executables=tools,
    )
    assert before["status"] == "complete"
    assert sorted(row["id"] for row in before["findings"]) == oracle["before"]

    outcomes = [
        {
            "finding_id": row["id"],
            "outcome": "actionable",
            "reason": "live fixture regression",
            "evidence": f"live:{host}:{row['id']}",
        }
        for row in before["findings"]
    ]
    judgment = build_judgment(
        before,
        judge_identity="live-fixture-judge",
        judge_version="1",
        outcomes=outcomes,
        parser_run_context=parser_context,
    )
    digest = render_judged_digest(
        before,
        judgment,
        purpose="agent",
        parser_run_context=parser_context,
    )
    assert digest["total_actionable"] == before["total"]

    _overlay_tree(HOSTS / host / "after", work)
    diff_bytes = subprocess.run(
        ["git", "diff", "--binary", "HEAD", "--"],
        cwd=work,
        check=True,
        capture_output=True,
    ).stdout
    changed = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--"],
        cwd=work,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert changed

    after = scan_profile(
        root=work,
        profile=profile,
        source=_source(revision, dirty=True, dirty_bytes=diff_bytes),
        executables=tools,
    )
    assert after["status"] == "complete"
    assert sorted(row["id"] for row in after["findings"]) == oracle["after"]

    packet = build_packet(
        before,
        judgment,
        finding_ids=oracle["fixed"],
        scope=sorted(changed),
        recipe=f"apply the checked-in {host} after fixture",
        verification="/usr/bin/true",
        expected_delta={
            "fixed": oracle["fixed"],
            "allowed_new": oracle["new"],
            "metrics": [],
        },
        token_budget=packet_budget_ceiling(changed, root=work),
        root=work,
        parser_run_context=parser_context,
    )
    scanner = tmp_path / "sweep_cli.py"
    scanner.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT / 'scripts')!r})\n"
        "from sweep.__main__ import main\n"
        "raise SystemExit(main(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    scan_argv = [
        sys.executable,
        str(scanner),
        "scan",
        "--root",
        str(work),
        "--profile",
        str(PROFILES / profile_name),
        "--out",
        str(tmp_path / f"{host}-after-manifest.json"),
        "--revision",
        revision,
        "--dirty",
        "--dirty-state-hash",
        hashlib.sha256(diff_bytes).hexdigest(),
    ]
    for provider, executable in sorted(tools.items()):
        scan_argv.extend(("--tool", f"{provider}={executable}"))
    scan_command = shlex.join(scan_argv)
    evidence = verify_packet(
        packet,
        before,
        judgment,
        root=work,
        scanner=lambda: run_scan_command(scan_command, work),
    )
    assert evidence["verdict"] == "verified"
    assert evidence["diff"]["fixed"] == oracle["fixed"]
    assert evidence["diff"]["new"] == oracle["new"]
    assert evidence["diff"]["persisting"] == oracle["persisting"]

    accepts = [
        {
            "finding_id": finding_id,
            "reason": "live fixture exercises auditable allowed-new ratchet behavior",
            "operator": "live-fixture-test",
            "revision": revision,
            "timestamp": "2026-07-16T20:00:00+00:00",
        }
        for finding_id in oracle["new"]
    ]
    ratchet = apply_ratchet(
        before,
        after,
        accepts=accepts,
        parser_run_context=parser_context,
    )
    assert ratchet.violations == ()
    assert ratchet.tighten is True
    assert [row["finding_id"] for row in ratchet.diff["accepts"]] == oracle["new"]

    clean_root = tmp_path / f"{host}-clean"
    shutil.copytree(HOSTS / host / "clean", clean_root)
    clean = scan_profile(
        root=clean_root,
        profile=profile,
        source=_source("c" * 40),
        executables=tools,
    )
    assert clean["status"] == "complete"
    assert clean["total"] == 0


@pytest.mark.sweep_live
def test_im_15_live_clean_zero_is_distinct_from_provider_failure(tmp_path: Path) -> None:
    root = tmp_path / "python-clean"
    shutil.copytree(HOSTS / "python/clean", root)
    profile_name = "python-case-sensitive.json"
    profile = load_sweep_profile(PROFILES / profile_name)
    tools = _tools(profile_name, root)

    clean = scan_profile(
        root=root,
        profile=profile,
        source=_source("c" * 40),
        executables=tools,
    )
    assert clean["status"] == "complete" and clean["total"] == 0

    with pytest.raises(ProviderExecutionError) as failure:
        scan_profile(
            root=root,
            profile=profile,
            source=_source("c" * 40),
            executables={**tools, "ruff": tmp_path / "missing-ruff"},
        )
    assert failure.value.failure["kind"] == "missing_executable"
