#!/usr/bin/env python3
"""Run Codex targets without ambient project hooks, plugins, or saved sessions."""
from __future__ import annotations

import os
import shutil
import sys


def main() -> None:
    codex = os.environ.get("SKILLOPT_REAL_CODEX") or shutil.which("codex")
    if not codex:
        raise SystemExit("Codex CLI is not on PATH; set SKILLOPT_REAL_CODEX")
    arguments = list(sys.argv[1:])
    if not arguments or arguments[0] != "exec":
        raise SystemExit("the SkillOpt isolation wrapper supports only `codex exec`")
    isolated = [
        arguments[0],
        "--ignore-user-config",
        "--ignore-rules",
        "--ephemeral",
        "--disable",
        "hooks",
        "--disable",
        "plugins",
        "--disable",
        "apps",
        "--disable",
        "multi_agent",
        "--disable",
        "goals",
        *arguments[1:],
    ]
    os.execv(codex, [codex, *isolated])


if __name__ == "__main__":
    main()
