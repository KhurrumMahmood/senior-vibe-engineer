#!/usr/bin/env python3
"""Run ecosystem AST lint rules with one source of scope truth.

Host projects extend RULES with their own rule specs — keep the
generic rules here, add domain-specific ones in an overlay file or by
appending to RULES at import time.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from path_utils import expand_python_paths, should_skip_dir


RuleName = str


@dataclass(frozen=True)
class RuleSpec:
    name: RuleName
    script: str
    include: re.Pattern[str]
    exclude: re.Pattern[str] | None = None
    suffixes: tuple[str, ...] = (".py",)


# Default scope: anything under app/ or src/ that looks like a service,
# view, page, api, or task layer. Host projects override via INCLUDE_ROOTS.
_DEFAULT_PYTHON_INCLUDE = (
    r"^(?:app|src)/(services|views|pages|api|tasks)/.*\.py$"
)
_DEFAULT_PYTHON_BROAD = r"^(?:app|src)/.*\.py$"


RULES: tuple[RuleSpec, ...] = (
    RuleSpec(
        name="silent-catch",
        script="scripts/lint/silent_catch.py",
        include=re.compile(_DEFAULT_PYTHON_INCLUDE),
        exclude=re.compile(r"^tests/test_.*\.py$"),
    ),
    RuleSpec(
        name="query-mutation",
        script="scripts/lint/no_query_mutation.py",
        include=re.compile(_DEFAULT_PYTHON_INCLUDE),
        exclude=re.compile(r"^tests/test_.*\.py$"),
    ),
    RuleSpec(
        name="bare-delay",
        script="scripts/lint/no_bare_delay.py",
        include=re.compile(_DEFAULT_PYTHON_INCLUDE),
        exclude=re.compile(
            r"^(?:app|src)/(tasks/__init__\.py|views/__init__\.py|"
            r"services/task_dispatch\.py|services/_common/task_dispatch\.py|"
            r"tests_.*\.py)$"
        ),
    ),
    RuleSpec(
        name="stringly-status",
        script="scripts/lint/no_stringly_typed_status.py",
        include=re.compile(_DEFAULT_PYTHON_BROAD),
        exclude=re.compile(
            r"^(?:app|src)/(models/__init__\.py|tests_.*\.py|migrations/.*)$"
        ),
    ),
    RuleSpec(
        name="fat-view",
        script="scripts/lint/no_fat_view.py",
        include=re.compile(r"^(?:app|src)/(?:views|pages|api)/.*\.py$"),
        exclude=re.compile(
            r"^(?:app|src)/(?:views|pages|api)/__init__\.py$"
        ),
    ),
    RuleSpec(
        name="comment-drift",
        script="scripts/lint/no_comment_drift.py",
        include=re.compile(r"^(?:app|src)/.*\.(py|js|html)$"),
        suffixes=(".py", ".js", ".html"),
    ),
    RuleSpec(
        name="codegen-emits-new-paths",
        script="scripts/lint/codegen_emits_new_paths.py",
        include=re.compile(r"^(?:app|src)/.*\.py$"),
    ),
)

RULE_BY_NAME = {rule.name: rule for rule in RULES}
RULE_CHOICES = ("all",) + tuple(rule.name for rule in RULES)


def _repo_relative(path: str, repo_root: Path) -> str | None:
    candidate = Path(path)
    if not candidate.is_absolute():
        return candidate.as_posix()
    try:
        return candidate.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None


def _git_paths(
    git_args: list[str],
    repo_root: Path,
    pathspecs: tuple[str, ...],
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[str]:
    result = runner(
        ["git", *git_args, "--", *pathspecs],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        print(result.stderr.strip() or "git diff failed", file=sys.stderr)
        raise SystemExit(result.returncode)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _suffixes_for_rules(rules: Iterable[RuleSpec]) -> tuple[str, ...]:
    suffixes = {suffix for rule in rules for suffix in rule.suffixes}
    return tuple(sorted(suffixes))


def _pathspecs_for_suffixes(suffixes: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(f"*{suffix}" for suffix in suffixes)


def _dedupe(paths: Iterable[str]) -> list[str]:
    scoped: list[str] = []
    seen: set[str] = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        scoped.append(path)
    return scoped


def _expand_paths_by_suffix(paths: Iterable[str], suffixes: tuple[str, ...]) -> list[str]:
    if suffixes == (".py",):
        return expand_python_paths(paths)

    expanded: list[str] = []
    seen: set[str] = set()

    def add(path: Path | str) -> None:
        display = os.fspath(path)
        key = str(Path(display).resolve()) if Path(display).exists() else display
        if key in seen:
            return
        seen.add(key)
        expanded.append(display)

    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            for dirpath, dirnames, filenames in os.walk(path):
                dirnames[:] = [d for d in sorted(dirnames) if not should_skip_dir(d)]
                for filename in sorted(filenames):
                    candidate = Path(dirpath) / filename
                    if candidate.suffix in suffixes:
                        add(candidate)
            continue

        if path.exists() and path.suffix not in suffixes:
            continue
        add(raw_path)

    return expanded


def collect_candidate_paths(
    args: argparse.Namespace,
    repo_root: Path,
    git_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[str]:
    rules = selected_rules(args.rule)
    suffixes = _suffixes_for_rules(rules)
    pathspecs = _pathspecs_for_suffixes(suffixes)
    if args.staged:
        return _git_paths(
            ["diff", "--name-only", "--cached", "--diff-filter=ACMRT"],
            repo_root,
            pathspecs,
            git_runner,
        )
    if args.changed_from:
        return _git_paths(
            ["diff", "--name-only", "--diff-filter=ACMRT", f"{args.changed_from}...HEAD"],
            repo_root,
            pathspecs,
            git_runner,
        )
    if args.all:
        candidates: list[str] = []
        if ".py" in suffixes:
            candidates.extend(
                expand_python_paths([
                    str(repo_root / "core"),
                    str(repo_root / "app"),
                ])
            )
        if ".js" in suffixes:
            candidates.extend(
                _expand_paths_by_suffix([str(repo_root / "static" / "js")], (".js",))
            )
        if ".html" in suffixes:
            candidates.extend(
                _expand_paths_by_suffix(
                    [str(repo_root / "templates"), str(repo_root / "app")],
                    (".html",),
                )
            )
        return _dedupe(candidates)
    return _expand_paths_by_suffix(args.paths, suffixes)


def selected_rules(rule_name: str) -> tuple[RuleSpec, ...]:
    if rule_name == "all":
        return RULES
    return (RULE_BY_NAME[rule_name],)


def filter_paths_for_rule(
    paths: Iterable[str],
    rule: RuleSpec,
    repo_root: Path,
) -> list[str]:
    scoped: list[str] = []
    seen: set[str] = set()
    for path in paths:
        rel = _repo_relative(path, repo_root)
        if rel is None:
            continue
        rel = rel.replace("\\", "/")
        if any(should_skip_dir(part) for part in rel.split("/")):
            continue
        if not rule.include.search(rel):
            continue
        if rule.exclude and rule.exclude.search(rel):
            continue
        if rel in seen:
            continue
        seen.add(rel)
        scoped.append(rel)
    return scoped


def run_rule(
    rule: RuleSpec,
    paths: list[str],
    repo_root: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> int:
    if not paths:
        print(f"[lint:{rule.name}] no matching files")
        return 0

    print(f"[lint:{rule.name}] {len(paths)} file(s)")
    result = runner(
        [sys.executable, rule.script, *paths],
        cwd=repo_root,
        text=True,
    )
    return result.returncode


def run_rules(
    rules: tuple[RuleSpec, ...],
    candidate_paths: list[str],
    repo_root: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> int:
    exit_code = 0
    for rule in rules:
        scoped = filter_paths_for_rule(candidate_paths, rule, repo_root)
        code = run_rule(rule, scoped, repo_root, runner)
        if code:
            exit_code = max(exit_code, code)
    return exit_code


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--staged", action="store_true", help="Lint staged scoped files")
    source.add_argument(
        "--changed-from",
        metavar="REF",
        help="Lint scoped files changed from REF to HEAD",
    )
    source.add_argument("--all", action="store_true", help="Lint all scoped project files")
    parser.add_argument(
        "--rule",
        default="all",
        choices=RULE_CHOICES,
        help="Rule to run (default: all)",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("paths", nargs="*", help="Explicit files or directories to lint")
    args = parser.parse_args(argv)
    if not (args.staged or args.changed_from or args.all or args.paths):
        parser.error("choose --staged, --changed-from, --all, or pass explicit paths")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    candidates = collect_candidate_paths(args, repo_root)
    rules = selected_rules(args.rule)
    return run_rules(rules, candidates, repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
