#!/usr/bin/env python3
"""Shared policy checks for local coding agents.

This module is intentionally stdlib-only. Hook runners can call it before the
project virtualenv is installed, while normal project verification still uses
``.venv/bin/python``.

The command-level checks here are universal (venv usage, destructive shell,
network/migration approval). Patch-scanning hooks and stop-hook sensitivity
are *project-specific* — host projects extend ``SENSITIVE_PREFIXES`` and the
``_looks_like_*`` predicates with their own rules. See the placeholders below.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = REPO_ROOT / "logs" / "agent_policy"
TEST_RUN_LOG = LOG_DIR / "test_runs.jsonl"

DECISION_ORDER = {"allow": 0, "warn": 1, "ask": 2, "block": 3}

# Host projects fill this with directories or files whose changes warrant a
# stop-hook "did you run the tests?" gate. Empty by default — the framework
# stays useful as command-level enforcement even when no patch-level surface
# is declared sensitive.
SENSITIVE_PREFIXES: tuple[str, ...] = (
    "scripts/agent_policy/",
)


@dataclass(frozen=True)
class PolicyDecision:
    rule_id: str
    decision: str
    reason: str
    summary: str = ""
    source: str = "automatic"

    def to_record(self, tool: str = "", event: str = "") -> dict[str, str]:
        record = asdict(self)
        record["tool"] = tool
        record["event"] = event
        return record


def strongest_decision(decisions: Iterable[PolicyDecision]) -> PolicyDecision | None:
    strongest: PolicyDecision | None = None
    for decision in decisions:
        if strongest is None:
            strongest = decision
            continue
        if DECISION_ORDER[decision.decision] > DECISION_ORDER[strongest.decision]:
            strongest = decision
    return strongest


def evaluate_command(command: str) -> list[PolicyDecision]:
    command = command.strip()
    if not command:
        return []

    scan_text = _strip_quoted(command)
    decisions: list[PolicyDecision] = []

    if re.search(r"(^|[;&|]\s*)(python|python3)\s+(manage\.py|-m\s+pytest)\b", scan_text):
        decisions.append(
            PolicyDecision(
                "command.require_venv_python",
                "block",
                "Use `.venv/bin/python`, not bare `python` or `python3`, for project commands.",
                command_summary(command),
            )
        )

    destructive_patterns = {
        "command.destructive_rm": r"(^|[;&|]\s*)rm\s+-[A-Za-z]*r[A-Za-z]*f\b",
        "command.git_reset_hard": r"(^|[;&|]\s*)git\s+reset\s+--hard\b",
        "command.git_clean_force": r"(^|[;&|]\s*)git\s+clean\s+-[A-Za-z]*f\b",
        "command.sudo": r"(^|[;&|]\s*)sudo\b",
        "command.chmod_777": r"(^|[;&|]\s*)chmod\s+777\b",
    }
    for rule_id, pattern in destructive_patterns.items():
        if re.search(pattern, scan_text):
            decisions.append(
                PolicyDecision(
                    rule_id,
                    "block",
                    "Destructive command blocked by agent policy; ask the user for an explicit path.",
                    command_summary(command),
                )
            )
            break

    ask_patterns = {
        "command.git_push": r"(^|[;&|]\s*)git\s+push\b",
        "command.git_checkout_dashdash": r"(^|[;&|]\s*)git\s+checkout\s+--\s+",
        "command.django_migration": (
            r"manage\.py\s+(migrate|makemigrations)\b(?!.*--(?:dry-run|check)\b)"
        ),
        "command.package_install": (
            r"(^|[;&|]\s*)((pip|pip3|uv\s+pip|poetry|npm|pnpm|yarn)\s+"
            r"(install|add|update|upgrade|sync|ci)\b)"
        ),
        "command.live_integration": r"(--run-live|RUN_LIVE_INTEGRATION=1)",
    }
    for rule_id, pattern in ask_patterns.items():
        if re.search(pattern, scan_text):
            decisions.append(
                PolicyDecision(
                    rule_id,
                    "ask",
                    "This command crosses a higher-risk boundary and should be user-approved.",
                    command_summary(command),
                )
            )

    return decisions


def scan_patch(patch_text: str, tool_input: dict | None = None) -> list[PolicyDecision]:
    """Scan a proposed patch for project-specific patch-time violations.

    Host projects override the ``_looks_like_*`` predicates and the path
    filter to enforce things like:

    - "isolated runtime packages may not construct model providers directly"
    - "artifact-only packages may not write production rows or dispatch
      background tasks"
    - "resolver/planner prompts may not include scorer-only truth or holdout
      values"

    The base implementation is a no-op — declare the sensitive prefixes and
    predicates that fit your repo before relying on patch-time enforcement.
    """
    if not patch_text and not tool_input:
        return []
    additions = list(_iter_patch_additions(patch_text, tool_input or {}))
    decisions: list[PolicyDecision] = []
    for path, line in additions:
        normalized = _normalize_path(path)
        if not _is_patch_scanned_path(normalized):
            continue

        line_summary = f"{normalized}: {line.strip()[:120]}"
        if _looks_like_direct_provider(line):
            decisions.append(
                PolicyDecision(
                    "patch.isolated_runtime_direct_provider",
                    "block",
                    "Isolated runtime model calls must go through the canonical AI runtime facade.",
                    line_summary,
                )
            )
        if _looks_like_production_write(line):
            decisions.append(
                PolicyDecision(
                    "patch.artifact_only_production_write",
                    "block",
                    "Artifact-only packages must not write production rows or dispatch background tasks.",
                    line_summary,
                )
            )
        if _looks_like_prompt_truth_leak(normalized, line):
            decisions.append(
                PolicyDecision(
                    "patch.prompt_truth_leak",
                    "block",
                    "Resolver/planner prompts must not include scorer-only truth or holdout values.",
                    line_summary,
                )
            )
    return decisions


def evaluate_stop(
    changed_files: Iterable[str] | None = None,
    last_message: str = "",
    test_log_path: Path | None = None,
) -> list[PolicyDecision]:
    files = [_normalize_path(p) for p in (current_changed_files() if changed_files is None else changed_files)]
    sensitive = [p for p in files if is_sensitive_path(p)]
    if not sensitive:
        return []
    if has_recent_test_evidence(test_log_path=test_log_path):
        return []
    if _message_mentions_unrun_tests(last_message):
        return []
    return [
        PolicyDecision(
            "stop.require_verification_note",
            "block",
            "Sensitive files changed. Run relevant tests or state what was not run and why before finishing.",
            ", ".join(sensitive[:5]),
        )
    ]


def record_test_command(
    command: str,
    success: bool,
    log_path: Path | None = None,
    now: datetime | None = None,
) -> bool:
    if not success or not is_test_command(command):
        return False
    path = log_path or TEST_RUN_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": (now or datetime.now(timezone.utc)).isoformat(),
        "command": command_summary(command),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    _trim_test_log(path)
    return True


def has_recent_test_evidence(
    *,
    test_log_path: Path | None = None,
    now: datetime | None = None,
    within_hours: int = 12,
) -> bool:
    path = test_log_path or TEST_RUN_LOG
    if not path.exists():
        return False
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(hours=within_hours)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        # ValueError covers UnicodeDecodeError on a corrupted log.
        return False
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            timestamp = datetime.fromisoformat(data.get("timestamp", ""))
        except (ValueError, json.JSONDecodeError):
            continue
        if timestamp >= cutoff:
            return True
    return False


def is_test_command(command: str) -> bool:
    scan_text = _strip_quoted(command)
    return any(
        marker in scan_text
        for marker in (
            " -m pytest",
            " manage.py test",
            "ruff check",
            "scripts/lint/",
            "scripts/agent_policy/policy.py --self-test",
            "scripts/agent_policy/friction.py summarize",
        )
    )


def is_sensitive_path(path: str) -> bool:
    normalized = _normalize_path(path)
    return any(normalized.startswith(prefix) for prefix in SENSITIVE_PREFIXES)


def current_changed_files() -> list[str]:
    commands = [
        ["git", "diff", "--name-only"],
        ["git", "diff", "--cached", "--name-only"],
    ]
    paths: set[str] = set()
    for cmd in commands:
        try:
            result = subprocess.run(
                cmd,
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            if line.strip():
                paths.add(_normalize_path(line.strip()))
    return sorted(paths)


def command_summary(command: str, limit: int = 240) -> str:
    text = command.strip().replace("\n", " ")
    if "*** Begin Patch" in text or "diff --git" in text:
        return "<patch redacted>"
    text = re.sub(r"(?i)(api[_-]?key|token|secret|password)=\S+", r"\1=<redacted>", text)
    text = re.sub(r"sk-[A-Za-z0-9_-]+", "sk-<redacted>", text)
    text = re.sub(r"\b[A-Za-z0-9_/-]{48,}\b", "<redacted-token>", text)
    return text[:limit]


def _normalize_path(path: str) -> str:
    path = path.strip().replace("\\", "/")
    if path.startswith("b/") or path.startswith("a/"):
        path = path[2:]
    if path.startswith(str(REPO_ROOT)):
        path = str(Path(path).relative_to(REPO_ROOT)).replace("\\", "/")
    return path.lstrip("./")


def _strip_quoted(command: str) -> str:
    # Quoted spans (e.g. grep -E "command|pip install") aren't shell tokens —
    # blank them out so command-detection regexes don't match literal text
    # inside grep queries, message arguments, or doc fragments.
    text = re.sub(r'"[^"]*"', '""', command)
    text = re.sub(r"'[^']*'", "''", text)
    return text


def _trim_test_log(path: Path, *, max_lines: int = 5000) -> None:
    try:
        # ~225 bytes/line average; 5000 lines ≈ 1.1 MB. Skip the trim until
        # the file is comfortably past the cap so most appends just write the
        # new line and return.
        if path.stat().st_size < 1_500_000:
            return
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) <= max_lines:
            return
        kept = lines[-max_lines:]
        # Atomic replace so a concurrent PostToolUse append from another tool
        # call doesn't get clobbered by our truncated rewrite.
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text("\n".join(kept) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        return


def _iter_patch_additions(
    patch_text: str,
    tool_input: dict,
) -> Iterable[tuple[str, str]]:
    current_path = (
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("filename")
        or tool_input.get("file")
        or ""
    )
    if tool_input.get("new_string"):
        for line in str(tool_input["new_string"]).splitlines():
            yield str(current_path), line
    if tool_input.get("content") and current_path:
        for line in str(tool_input["content"]).splitlines():
            yield str(current_path), line
    for raw in patch_text.splitlines():
        if raw.startswith("*** Update File: ") or raw.startswith("*** Add File: "):
            current_path = raw.split(": ", 1)[1].strip()
            continue
        if raw.startswith("+++ b/"):
            current_path = raw[6:].strip()
            continue
        if raw.startswith("+++ "):
            current_path = raw[4:].strip()
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            yield str(current_path), raw[1:]


# --- Project-specific extension surface ----------------------------------
# Replace these stubs with predicates that match your repo's sensitive
# import boundaries, write boundaries, and prompt-safety constraints.


def _is_patch_scanned_path(normalized: str) -> bool:
    """Return True if the patched path belongs to an isolated runtime / sidecar
    surface that should be patch-scanned. Default: no paths are scanned."""
    return False


def _looks_like_direct_provider(line: str) -> bool:
    """Return True if the line constructs a model provider directly instead of
    going through the canonical AI runtime facade. Default: never."""
    return False


def _looks_like_production_write(line: str) -> bool:
    """Return True if the line performs a production write (DB row create/
    update/delete or background-task dispatch) from a package that should be
    artifact-only. Default: never."""
    return False


def _looks_like_prompt_truth_leak(path: str, line: str) -> bool:
    """Return True if a resolver/planner prompt module is being given access
    to scorer-only truth or holdout values. Default: never."""
    return False


def _message_mentions_unrun_tests(message: str) -> bool:
    lowered = message.lower()
    # Unambiguous admissions of not running tests.
    strong_phrases = (
        "not run",
        "did not run",
        "didn't run",
        "was not run",
        "were not run",
        "unable to run",
        "no tests run",
        "no tests were run",
        "skipped the tests",
        "skipped running",
        "skipping the tests",
    )
    if any(phrase in lowered for phrase in strong_phrases):
        return True
    # "skipped tests" / "tests skipped" naturally appear in pytest summaries
    # ("tests skipped 5 cases via @skip") so require an explicit reason marker
    # before treating them as an admission of omission.
    ambiguous_phrases = ("skipped tests", "tests skipped")
    if not any(phrase in lowered for phrase in ambiguous_phrases):
        return False
    reason_markers = (
        "because",
        "since",
        "given",
        "for now",
        "docs-only",
        "documentation",
        "no need",
        "not needed",
    )
    return any(marker in lowered for marker in reason_markers)


def _self_test() -> None:
    assert strongest_decision(evaluate_command("python manage.py test")).rule_id == (
        "command.require_venv_python"
    )
    assert not evaluate_command(".venv/bin/python manage.py test core.tests")
    assert strongest_decision(evaluate_command("rm -rf /tmp/x")).decision == "block"
    assert strongest_decision(evaluate_command("git push origin main")).decision == "ask"

    # git checkout -- is now an ask (downgraded from block)
    checkout_decision = strongest_decision(evaluate_command("git checkout -- foo.py"))
    assert checkout_decision is not None
    assert checkout_decision.rule_id == "command.git_checkout_dashdash"
    assert checkout_decision.decision == "ask"

    # Read-only migration flags don't trigger django_migration ask
    assert not evaluate_command(".venv/bin/python manage.py migrate --dry-run --check")
    assert not evaluate_command(".venv/bin/python manage.py makemigrations --dry-run")
    # Real migrations still ask
    assert strongest_decision(
        evaluate_command(".venv/bin/python manage.py migrate")
    ).rule_id == "command.django_migration"

    # Quoted spans (grep query strings, etc.) don't false-positive
    assert not evaluate_command('grep -E "command|pip install" docs/setup.md')
    assert not evaluate_command("grep -E 'git push' docs/setup.md")
    # Real package installs still ask
    assert strongest_decision(evaluate_command("pip install requests")).rule_id == (
        "command.package_install"
    )

    # is_test_command also ignores markers inside quoted spans
    assert is_test_command(".venv/bin/python -m pytest tests/test_x.py")
    assert not is_test_command('grep -F " -m pytest" docs/runbook.md')

    # Stop-hook unrun-tests phrasing. Pass a non-existent log path so
    # has_recent_test_evidence doesn't short-circuit on real session telemetry.
    sensitive = ["scripts/agent_policy/policy.py"]
    no_log = Path("/tmp/agent_policy_selftest_no_such_log.jsonl")
    # Admissions clear the gate.
    assert not evaluate_stop(sensitive, "tests not run because docs-only", test_log_path=no_log)
    assert not evaluate_stop(sensitive, "skipped tests since this is documentation", test_log_path=no_log)
    assert not evaluate_stop(sensitive, "I was unable to run the suite", test_log_path=no_log)
    # Pytest-summary phrasing must NOT clear the gate (regression guard).
    assert evaluate_stop(sensitive, "All tests passed; no tests failed", test_log_path=no_log)
    assert evaluate_stop(sensitive, "tests skipped 5 unrelated cases via @skip", test_log_path=no_log)
    assert evaluate_stop(sensitive, "Result: no tests broken", test_log_path=no_log)
    assert evaluate_stop(sensitive, "I ran -m pytest. No tests failed.", test_log_path=no_log)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Local agent policy checks")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        _self_test()
        print("agent policy self-test passed")
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
