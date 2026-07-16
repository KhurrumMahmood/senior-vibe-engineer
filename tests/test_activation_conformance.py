from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from _lib.host_profile import profile_host


REPO_ROOT = Path(__file__).resolve().parent.parent
MATCHER = REPO_ROOT / ".claude" / "skills" / "which-skill" / "scripts" / "match.py"
SHAPE = REPO_ROOT / ".claude" / "skills" / "which-shape" / "scripts" / "route.py"
CLEANUP = REPO_ROOT / ".claude" / "skills" / "which-cleanup" / "scripts" / "run.py"
MANIFEST = REPO_ROOT / "scripts" / "manifest.py"


def _seed_typescript_host(root: Path) -> None:
    root.joinpath("package.json").write_text(
        json.dumps(
            {
                "dependencies": {"react": "19.0.0"},
                "devDependencies": {"typescript": "5.9.3"},
                "scripts": {"test": "vitest"},
            }
        ),
        encoding="utf-8",
    )
    root.joinpath("tsconfig.json").write_text("{}\n", encoding="utf-8")
    source = root / "src"
    source.mkdir()
    source.joinpath("App.tsx").write_text("export const App = () => <main />;\n", encoding="utf-8")
    root.joinpath("README.md").write_text("# TypeScript host\n", encoding="utf-8")
    profile_path = root / ".engineering" / "project" / "host-profile.json"
    profile_path.parent.mkdir(parents=True)
    profile_path.write_text(json.dumps(profile_host(root)), encoding="utf-8")


def _run_json(command: list[str], *, cwd: Path) -> tuple[int, dict]:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.stdout, result.stderr
    return result.returncode, json.loads(result.stdout)


def test_all_four_surfaces_share_the_exact_profile_activation_decision(tmp_path):
    _seed_typescript_host(tmp_path)

    manifest_rc, manifest_payload = _run_json(
        [
            sys.executable,
            str(MANIFEST),
            "--project-root",
            str(tmp_path),
            "resolve",
            "--json",
        ],
        cwd=REPO_ROOT,
    )
    skill_rc, skill_payload = _run_json(
        [
            sys.executable,
            str(MATCHER),
            "prevent this recurring regression with a guard",
            "--project-root",
            str(tmp_path),
            "--top",
            "20",
            "--json",
        ],
        cwd=REPO_ROOT,
    )
    shape_rc, shape_payload = _run_json(
        [
            sys.executable,
            str(SHAPE),
            "this bug keeps coming back",
            "--project-root",
            str(tmp_path),
            "--json",
            "--skip-log",
        ],
        cwd=REPO_ROOT,
    )
    cleanup_rc, cleanup_payload = _run_json(
        [
            sys.executable,
            str(CLEANUP),
            "README.md",
            "--project-root",
            str(tmp_path),
            "--json",
            "--skip-effectiveness-log",
            "--now",
            "20260716-000000",
        ],
        cwd=REPO_ROOT,
    )

    assert manifest_rc == 0
    assert skill_rc in {0, 1}
    assert shape_rc == 0
    assert cleanup_rc == 0

    manifest_decision = manifest_payload["decisions"]["prevent-regression"]
    skill_decision = next(
        item["activation"]
        for item in skill_payload["excluded_inactive"]
        if item["name"] == "prevent-regression"
    )
    shape_decision = next(
        item
        for item in shape_payload["recommendation"]["activation_steps"]
        if item["skill"] == "prevent-regression"
    )
    cleanup_decision = next(
        item["activation"]
        for item in cleanup_payload["inactive"]
        if item["skill"] == "prevent-regression"
    )

    decisions = [manifest_decision, skill_decision, shape_decision, cleanup_decision]
    assert all(decision["active"] is False for decision in decisions)
    assert len({tuple(decision["exclusion_reasons"]) for decision in decisions}) == 1
    assert "no profile root matches" in decisions[0]["exclusion_reasons"][-1]
