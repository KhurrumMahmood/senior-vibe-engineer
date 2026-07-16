from __future__ import annotations

import hashlib
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sweep.commands import apply_ratchet, scan_profile
from sweep.native import discover_executable, provider_contracts_from_registry
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
                pytest.skip(f"live provider is unavailable: {contract.provider}")
            prior = resolved.setdefault(contract.provider, executable)
            assert prior == executable
    return resolved


@pytest.mark.sweep_live
@pytest.mark.parametrize(
    ("host", "profile_name", "minimum_before"),
    [
        ("python", "python-case-sensitive.json", 1),
        ("typescript", "typescript-case-sensitive.json", 2),
        ("rust", "rust-case-sensitive.json", 1),
        ("go", "go-case-sensitive.json", 1),
        ("mixed", "mixed-case-sensitive.json", 5),
    ],
)
def test_im_15_live_host_runs_scan_judgment_packet_harness_diff_and_ratchet(
    host: str,
    profile_name: str,
    minimum_before: int,
    tmp_path: Path,
) -> None:
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
    assert before["total"] >= minimum_before

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

    shutil.copytree(HOSTS / host / "after", work, dirs_exist_ok=True)
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
    assert after["total"] == 0

    identifiers = [row["id"] for row in before["findings"]]
    packet = build_packet(
        before,
        judgment,
        finding_ids=identifiers,
        scope=sorted(changed),
        recipe=f"apply the checked-in {host} after fixture",
        verification="/usr/bin/true",
        expected_delta={"fixed": sorted(identifiers), "allowed_new": [], "metrics": []},
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
    assert evidence["diff"]["fixed"] == sorted(identifiers)
    assert evidence["diff"]["new"] == []
    assert evidence["diff"]["persisting"] == []

    ratchet = apply_ratchet(
        before,
        after,
        accepts=[],
        parser_run_context=parser_context,
    )
    assert ratchet.violations == ()
    assert ratchet.tighten is True

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
