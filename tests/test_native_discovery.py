from __future__ import annotations

from pathlib import Path
import os
import sys

import pytest

from _lib.native_discovery import (
    NativeDiscoveryParseError,
    NativeSkillRow,
    parse_gemini_skills_list,
    validate_gemini_skills_list_stderr,
)
from _lib.skill_installer import LifecycleError, _run_native_command


def _output(root: Path) -> bytes:
    first = (root / ".gemini/skills/host-skill/SKILL.md").resolve()
    second = (root / ".gemini/skills/which-shape/SKILL.md").resolve()
    return (
        "Ripgrep is not available. Falling back to GrepTool.\n"
        "Discovered Agent Skills:\n\n"
        "host-skill [Enabled]\n"
        "  Description: Host-owned fixture.\n"
        f"  Location:    {first}\n\n"
        "which-shape [Enabled]\n"
        "  Description: Toolkit fixture.\n"
        f"  Location:    {second}\n\n"
    ).encode()


def test_gemini_parser_returns_strict_enabled_name_location_rows(tmp_path: Path) -> None:
    rows = parse_gemini_skills_list(_output(tmp_path), project_root=tmp_path)

    assert rows == (
        NativeSkillRow(
            name="host-skill",
            location=(tmp_path / ".gemini/skills/host-skill/SKILL.md").resolve(),
        ),
        NativeSkillRow(
            name="which-shape",
            location=(tmp_path / ".gemini/skills/which-shape/SKILL.md").resolve(),
        ),
    )


def test_gemini_parser_accepts_only_the_native_empty_inventory_shape(
    tmp_path: Path,
) -> None:
    assert parse_gemini_skills_list(
        b"Ripgrep is not available. Falling back to GrepTool.\nNo skills discovered.\n",
        project_root=tmp_path,
    ) == ()


def test_gemini_parser_accepts_only_known_empty_or_ripgrep_stderr() -> None:
    validate_gemini_skills_list_stderr(b"")
    validate_gemini_skills_list_stderr(
        b"Ripgrep is not available. Falling back to GrepTool.\n"
    )
    with pytest.raises(NativeDiscoveryParseError, match="stderr is malformed"):
        validate_gemini_skills_list_stderr(b"network or model warning\n")


@pytest.mark.parametrize(
    ("attack", "match"),
    [
        (
            b"Discovered Agent Skills:\n\nalpha [Enabled]\n  Description: A.\n",
            "missing Location",
        ),
        (
            b"Discovered Agent Skills:\n\nalpha [Disabled]\n  Location:    /tmp/alpha\n",
            "disabled",
        ),
        (
            b"Discovered Agent Skills:\n\nalpha [Enabled]\n  Location:    /tmp/a\n\n"
            b"alpha [Enabled]\n  Location:    /tmp/b\n",
            "duplicate skill name",
        ),
        (
            b"Discovered Agent Skills:\n\nalpha [Enabled]\n  Location:    /tmp/a\n\n"
            b"beta [Enabled]\n  Location:    /tmp/a\n",
            "duplicate skill location",
        ),
        (
            b"Discovered Agent Skills:\n\nalpha [Enabled]\n  Unknown: x\n"
            b"  Location:    /tmp/a\n",
            "missing Location",
        ),
        (b"Discovered Agent Skills:\n\n", "missing skill rows"),
        (b"No skills discovered.\ntrailing\n", "malformed"),
        (b"\xff", "UTF-8"),
    ],
)
def test_gemini_parser_rejects_malformed_duplicate_missing_and_disabled_rows(
    tmp_path: Path, attack: bytes, match: str
) -> None:
    del tmp_path
    with pytest.raises(NativeDiscoveryParseError, match=match):
        parse_gemini_skills_list(attack, project_root=Path("/"))


def test_gemini_parser_rejects_locations_outside_the_project_root(tmp_path: Path) -> None:
    outside = (tmp_path.parent / "outside/SKILL.md").resolve()
    output = (
        "Discovered Agent Skills:\n\n"
        "alpha [Enabled]\n"
        f"  Location:    {outside}\n"
    ).encode()

    with pytest.raises(NativeDiscoveryParseError, match="outside project root"):
        parse_gemini_skills_list(output, project_root=tmp_path)


def test_native_process_runner_enforces_timeout_and_output_bounds(tmp_path: Path) -> None:
    env = {"PATH": os.environ.get("PATH", os.defpath), "TMPDIR": str(tmp_path)}

    with pytest.raises(LifecycleError, match="output limit"):
        _run_native_command(
            [sys.executable, "-c", "print('x' * 4096)"],
            tmp_path,
            env,
            output_limit_bytes=32,
        )
    with pytest.raises(LifecycleError, match="timeout"):
        _run_native_command(
            [sys.executable, "-c", "import time; time.sleep(1)"],
            tmp_path,
            env,
            timeout_seconds=0.01,
        )
