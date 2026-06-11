#!/usr/bin/env python3
"""CLI for managing agent-policy grants.

A grant is a temporary, scoped exemption from a policy rule. See
`scripts/agent_policy/grants.py` for storage; this module is just the
user-facing CLI.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.agent_policy.friction import append_event
    from scripts.agent_policy.grants import (
        AGENT_MAX_DURATION,
        DEFAULT_GRANTS_PATH,
        GRANTED_BY_VALUES,
        Grant,
        add_grant,
        load_grants,
        new_grant_id,
        now_iso,
        parse_duration,
        prune_expired,
        revoke_grant,
        save_grants,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.agent_policy.friction import append_event
    from scripts.agent_policy.grants import (
        AGENT_MAX_DURATION,
        DEFAULT_GRANTS_PATH,
        GRANTED_BY_VALUES,
        Grant,
        add_grant,
        load_grants,
        new_grant_id,
        now_iso,
        parse_duration,
        prune_expired,
        revoke_grant,
        save_grants,
    )


def cmd_grant(args: argparse.Namespace) -> int:
    scope_flags = sum(bool(x) for x in (args.once, args.duration, args.session))
    if scope_flags == 0:
        print(
            "error: must specify exactly one of --once, --duration, or --session",
            file=sys.stderr,
        )
        return 2
    if scope_flags > 1:
        print(
            "error: --once, --duration, and --session are mutually exclusive",
            file=sys.stderr,
        )
        return 2

    if args.session:
        if args.tool != "claude":
            print(
                "error: --session is Claude Code only (relies on Stop-hook session_id "
                "pruning that codex/augment do not emit). Pass --tool claude, or use "
                "--duration <window> instead.",
                file=sys.stderr,
            )
            return 2
        if not args.session_id:
            print(
                "error: --session requires --session-id "
                "(copy it from the hook's error message)",
                file=sys.stderr,
            )
            return 2

    if not args.reason or not args.reason.strip():
        print("error: --reason is required", file=sys.stderr)
        return 2

    if args.granted_by not in GRANTED_BY_VALUES:
        print(
            f"error: --granted-by must be one of {', '.join(GRANTED_BY_VALUES)}",
            file=sys.stderr,
        )
        return 2

    if args.granted_by == "agent_after_user_approval":
        if not args.approval_quote:
            print(
                "error: --approval-quote required when --granted-by=agent_after_user_approval",
                file=sys.stderr,
            )
            return 2
        if not (args.pattern or args.path_glob):
            print(
                "error: --granted-by=agent_after_user_approval requires --pattern or "
                "--path-glob (scope-less agent self-grants are not allowed; if the user "
                "wants a broad grant they should run grant.py themselves with --granted-by user)",
                file=sys.stderr,
            )
            return 2

    now = datetime.now(timezone.utc)
    expires_at: str | None = None
    scope_kind: str
    remaining_uses: int | None = None

    if args.duration:
        try:
            delta = parse_duration(args.duration)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if (
            args.granted_by == "agent_after_user_approval"
            and delta > AGENT_MAX_DURATION
        ):
            print(
                f"error: --granted-by=agent_after_user_approval caps --duration at "
                f"{AGENT_MAX_DURATION.days}d (longer agent self-grants must come from "
                "a human via --granted-by=user, which honors the 30d cap)",
                file=sys.stderr,
            )
            return 2
        expires_at = (now + delta).isoformat()
        scope_kind = "duration"
    elif args.once:
        scope_kind = "once"
        remaining_uses = 1
    else:
        scope_kind = "session"

    grant = Grant(
        id=new_grant_id(now),
        rule_id=args.rule,
        scope_kind=scope_kind,
        expires_at=expires_at,
        session_id=args.session_id if args.session else None,
        command_pattern=args.pattern or None,
        path_glob=args.path_glob or None,
        remaining_uses=remaining_uses,
        granted_by=args.granted_by,
        approval_quote=args.approval_quote or None,
        reason=args.reason.strip(),
        granted_at=now_iso(now),
    )

    add_grant(grant, path=args.grants_path)

    append_event(
        rule_id=args.rule,
        decision="grant_issued",
        reason=grant.reason,
        summary=_summarize_grant(grant),
        tool=args.tool or "",
        event="",
        source="explicit",
        log_path=args.log_path,
        now=now,
    )

    print(f"Granted {grant.id} for {grant.rule_id} (scope={grant.scope_kind}).")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    grants = load_grants(args.grants_path)
    if not args.include_expired:
        grants, _ = prune_expired(grants)

    if args.rule:
        grants = [g for g in grants if g.rule_id == args.rule]

    if not grants:
        print("No active grants.")
        return 0

    rows = [("ID", "RULE", "SCOPE", "EXPIRES", "PATTERN", "REASON")]
    now = datetime.now(timezone.utc)
    for g in grants:
        rows.append(
            (
                g.id,
                g.rule_id,
                g.scope_kind,
                g.time_to_expiry(now=now),
                _short(g.command_pattern or g.path_glob or "—", 32),
                _short(g.reason, 48),
            )
        )

    widths = [max(len(str(row[i])) for row in rows) for i in range(len(rows[0]))]
    for index, row in enumerate(rows):
        line = "  ".join(str(cell).ljust(widths[col]) for col, cell in enumerate(row))
        print(line)
        if index == 0:
            print("  ".join("-" * widths[col] for col in range(len(rows[0]))))
    return 0


def cmd_revoke(args: argparse.Namespace) -> int:
    grant = revoke_grant(args.grant_id, path=args.grants_path)
    if not grant:
        print(f"error: no grant with id {args.grant_id!r}", file=sys.stderr)
        return 1
    append_event(
        rule_id=grant.rule_id,
        decision="grant_revoked",
        reason=f"Revoked grant {grant.id}",
        summary=_summarize_grant(grant),
        tool=args.tool or "",
        event="",
        source="explicit",
        log_path=args.log_path,
    )
    print(f"Revoked grant {grant.id} (rule {grant.rule_id}).")
    return 0


def cmd_clear(args: argparse.Namespace) -> int:
    if not args.rule and not args.all:
        print("error: --rule or --all required", file=sys.stderr)
        return 2
    grants = load_grants(args.grants_path)
    if not grants:
        print("No grants to clear.")
        return 0

    if args.all:
        if not args.yes:
            response = input(
                f"Clear ALL {len(grants)} grants? [y/N] "
            ).strip().lower()
            if response not in ("y", "yes"):
                print("Aborted.")
                return 1
        cleared = grants
        remaining: list[Grant] = []
    else:
        cleared = [g for g in grants if g.rule_id == args.rule]
        remaining = [g for g in grants if g.rule_id != args.rule]
        if not cleared:
            print(f"No grants matching rule {args.rule!r}.")
            return 0

    save_grants(remaining, args.grants_path)
    for g in cleared:
        append_event(
            rule_id=g.rule_id,
            decision="grant_revoked",
            reason="Cleared via grant.py clear",
            summary=_summarize_grant(g),
            tool=args.tool or "",
            event="",
            source="explicit",
            log_path=args.log_path,
        )
    print(f"Cleared {len(cleared)} grant(s).")
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    grants = load_grants(args.grants_path)
    kept, expired = prune_expired(grants)
    if expired:
        save_grants(kept, args.grants_path)
        for g in expired:
            append_event(
                rule_id=g.rule_id,
                decision="grant_expired",
                reason=f"Pruned expired grant {g.id}",
                summary=_summarize_grant(g),
                tool=args.tool or "",
                event="",
                source="automatic",
                log_path=args.log_path,
            )
    print(f"Pruned {len(expired)} expired grant(s); {len(kept)} active.")
    return 0


def _summarize_grant(g: Grant) -> str:
    parts = [f"scope={g.scope_kind}"]
    if g.expires_at:
        parts.append(f"expires_at={g.expires_at}")
    if g.session_id:
        parts.append(f"session={g.session_id[:12]}")
    if g.command_pattern:
        parts.append(f"pattern={g.command_pattern!r}")
    if g.path_glob:
        parts.append(f"path_glob={g.path_glob!r}")
    if g.remaining_uses is not None:
        parts.append(f"remaining_uses={g.remaining_uses}")
    if g.granted_by:
        parts.append(f"by={g.granted_by}")
    return " ".join(parts)


def _short(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage temporary, scoped exemptions to agent-policy rules. "
        "See docs/canonical-patterns.md for the rule catalogue.",
    )
    parser.add_argument(
        "--grants-path", type=Path, default=None,
        help=f"Override grants file path (default: {DEFAULT_GRANTS_PATH}).",
    )
    parser.add_argument(
        "--log-path", type=Path, default=None,
        help="Override friction log path (default: logs/agent_policy/friction.jsonl).",
    )
    parser.add_argument(
        "--tool", default="",
        help="Tool emitting the request (claude/codex/augment); recorded in audit log.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    grant_p = sub.add_parser(
        "grant",
        help="Issue a new grant exempting a rule for a scope/duration.",
    )
    grant_p.add_argument("--rule", required=True, help="Rule ID to exempt (e.g. command.git_clean_force).")
    scope_group = grant_p.add_argument_group("scope (pick one)")
    scope_group.add_argument("--once", action="store_true", help="One-shot: consumed by next match.")
    scope_group.add_argument("--duration", help="Time-bounded; e.g. 30m, 2h, 7d (cap 30d).")
    scope_group.add_argument("--session", action="store_true", help="Session-bound (Claude Code only).")
    grant_p.add_argument("--session-id", help="Session ID (required for --session).")
    grant_p.add_argument("--pattern", help="Narrow to commands containing this substring or matching this glob.")
    grant_p.add_argument("--path-glob", help="Narrow to patches against paths matching this fnmatch glob.")
    grant_p.add_argument("--reason", required=True, help="Why this grant exists (for audit log).")
    grant_p.add_argument(
        "--granted-by", default="user",
        choices=GRANTED_BY_VALUES,
        help="Who issued the grant (user / agent_after_user_approval).",
    )
    grant_p.add_argument(
        "--approval-quote",
        help="If --granted-by=agent_after_user_approval, the user's quoted approval line.",
    )
    grant_p.set_defaults(func=cmd_grant)

    list_p = sub.add_parser("list", help="Show active grants.")
    list_p.add_argument("--rule", help="Filter to one rule.")
    list_p.add_argument("--include-expired", action="store_true", help="Show expired entries too.")
    list_p.set_defaults(func=cmd_list)

    revoke_p = sub.add_parser("revoke", help="Revoke a single grant by ID.")
    revoke_p.add_argument("grant_id")
    revoke_p.set_defaults(func=cmd_revoke)

    clear_p = sub.add_parser("clear", help="Bulk revoke grants by rule, or all of them.")
    clear_p.add_argument("--rule", help="Clear only grants for this rule.")
    clear_p.add_argument("--all", action="store_true", help="Clear all grants.")
    clear_p.add_argument("--yes", action="store_true", help="Skip confirmation prompt for --all.")
    clear_p.set_defaults(func=cmd_clear)

    prune_p = sub.add_parser("prune", help="Remove expired grants (also runs lazily on hook read).")
    prune_p.set_defaults(func=cmd_prune)

    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
