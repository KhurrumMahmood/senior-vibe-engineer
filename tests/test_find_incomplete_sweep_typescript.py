"""Compiler-backed TypeScript find-incomplete-sweep outcome and closure proof."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "find-incomplete-sweep"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "find-incomplete-sweep-typescript"


def _run(
    *args: str,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _source_hashes(host: Path) -> dict[str, str]:
    return {
        str(path.relative_to(host)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((host / "src").rglob("*.ts*"))
    }


def _prepare_git_trajectory(host: Path) -> None:
    """Make the three present option sites newer than the one old-shape site."""
    calls = host / "src" / "calls.ts"
    current = calls.read_text(encoding="utf-8")
    old_shape = current.replace(" // swept", "")
    assert old_shape != current
    calls.write_text(old_shape, encoding="utf-8")
    assert _run("git", "init", cwd=host).returncode == 0
    assert _run("git", "config", "user.email", "fixture@example.test", cwd=host).returncode == 0
    assert _run("git", "config", "user.name", "Fixture", cwd=host).returncode == 0
    assert _run("git", "add", ".", cwd=host).returncode == 0
    first = _run("git", "commit", "-m", "old request shapes", cwd=host, env={
        **os.environ,
        "GIT_AUTHOR_DATE": "2025-01-01T00:00:00Z",
        "GIT_COMMITTER_DATE": "2025-01-01T00:00:00Z",
    })
    assert first.returncode == 0, first.stdout + first.stderr
    calls.write_text(current, encoding="utf-8")
    assert _run("git", "add", "src/calls.ts", cwd=host).returncode == 0
    second = _run("git", "commit", "-m", "sweep region option", cwd=host, env={
        **os.environ,
        "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
        "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
    })
    assert second.returncode == 0, second.stdout + second.stderr


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE / "host", host)
    install = _run("npm", "ci", "--offline", "--ignore-scripts", cwd=host)
    assert install.returncode == 0, install.stdout + install.stderr
    typecheck = _run("npm", "run", "typecheck", cwd=host)
    assert typecheck.returncode == 0, typecheck.stdout + typecheck.stderr
    native = _run("npm", "test", cwd=host)
    assert native.returncode == 0, native.stdout + native.stderr
    _prepare_git_trajectory(host)
    return host


def _scan(
    skill: Path,
    host: Path,
    *,
    target: str = "src",
    report_name: str = "typescript-scan",
    tsconfig: str = "tsconfig.json",
) -> tuple[subprocess.CompletedProcess[str], Path]:
    report_dir = host / "reports" / "find-incomplete-sweep" / report_name
    result = _run(
        "node",
        str(skill / "scripts" / "detect_typescript_sweep.mjs"),
        "--target", target,
        "--project-root", str(host),
        "--tsconfig", tsconfig,
        "--report-dir", str(report_dir),
        cwd=host,
    )
    return result, report_dir


def _triage(skill: Path, report_dir: Path) -> subprocess.CompletedProcess[str]:
    packets = json.loads((report_dir / "scout_packets.json").read_text(encoding="utf-8"))
    assert packets["packet_count"] == 1
    (report_dir / "scout_verdicts.json").write_text(json.dumps({
        "scan_dir": str(report_dir),
        "verdicts": [{
            "id": packets["packets"][0]["id"],
            "verdict": "forgotten",
            "rationale": "The three newer siblings consistently override the default region.",
            "completion": 'add `region: "us"` to the straggler options object',
        }],
    }, indent=2), encoding="utf-8")
    return _run(sys.executable, str(skill / "scripts" / "triage.py"), "--scan-dir", str(report_dir), cwd=report_dir)


def _documented_command(skill: Path, name: str) -> str:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(
        rf"<!-- installed-command:{name}:start -->\n```bash\n(.*?)\n```\n"
        rf"<!-- installed-command:{name}:end -->",
        text,
        re.DOTALL,
    )
    assert match is not None, name
    return match.group(1)


def test_typescript_resolved_candidate_reaches_packet_verdict_and_triage(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _source_hashes(host)
    result, report_dir = _scan(SKILL, host)

    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((report_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["language"] == "typescript"
    assert manifest["analyzer"] == "typescript-compiler-api"
    assert manifest["status"] == "complete"
    assert manifest["summary"] == {
        "raw_divergence_candidates": 2,
        "gated_in": 1,
        "down_ranked": 1,
        "gated_out": 0,
        "deferred": 1,
    }
    assert manifest["findings"] == [{
        "callee": "buildRequest",
        "kwarg": "region",
        "group_size": 4,
        "present_count": 3,
        "majority_frac": 0.75,
        "straggler": "src/calls.ts:10",
        "present_sites": [
            {"file": "src/calls.ts", "line": 6},
            {"file": "src/calls.ts", "line": 7},
            {"file": "src/calls.ts", "line": 8},
        ],
        "gated_in": True,
        "optional_by_default": False,
        "override_value": '"us"',
        "default_value": '"global"',
        "trajectory": "3/3 option-present sites touched AFTER the straggler — consistent with a sweep that missed it",
    }]
    assert manifest["down_ranked"] == [{
        "callee": "stableRequest",
        "kwarg": "region",
        "group_size": 4,
        "present_count": 3,
        "optional_by_default": True,
        "default_value": '"global"',
    }]
    assert manifest["deferred"] == [{
        "file": "src/framework.ts",
        "line": 8,
        "reason": "framework_or_external_method_signature",
    }]
    assert "buildRequest" in (report_dir / "findings.md").read_text(encoding="utf-8")

    scout = _run(
        sys.executable,
        str(SKILL / "scripts" / "scout.py"),
        "--scan-dir", str(report_dir),
        "--project-root", str(host),
        cwd=host,
    )
    assert scout.returncode == 0, scout.stdout + scout.stderr
    packets = json.loads((report_dir / "scout_packets.json").read_text(encoding="utf-8"))
    assert packets["packet_count"] == 1
    assert packets["packets"][0]["callee"] == "buildRequest"
    assert len(packets["packets"][0]["present_sites"]) == 2

    triage = _triage(SKILL, report_dir)
    assert triage.returncode == 0, triage.stdout + triage.stderr
    rendered = (report_dir / "triaged.md").read_text(encoding="utf-8")
    assert "## Forgotten (1)" in rendered
    assert "/fix-workflow cluster:SW-01" in rendered
    assert "add `region: \"us\"`" in rendered
    assert _source_hashes(host) == before


def test_typescript_invalid_missing_compiler_and_partial_resolution_are_explicit(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    (host / "src" / "unresolved.ts").write_text(
        'import { missing } from "@app/not-here";\nexport const broken = missing;\n',
        encoding="utf-8",
    )
    partial, partial_dir = _scan(SKILL, host, report_name="partial")
    assert partial.returncode == 0, partial.stdout + partial.stderr
    payload = json.loads((partial_dir / "manifest.json").read_text(encoding="utf-8"))
    assert payload["status"] == "partial"
    assert payload["project_resolution"] == {
        "state": "partial",
        "unresolved_modules": [{"file": "src/unresolved.ts", "specifier": "@app/not-here"}],
    }

    (host / "src" / "broken.ts").write_text("export function broken(: string { return ''; }\n", encoding="utf-8")
    syntax, _ = _scan(SKILL, host, target="src/broken.ts", report_name="syntax")
    assert syntax.returncode == 2
    assert "TypeScript syntax errors" in syntax.stderr

    missing_config, _ = _scan(SKILL, host, tsconfig="missing.json", report_name="missing-config")
    assert missing_config.returncode == 2
    assert "project-local TypeScript requires tsconfig" in missing_config.stderr

    no_compiler = tmp_path / "no-compiler"
    shutil.copytree(FIXTURE / "host", no_compiler, ignore=shutil.ignore_patterns("node_modules"))
    missing_compiler, _ = _scan(SKILL, no_compiler, report_name="missing-compiler")
    assert missing_compiler.returncode == 2
    assert "project-local TypeScript package is unavailable" in missing_compiler.stderr


def test_final_triage_oracle_rejects_missing_or_invalid_packet_verdicts(tmp_path: Path) -> None:
    scan_dir = tmp_path / "reports" / "find-incomplete-sweep" / "invalid"
    scan_dir.mkdir(parents=True)
    (scan_dir / "scout_packets.json").write_text(json.dumps({
        "language": "python",
        "packets": [{"id": "SW-01", "callee": "build", "kwarg": "region", "straggler": {"ref": "src/calls.ts:10"}}],
    }), encoding="utf-8")
    (scan_dir / "scout_verdicts.json").write_text(json.dumps({"verdicts": []}), encoding="utf-8")
    missing = _run(sys.executable, str(SKILL / "scripts" / "triage.py"), "--scan-dir", str(scan_dir), cwd=scan_dir)
    assert missing.returncode == 2
    assert "missing packets: SW-01" in missing.stderr

    (scan_dir / "scout_verdicts.json").write_text(json.dumps({"verdicts": [{
        "id": "SW-01", "verdict": "guess", "rationale": "not allowed",
    }]}), encoding="utf-8")
    invalid = _run(sys.executable, str(SKILL / "scripts" / "triage.py"), "--scan-dir", str(scan_dir), cwd=scan_dir)
    assert invalid.returncode == 2
    assert "invalid verdict" in invalid.stderr


def test_typescript_exclusions_symlinks_and_report_containment_are_safe(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    source = host / "src" / "calls.ts"
    before = source.read_bytes()
    for index, target in enumerate(("src/generated", "src/vendor", "src/calls.spec.ts")):
        result, report_dir = _scan(SKILL, host, target=target, report_name=f"excluded-{index}")
        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads((report_dir / "manifest.json").read_text(encoding="utf-8"))
        assert payload["target"]["exclusion"] == "excluded"
        assert payload["findings"] == []

    external = tmp_path / "external"
    external.mkdir()
    (external / "outside.ts").write_text("export const outside = true;\n", encoding="utf-8")
    os.symlink(external, host / "src" / "external-link")
    os.symlink(host / "src" / "vendor", host / "src" / "internal-link")
    broad, _ = _scan(SKILL, host, report_name="symlink-broad")
    assert broad.returncode == 0, broad.stdout + broad.stderr
    for index, target in enumerate(("src/external-link", "src/internal-link")):
        direct, _ = _scan(SKILL, host, target=target, report_name=f"symlink-direct-{index}")
        assert direct.returncode == 2
        assert "symbolic link" in direct.stderr

    shutil.rmtree(host / "reports")
    os.symlink(host / "src", host / "reports")
    unsafe, _ = _scan(SKILL, host, report_name="unsafe")
    assert unsafe.returncode == 2
    assert "symbolic link" in unsafe.stderr
    assert source.read_bytes() == before


def test_typescript_scout_and_triage_keep_the_final_writers_out_of_symlink_outputs(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = (host / "src" / "calls.ts").read_bytes()
    result, report_dir = _scan(SKILL, host, report_name="writer-containment")
    assert result.returncode == 0, result.stdout + result.stderr
    os.symlink(host / "src" / "calls.ts", report_dir / "scout_packets.json")
    unsafe_scout = _run(
        sys.executable, str(SKILL / "scripts" / "scout.py"), "--scan-dir", str(report_dir),
        "--project-root", str(host), cwd=host,
    )
    assert unsafe_scout.returncode == 2
    assert "symbolic link" in unsafe_scout.stderr
    assert (host / "src" / "calls.ts").read_bytes() == before
    (report_dir / "scout_packets.json").unlink()

    safe_scout = _run(
        sys.executable, str(SKILL / "scripts" / "scout.py"), "--scan-dir", str(report_dir),
        "--project-root", str(host), cwd=host,
    )
    assert safe_scout.returncode == 0, safe_scout.stdout + safe_scout.stderr
    packets = json.loads((report_dir / "scout_packets.json").read_text(encoding="utf-8"))
    (report_dir / "scout_verdicts.json").write_text(json.dumps({"verdicts": [{
        "id": packets["packets"][0]["id"],
        "verdict": "forgotten",
        "rationale": "The evidence is a real sweep residue.",
        "completion": 'add `region: "us"` to the straggler options object',
    }]}), encoding="utf-8")
    os.symlink(host / "src" / "calls.ts", report_dir / "triaged.md")
    unsafe_triage = _run(sys.executable, str(SKILL / "scripts" / "triage.py"), "--scan-dir", str(report_dir), cwd=host)
    assert unsafe_triage.returncode == 2
    assert "symbolic link" in unsafe_triage.stderr
    assert (host / "src" / "calls.ts").read_bytes() == before


def test_copied_and_stock_selected_skill_runs_without_checkout_runtime(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _source_hashes(host)
    copied = tmp_path / "installed" / "find-incomplete-sweep"
    shutil.copytree(SKILL, copied)
    copied_result, copied_dir = _scan(copied, host, report_name="copied")
    assert copied_result.returncode == 0, copied_result.stdout + copied_result.stderr
    scout = _run(sys.executable, str(copied / "scripts" / "scout.py"), "--scan-dir", str(copied_dir), "--project-root", str(host), cwd=host)
    assert scout.returncode == 0, scout.stdout + scout.stderr
    assert _triage(copied, copied_dir).returncode == 0
    copied_runtime = "\n".join(
        path.read_text(encoding="utf-8") for path in (copied / "scripts").iterdir() if path.is_file()
    )
    assert "scripts/_lib" not in copied_runtime
    assert "/_common" not in copied_runtime

    install = _run(
        "bash", "-c", _documented_command(SKILL, "stock-install"), cwd=host,
        env={**os.environ, "DO_NOT_TRACK": "1", "FIND_INCOMPLETE_SWEEP_SOURCE": str(REPO_ROOT)},
    )
    assert install.returncode == 0, install.stdout + install.stderr
    installed = host / ".agents" / "skills" / "find-incomplete-sweep"
    assert installed.is_dir()
    assert not installed.resolve().is_relative_to(REPO_ROOT.resolve())
    command = _documented_command(installed, "typescript-scan")
    stock = _run("bash", "-c", command, cwd=host, env={**os.environ, "TARGET": "src", "REPORT_NAME": "stock"})
    assert stock.returncode == 0, stock.stdout + stock.stderr
    stock_dir = host / "reports" / "find-incomplete-sweep" / "stock"
    assert _run(sys.executable, str(installed / "scripts" / "scout.py"), "--scan-dir", str(stock_dir), "--project-root", str(host), cwd=host).returncode == 0
    assert _triage(installed, stock_dir).returncode == 0
    assert "## Forgotten (1)" in (stock_dir / "triaged.md").read_text(encoding="utf-8")
    assert str(REPO_ROOT) not in installed.joinpath("scripts", "detect_typescript_sweep.mjs").read_text(encoding="utf-8")
    assert _run("npm", "run", "typecheck", cwd=host).returncode == 0
    assert _run("npm", "test", cwd=host).returncode == 0
    assert _source_hashes(host) == before


def test_docs_state_the_narrow_compiler_backed_contract() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "language: any" in text
    assert "scans: [python, typescript]" in text
    assert "TypeScript Compiler API" in text
    assert "aliases, resolved object-literal spreads, overloads, and defaults" in text
    assert "framework APIs" in text
