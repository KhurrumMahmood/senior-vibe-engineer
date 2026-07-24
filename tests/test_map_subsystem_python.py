"""Canonical output-boundary checks for the Python subsystem renderer."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / ".claude/skills/map-subsystem/scripts/render_doc.py"


def _render(host: Path, output: str) -> subprocess.CompletedProcess[str]:
    scratch = host / "reports/map/billing"
    scratch.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [
            sys.executable,
            str(RENDERER),
            "--name",
            "billing",
            "--target",
            "src/billing.py",
            "--scratch",
            str(scratch),
            "--output",
            output,
            "--effectiveness-log",
            "",
        ],
        cwd=host,
        check=False,
        capture_output=True,
        text=True,
    )


def test_python_renderer_writes_only_below_canonical_subsystem_home(
    tmp_path: Path,
) -> None:
    canonical = ".engineering/docs/subsystems/billing.md"

    rendered = _render(tmp_path, canonical)

    assert rendered.returncode == 0, rendered.stdout + rendered.stderr
    assert (tmp_path / canonical).is_file()

    for output in (
        ".claude/docs/subsystems/legacy.md",
        "reports/map/outside.md",
    ):
        refused = _render(tmp_path, output)
        assert refused.returncode == 2
        assert "output must stay below .engineering/docs/subsystems" in refused.stderr
        assert not (tmp_path / output).exists()


def test_python_renderer_rejects_symlinked_canonical_parent(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    docs = tmp_path / ".engineering/docs"
    docs.mkdir(parents=True)
    (docs / "subsystems").symlink_to(outside, target_is_directory=True)

    refused = _render(tmp_path, ".engineering/docs/subsystems/billing.md")

    assert refused.returncode == 2
    assert "canonical output parent is a symlink" in refused.stderr
    assert not (outside / "billing.md").exists()
