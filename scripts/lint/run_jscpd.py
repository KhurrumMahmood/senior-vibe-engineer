#!/usr/bin/env python3
"""Pinned jscpd wrapper for the find-duplication skill."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


DEFAULT_JSCPD_VERSION = "4.0.5"
DEFAULT_NPM_CACHE = Path(tempfile.gettempdir()) / "your-project-jscpd-npm-cache"


@dataclass(frozen=True)
class JscpdOptions:
    targets: tuple[str, ...]
    output: str
    version: str = DEFAULT_JSCPD_VERSION
    npm_cache: str = str(DEFAULT_NPM_CACHE)
    npx_bin: str = "npx"
    mode: str = "weak"
    threshold: str = "5"
    reporters: str = "json,html"
    offline_ok: bool = False


def build_command(options: JscpdOptions) -> list[str]:
    return [
        options.npx_bin,
        "--yes",
        f"jscpd@{options.version}",
        "--mode",
        options.mode,
        "--threshold",
        options.threshold,
        "--reporters",
        options.reporters,
        "--output",
        options.output,
        *options.targets,
    ]


def build_env(options: JscpdOptions, base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base_env or os.environ)
    env["NPM_CONFIG_CACHE"] = options.npm_cache
    env.setdefault("NPM_CONFIG_AUDIT", "false")
    env.setdefault("NPM_CONFIG_FUND", "false")
    env.setdefault("NPM_CONFIG_UPDATE_NOTIFIER", "false")
    return env


def write_skipped_report(
    options: JscpdOptions,
    command: list[str],
    returncode: int,
    stderr: str,
) -> None:
    output_dir = Path(options.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "duplicates": [],
        "statistics": {},
        "run": {
            "status": "skipped_lexical",
            "tool": "jscpd",
            "version": options.version,
            "targets": list(options.targets),
            "command": command,
            "returncode": returncode,
            "stderr": stderr.strip()[-4000:],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    (output_dir / "jscpd-report.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    (output_dir / "skipped-lexical.json").write_text(
        json.dumps(payload["run"], indent=2), encoding="utf-8"
    )


def run_jscpd(
    options: JscpdOptions,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> int:
    Path(options.output).mkdir(parents=True, exist_ok=True)
    Path(options.npm_cache).mkdir(parents=True, exist_ok=True)
    command = build_command(options)
    result = runner(
        command,
        text=True,
        env=build_env(options),
        capture_output=True,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.returncode == 0:
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        return 0
    if not options.offline_ok:
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        return result.returncode

    write_skipped_report(
        options,
        command,
        result.returncode,
        result.stderr or result.stdout or "",
    )
    print(
        "[run_jscpd] lexical duplicate scan skipped; "
        f"wrote {Path(options.output) / 'jscpd-report.json'}",
        file=sys.stderr,
    )
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="+", help="Files or directories for jscpd")
    parser.add_argument("--output", required=True, help="jscpd report directory")
    parser.add_argument(
        "--version",
        default=DEFAULT_JSCPD_VERSION,
        help=f"Pinned jscpd version (default {DEFAULT_JSCPD_VERSION})",
    )
    parser.add_argument(
        "--npm-cache",
        default=str(DEFAULT_NPM_CACHE),
        help=f"Deterministic npm cache directory (default {DEFAULT_NPM_CACHE})",
    )
    parser.add_argument("--npx-bin", default="npx", help=argparse.SUPPRESS)
    parser.add_argument("--mode", default="weak")
    parser.add_argument("--threshold", default="5")
    parser.add_argument("--reporters", default="json,html")
    parser.add_argument(
        "--offline-ok",
        action="store_true",
        help="Write an empty skipped-lexical report instead of failing when npx fails",
    )
    return parser.parse_args(argv)


def options_from_args(args: argparse.Namespace) -> JscpdOptions:
    return JscpdOptions(
        targets=tuple(args.targets),
        output=args.output,
        version=args.version,
        npm_cache=args.npm_cache,
        npx_bin=args.npx_bin,
        mode=args.mode,
        threshold=args.threshold,
        reporters=args.reporters,
        offline_ok=args.offline_ok,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run_jscpd(options_from_args(args))


if __name__ == "__main__":
    raise SystemExit(main())
