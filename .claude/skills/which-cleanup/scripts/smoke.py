#!/usr/bin/env python3
"""Fast isolated self-check for the installed /which-cleanup entrypoint."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import route


def main() -> int:
    root = Path.cwd().resolve()
    args = argparse.Namespace(
        paths=["src/app.py", "tests/test_app.py"],
        staged=False,
        changed_from=None,
        commit=None,
        range=None,
        project_root=root,
        library_root=root / ".missing-engineering-skills-library",
        source=route.DEFAULT_SOURCE,
        skills_cli_version=route.DEFAULT_CLI_VERSION,
        agent="codex",
        json=True,
    )

    result = route.build_result(args)
    assert result["target"] == "explicit paths"
    assert result["resolved_paths"] == ["src/app.py", "tests/test_app.py"]
    assert result["scope_band"] == "small"
    assert [item["skill"] for item in result["recommendations"]] == [
        "find-test-obligation-drift",
        "find-comment-drift",
        "prevent-regression",
    ]
    assert all(not item["handoff"]["available"] for item in result["recommendations"])
    assert all(
        item["handoff"]["capabilities"]["reason"] == "manifest_missing"
        for item in result["recommendations"]
    )

    companion_command = route.install_command(
        source=route.DEFAULT_SOURCE,
        version=route.DEFAULT_CLI_VERSION,
        skills=["prevent-regression", "find-implicit-state"],
        agent="codex",
    )
    assert "--skill prevent-regression" in companion_command
    assert "--skill find-implicit-state" in companion_command

    print("which-cleanup smoke: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
