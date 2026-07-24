from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS = REPO_ROOT / ".claude" / "skills"
ROUTERS = {
    "which-skill": SKILLS / "which-skill" / "scripts" / "match.py",
    "which-shape": SKILLS / "which-shape" / "scripts" / "route.py",
    "which-cleanup": SKILLS / "which-cleanup" / "scripts" / "route.py",
}
SOURCE = "https://github.com/KhurrumMahmood/senior-vibe-engineer"  # host-ref-allow: public distribution repository


def _run(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-S", str(script), *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    ("router", "role_text"),
    [
        ("which-skill", "most relevant tactical skill"),
        ("which-shape", "overall workflow and complementary skill sequence"),
        ("which-cleanup", "recent work and recommend the bounded checks"),
    ],
)
def test_help_explains_role_and_is_non_writing(tmp_path, router, role_text):
    host = tmp_path / "host"
    host.mkdir()

    result = _run(ROUTERS[router], "--help", cwd=host)

    assert result.returncode == 0, result.stderr
    assert role_text in result.stdout
    assert "--help only prints this text" in result.stdout
    assert "external project-scoped library" in result.stdout
    assert "Python 3.11+" in result.stdout
    assert list(host.iterdir()) == []


@pytest.mark.parametrize(
    ("router", "args"),
    [
        (
            "which-skill",
            ("map this inherited repository",),
        ),
        (
            "which-shape",
            (
                "onboard",
                "this",
                "unknown",
                "inherited",
                "Python",
                "repository",
                "--skip-log",
            ),
        ),
    ],
)
def test_missing_library_prints_exact_non_executing_repair(tmp_path, router, args):
    host = tmp_path / "host"
    host.mkdir()
    missing_library = tmp_path / "missing-library"

    result = _run(
        ROUTERS[router],
        *args,
        "--project-root",
        str(host),
        "--library-root",
        str(missing_library),
        "--source",
        SOURCE,
        cwd=host,
    )

    assert result.returncode == 0, result.stderr
    expected_script = (
        host
        / ".agents"
        / "skills"
        / "which-skill"
        / "scripts"
        / "bootstrap_library.py"
    )
    assert "Library unavailable. Bootstrap it without running" in result.stdout
    assert str(expected_script) in result.stdout
    assert f"--source {SOURCE}" in result.stdout
    assert "Guide:" not in result.stdout
    assert "Guide /" not in result.stdout
    assert list(host.iterdir()) == []
    assert not missing_library.exists()


def test_readme_uninstall_is_router_scoped():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "npx --yes skills@1.5.19 remove --all" not in readme
    assert "which-shape which-skill which-cleanup" in readme
    assert "--agent codex -y" in readme
    assert "never from the engineering-skills source checkout" in readme
