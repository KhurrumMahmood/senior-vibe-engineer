#!/usr/bin/env python3
"""Storage and matching for agent-policy grants.

A *grant* is a temporary, scoped exemption from a single policy rule.
The hook reads grants on every PreToolUse to decide whether to downgrade
a block/ask decision to allow.

Stdlib-only, mirrors policy.py's constraint so it works pre-`.venv`.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import secrets
import sys
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GRANTS_PATH = REPO_ROOT / ".claude" / "agent_policy_grants.json"
MAX_DURATION = timedelta(days=30)
AGENT_MAX_DURATION = timedelta(days=1)
SCOPE_KINDS = ("once", "duration", "session")
GRANTED_BY_VALUES = ("user", "agent_after_user_approval")
_COMPOUND_OPERATORS = re.compile(r"(?:&&|\|\||;|\||`|\$\()")


@dataclass
class Grant:
    id: str
    rule_id: str
    scope_kind: str
    expires_at: str | None = None
    session_id: str | None = None
    command_pattern: str | None = None
    path_glob: str | None = None
    remaining_uses: int | None = None
    granted_by: str = "user"
    approval_quote: str | None = None
    reason: str = ""
    granted_at: str = ""

    def is_expired(self, *, now: datetime | None = None) -> bool:
        if self.expires_at:
            try:
                expiry = datetime.fromisoformat(self.expires_at)
            except ValueError:
                return True
            moment = now or datetime.now(timezone.utc)
            if moment >= expiry:
                return True
        if self.remaining_uses is not None and self.remaining_uses <= 0:
            return True
        return False

    def time_to_expiry(self, *, now: datetime | None = None) -> str:
        if not self.expires_at:
            if self.scope_kind == "session":
                return "session"
            if self.remaining_uses is not None:
                return f"{self.remaining_uses} uses left"
            return "never"
        try:
            expiry = datetime.fromisoformat(self.expires_at)
        except ValueError:
            return "<invalid>"
        delta = expiry - (now or datetime.now(timezone.utc))
        seconds = int(delta.total_seconds())
        if seconds <= 0:
            return "expired"
        if seconds < 3600:
            return f"{seconds // 60}m"
        if seconds < 86400:
            return f"{seconds // 3600}h{(seconds % 3600) // 60}m"
        return f"{seconds // 86400}d{(seconds % 86400) // 3600}h"


def now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).isoformat()


def new_grant_id(now: datetime | None = None) -> str:
    moment = now or datetime.now(timezone.utc)
    return f"g_{moment.strftime('%Y-%m-%d')}-{secrets.token_hex(4)}"


def load_grants(path: Path | None = None) -> list[Grant]:
    target = path or DEFAULT_GRANTS_PATH
    if not target.exists():
        return []
    try:
        data = json.loads(target.read_text(encoding="utf-8") or "{}")
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"agent_policy.grants: could not read {target}: {exc}; treating as empty",
            file=sys.stderr,
        )
        return []
    raw_grants = data.get("grants", []) if isinstance(data, dict) else []
    valid_keys = {f.name for f in fields(Grant)}
    result: list[Grant] = []
    for entry in raw_grants:
        if not isinstance(entry, dict):
            continue
        kwargs = {key: entry.get(key) for key in valid_keys if key in entry}
        try:
            grant = Grant(**kwargs)
        except TypeError:
            continue
        if not _is_well_formed(grant):
            print(
                f"agent_policy.grants: skipping malformed grant {grant.id!r} "
                "(invalid scope_kind, granted_by, expiry, or missing required scope fields)",
                file=sys.stderr,
            )
            continue
        result.append(grant)
    return result


def _is_well_formed(grant: Grant) -> bool:
    """Reject grants whose stored shape violates issue-time invariants.

    Defense-in-depth against hand-edited grants files: even if the CLI
    is bypassed, the hook will not honor a grant with an unknown
    scope_kind, an invalid expiry timestamp, or an agent-issued grant
    that lacks the narrowing the CLI requires.
    """
    if grant.scope_kind not in SCOPE_KINDS:
        return False
    if grant.granted_by not in GRANTED_BY_VALUES:
        return False
    if grant.expires_at:
        try:
            expiry = datetime.fromisoformat(grant.expires_at)
        except (TypeError, ValueError):
            return False
    else:
        expiry = None
    if grant.scope_kind == "duration" and expiry is None:
        return False
    if grant.scope_kind == "session" and not grant.session_id:
        return False
    if grant.scope_kind == "once" and grant.remaining_uses is None:
        return False
    if grant.granted_by == "agent_after_user_approval":
        if not grant.approval_quote:
            return False
        if not (grant.command_pattern or grant.path_glob):
            return False
        if expiry is not None and grant.granted_at:
            try:
                issued = datetime.fromisoformat(grant.granted_at)
            except (TypeError, ValueError):
                return False
            if expiry - issued > AGENT_MAX_DURATION:
                return False
    return True


def save_grants(grants: list[Grant], path: Path | None = None) -> None:
    """Atomic write: tempfile in same directory + os.replace.

    Same-directory tempfile keeps the rename within one filesystem so
    os.replace is guaranteed atomic. Callers can race on the read/modify
    cycle, but no reader will ever see a half-written file.
    """
    target = path or DEFAULT_GRANTS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"grants": [asdict(g) for g in grants]}
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    tmp = target.with_name(f"{target.name}.tmp.{os.getpid()}")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def prune_expired(
    grants: list[Grant], *, now: datetime | None = None
) -> tuple[list[Grant], list[Grant]]:
    moment = now or datetime.now(timezone.utc)
    kept: list[Grant] = []
    expired: list[Grant] = []
    for grant in grants:
        if grant.is_expired(now=moment):
            expired.append(grant)
        else:
            kept.append(grant)
    return kept, expired


def prune_session(
    grants: list[Grant], session_id: str
) -> tuple[list[Grant], list[Grant]]:
    if not session_id:
        return grants, []
    kept: list[Grant] = []
    expired: list[Grant] = []
    for grant in grants:
        if grant.scope_kind == "session" and grant.session_id == session_id:
            expired.append(grant)
        else:
            kept.append(grant)
    return kept, expired


def add_grant(grant: Grant, *, path: Path | None = None) -> Grant:
    grants = load_grants(path)
    grants.append(grant)
    save_grants(grants, path)
    return grant


def revoke_grant(grant_id: str, *, path: Path | None = None) -> Grant | None:
    grants = load_grants(path)
    revoked = next((grant for grant in grants if grant.id == grant_id), None)
    if revoked is None:
        return None
    save_grants([grant for grant in grants if grant is not revoked], path)
    return revoked


def match_active_grant(
    *,
    rule_id: str,
    command: str = "",
    patch_paths: Iterable[str] = (),
    session_id: str = "",
    path: Path | None = None,
    now: datetime | None = None,
) -> tuple[Grant | None, list[Grant]]:
    """Find the first matching, non-expired grant for the rule.

    Side effect: prunes expired entries, and decrements remaining_uses
    on the matched grant (deletes it if uses hit zero). Always re-saves
    the file when state changes.

    Returns (matched_grant_or_none, expired_grants_pruned) so the caller
    can log audit events.
    """
    grants = load_grants(path)
    if not grants:
        return None, []
    moment = now or datetime.now(timezone.utc)
    kept, expired = prune_expired(grants, now=moment)
    paths_list = list(patch_paths)
    matched = next(
        (
            grant
            for grant in kept
            if _grant_applies(grant, rule_id, command, paths_list, session_id)
        ),
        None,
    )
    state_changed = bool(expired)
    if matched is not None and matched.remaining_uses is not None:
        matched.remaining_uses -= 1
        if matched.remaining_uses <= 0:
            kept.remove(matched)
        state_changed = True
    if state_changed:
        save_grants(kept, path)
    return matched, expired


def consume_matching_grants(
    *,
    rule_ids: Iterable[str],
    command: str = "",
    patch_paths: Iterable[str] = (),
    session_id: str = "",
    path: Path | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, Grant], list[Grant]]:
    """Match active grants against a batch of rule_ids in one IO cycle.

    Returns ``(matches_by_rule_id, expired_grants)``. The map only
    includes rule_ids that found a matching grant; the same grant may
    cover multiple distinct rule_ids, in which case ``remaining_uses``
    is decremented once per rule_id matched.

    Same-rule duplicates within the batch share a single grant
    consumption (one tool invocation = one grant use per rule), which
    matches user expectations: ``--once`` means "one tool call", not
    "one rule firing".
    """
    grants = load_grants(path)
    if not grants:
        return {}, []
    moment = now or datetime.now(timezone.utc)
    kept, expired = prune_expired(grants, now=moment)
    paths_list = list(patch_paths)
    matches: dict[str, Grant] = {}
    state_changed = bool(expired)
    for rule_id in rule_ids:
        if rule_id in matches:
            continue
        match = next(
            (
                grant
                for grant in kept
                if _grant_applies(grant, rule_id, command, paths_list, session_id)
            ),
            None,
        )
        if match is None:
            continue
        matches[rule_id] = match
        if match.remaining_uses is not None:
            match.remaining_uses -= 1
            if match.remaining_uses <= 0 and match in kept:
                kept.remove(match)
            state_changed = True
    if state_changed:
        save_grants(kept, path)
    return matches, expired


def _grant_applies(
    grant: Grant,
    rule_id: str,
    command: str,
    patch_paths: list[str],
    session_id: str,
) -> bool:
    if grant.rule_id != rule_id:
        return False
    if grant.scope_kind == "session" and grant.session_id != session_id:
        return False
    if grant.command_pattern and not _command_matches(command, grant.command_pattern):
        return False
    if grant.path_glob and not _all_paths_match(patch_paths, grant.path_glob):
        return False
    return True


def _command_matches(command: str, pattern: str) -> bool:
    """Match `command` against `pattern` with a deliberately narrow semantic.

    - Compound shell commands (anything containing ; && || | ` $() ) never
      match: each segment must be authorized separately. Without this,
      a user grant for `git clean -f .venv` would also authorize
      `git clean -f .venv; rm -rf /` via raw substring containment.
    - Glob patterns (* ? [) match the *whole* command via fnmatch only;
      no auto-broadening to `*pattern*`.
    - Literal patterns use substring containment within the single
      (non-compound) command.
    """
    if not pattern:
        return True
    if _COMPOUND_OPERATORS.search(command):
        return False
    if any(ch in pattern for ch in "*?["):
        return fnmatch.fnmatchcase(command, pattern)
    return pattern in command


def _all_paths_match(paths: Iterable[str], glob: str) -> bool:
    """A path-glob grant only fires when *every* changed path is in scope.

    Otherwise a grant scoped to `tests/**` would silently authorize a
    multi-file patch that also touches `core/services/...`.
    Empty path list → no match (a glob-scoped grant has nothing to bind to).
    """
    paths_list = list(paths)
    if not paths_list:
        return False
    return all(fnmatch.fnmatchcase(path, glob) for path in paths_list)


def parse_duration(value: str) -> timedelta:
    """Parse 5m / 2h / 7d duration strings; cap at MAX_DURATION."""
    match = re.fullmatch(r"(\d+)([dhm])", value.strip())
    if not match:
        raise ValueError("duration must look like 5m, 2h, or 7d")
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "d":
        delta = timedelta(days=amount)
    elif unit == "h":
        delta = timedelta(hours=amount)
    else:
        delta = timedelta(minutes=amount)
    if delta > MAX_DURATION:
        raise ValueError(
            f"duration exceeds {MAX_DURATION.days}d cap; "
            "for permanent exemptions, edit scripts/agent_policy/policy.py instead."
        )
    if delta <= timedelta(0):
        raise ValueError("duration must be positive")
    return delta


def patch_paths_from(patch_text: str, tool_input: dict | None = None) -> list[str]:
    """Extract added-to paths from a patch payload (delegates to policy.py)."""
    # Local import: _iter_patch_additions is a private helper; importing it
    # at module scope would over-couple the modules and freeze it as public.
    from scripts.agent_policy.policy import _iter_patch_additions

    paths = {
        path
        for path, _ in _iter_patch_additions(patch_text, tool_input or {})
        if path
    }
    return sorted(paths)
